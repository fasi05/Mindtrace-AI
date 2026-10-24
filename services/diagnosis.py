"""Misconception Trace Engine: verify -> gather evidence -> AI diagnosis -> ground & validate."""
from __future__ import annotations

import re
from typing import Optional

from models.concepts import CONCEPTS
from models.schemas import DiagnosisAI, DiagnosisResult, WorkAnalysis
from services import prompts
from services.ai_client import StructuredAI
from services.math_verifier import analyze_work, canonical_steps, extract_math
from utils.validation import validate_diagnosis_input


def infer_concept(analysis: WorkAnalysis, question: str) -> Optional[str]:
    """Deterministic concept guess from problem structure (used when no AI concept exists)."""
    text = extract_math(question)
    if analysis.problem_type == "equation":
        has_paren = "(" in text
        if has_paren:
            return "multi_step_equations"
        ops = len(re.findall(r"(?<=[a-z0-9\)])\s*[+\-]\s*(?=[0-9a-z\(])", text.split("=")[0]))
        return "two_step_equations" if ops >= 1 and re.search(r"\d\s*\*?\s*[a-z]", text) else "one_step_equations"
    if analysis.problem_type == "expression":
        return "distributive_property" if "(" in text else "simplifying_expressions"
    return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).lower().replace("−", "-")


def _quote_in(quote: str, *sources: str) -> bool:
    q = _norm(quote)
    return bool(q) and any(q in _norm(s) for s in sources)


class DiagnosisService:
    def __init__(self, ai: StructuredAI):
        self.ai = ai

    def diagnose(self, question: str, answer: str, reasoning: str = "") -> DiagnosisResult:
        """Deterministic verification decides right/wrong. The AI is only asked WHY, never WHETHER."""
        question, answer, reasoning = validate_diagnosis_input(question, answer, reasoning)
        analysis = analyze_work(question, answer)
        base = dict(analysis=analysis, provider=self.ai.provider_name, model=self.ai.model)

        # 1) Not machine-verifiable: never guess right/wrong and never invent a diagnosis.
        if not analysis.verifiable:
            return self._insufficient(base, analysis, question,
                "This problem or answer could not be verified automatically (supported: single-variable equations "
                "and expression simplification). No diagnosis is given because nothing could be checked reliably.")

        wrong_step = analysis.first_inconsistent_step is not None
        final_ok = analysis.final_answer_correct

        # 2) Verified correct: every readable line consistent AND final answer correct. No AI involved.
        if final_ok is True and not wrong_step:
            return DiagnosisResult(
                status="correct", confidence=None, correct_answer=analysis.correct_answer,
                concept_id=infer_concept(analysis, question),
                correct_solution_steps=canonical_steps(question) or [],
                message="Verified: every readable line is consistent with the original problem and the final answer is correct.",
                **base)

        # 3) Steps so far are fine but nothing final to judge.
        if final_ok is None and not wrong_step:
            return self._insufficient(base, analysis, question,
                "The steps you wrote are consistent so far, but there is no final answer yet. Finish the solution and submit again.")

        # From here the work is VERIFIED WRONG (bad final answer and/or a step that changes the solution).
        working = [s for s in analysis.steps if s.parsed]
        has_working = len(working) >= 2 or bool(reasoning) or (len(working) == 1 and analysis.final_answer_text is None)
        if not has_working:
            return self._insufficient(base, analysis, question,
                "Your final answer is not correct (it does not satisfy the original problem), but one line does not show why. "
                "A misconception cannot be identified confidently without more. Please add your step-by-step working, "
                "or describe in a sentence how you got your answer.")

        verified = {
            "problem_as_math": analysis.math_text,
            "correct_answer": analysis.correct_answer,
            "learner_final_answer": analysis.final_answer_text,
            "learner_final_answer_correct": final_ok,
            "step_checks": [s.model_dump() for s in analysis.steps],
            "first_inconsistent_step_index": analysis.first_inconsistent_step,
            "detected_signals": analysis.signals,
            "notes": analysis.notes,
        }
        ai: DiagnosisAI = self.ai.generate(
            DiagnosisAI, prompts.DIAGNOSIS_SYSTEM,
            prompts.diagnosis_user_prompt(question, answer, reasoning, verified))
        return self._ground(ai, base, analysis, question, answer, reasoning)

    # ------------------------------------------------------------------ helpers
    def _insufficient(self, base: dict, analysis: WorkAnalysis, question: str, message: str) -> DiagnosisResult:
        return DiagnosisResult(status="insufficient_evidence", message=message, confidence=None,
                               correct_answer=None, concept_id=infer_concept(analysis, question), **base)

    def _incorrect(self, base: dict, analysis: WorkAnalysis, question: str, follow_up: str) -> DiagnosisResult:
        """Verified wrong, but no misconception is demonstrated by the evidence."""
        steps = canonical_steps(question) or []
        bad = (analysis.steps[analysis.first_inconsistent_step].text
               if analysis.first_inconsistent_step is not None else None)
        msg = ("Verified: this work is not correct"
               + (f" (the line \"{bad}\" changes the solution of the original problem)" if bad else "")
               + ". There is not enough evidence to name a specific misconception. " + follow_up)
        return DiagnosisResult(status="incorrect", message=msg, confidence=None, correct_answer=analysis.correct_answer,
                               concept_id=infer_concept(analysis, question), correct_solution_steps=steps, **base)

    def _ground(self, ai: DiagnosisAI, base: dict, analysis: WorkAnalysis, question: str,
                answer: str, reasoning: str) -> DiagnosisResult:
        if not ai.can_diagnose:
            return self._incorrect(base, analysis, question,
                                   ai.follow_up_request or "More working is needed to identify the misconception.")
        notes: list[str] = []
        # Keep only evidence whose quote really appears in the learner's submission.
        kept = [e for e in ai.evidence if _quote_in(e.quote, answer, reasoning)]
        dropped = len(ai.evidence) - len(kept)
        confidence = ai.confidence
        if dropped:
            notes.append(f"{dropped} evidence item(s) were removed because they did not quote your submitted work.")
        if not kept:
            return self._incorrect(base, analysis, question,
                "A specific misconception could not be tied to anything you wrote, so none is claimed. "
                "Add or clarify your working to get a diagnosis.")
        updates = {"evidence": kept}
        if ai.incorrect_step_quote and not _quote_in(ai.incorrect_step_quote, answer, reasoning):
            updates["incorrect_step_quote"] = ""
            notes.append("A quoted 'incorrect step' was removed because it does not appear in your submission.")
        ai = ai.model_copy(update=updates)
        # Confidence caps: never "certain" without independent support.
        if not analysis.verifiable:
            confidence = "low"
            notes.append("This problem could not be machine-verified, so the diagnosis is unverified.")
        elif confidence == "high" and not analysis.signals and not reasoning:
            confidence = "medium"
            notes.append("Confidence capped at medium: the diagnosis is inferred from steps alone, without a stated explanation from you.")
        if dropped and confidence == "high":
            confidence = "medium"

        # Correct solution: deterministic when possible; otherwise AI steps only if the end matches the verified answer.
        steps = canonical_steps(question)
        if steps is None:
            steps = list(ai.correct_solution_steps)
            if analysis.correct_answer:
                last = _norm(steps[-1]) if steps else ""
                if _norm(analysis.correct_answer) not in last:
                    notes.append("The AI's solution steps did not end at the verified answer, so only the verified answer is shown.")
                    steps = []
            else:
                notes.append("The correct solution could not be independently verified.")
        concept = ai.concept_id if ai.concept_id in CONCEPTS else infer_concept(analysis, question)
        return DiagnosisResult(
            status="misconception_found", message="A likely misconception was identified from your submitted work.",
            diagnosis=ai, confidence=confidence, concept_id=concept, correct_answer=analysis.correct_answer,
            correct_solution_steps=steps, verification_notes=notes, dropped_evidence=dropped, **base)
