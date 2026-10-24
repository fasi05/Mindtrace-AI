"""All database operations. No Streamlit imports; every write runs in one transaction."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from database.models import (Activity, ConceptMastery, DiagnosisSession, Learner, MasteryHistory,
                             PracticeAttempt, PracticeQuestion)
from models.concepts import concept_name
from models.schemas import DiagnosisResult
from services import mastery as M
from services.practice import VerifiedItem


@dataclass
class AttemptOutcome:
    attempt: PracticeAttempt
    created: bool
    mission_complete: bool


def request_hash(subject: str, topic: str, question: str, answer: str, reasoning: str) -> str:
    raw = "\x1f".join(x.strip() for x in (subject, topic, question, answer, reasoning))
    return hashlib.sha256(raw.encode()).hexdigest()


class Repository:
    def __init__(self, factory: sessionmaker):
        self._factory = factory

    @contextmanager
    def _scope(self) -> Iterator[Session]:
        s = self._factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # ---------------------------------------------------------------- learners
    def get_or_create_learner(self, code: str) -> Learner:
        with self._scope() as s:
            learner = s.scalars(select(Learner).where(Learner.code == code)).first()
            if learner:
                return learner
            learner = Learner(code=code)
            s.add(learner)
            try:
                s.flush()
            except IntegrityError:  # concurrent rerun created it first
                s.rollback()
                learner = s.scalars(select(Learner).where(Learner.code == code)).one()
            return learner

    def learner_exists(self, code: str) -> bool:
        with self._scope() as s:
            return s.scalars(select(Learner.id).where(Learner.code == code)).first() is not None

    def delete_learner_data(self, learner_id: int) -> None:
        with self._scope() as s:
            ids = s.scalars(select(DiagnosisSession.id).where(DiagnosisSession.learner_id == learner_id)).all()
            qids = s.scalars(select(PracticeQuestion.id).where(PracticeQuestion.session_id.in_(ids))).all() if ids else []
            if qids:
                s.execute(delete(PracticeAttempt).where(PracticeAttempt.question_id.in_(qids)))
                s.execute(delete(PracticeQuestion).where(PracticeQuestion.id.in_(qids)))
            for model in (Activity, MasteryHistory, ConceptMastery, DiagnosisSession):
                s.execute(delete(model).where(model.learner_id == learner_id))
            s.execute(delete(Learner).where(Learner.id == learner_id))

    # --------------------------------------------------------------- diagnoses
    FINAL_STATUSES = ("correct", "misconception_found")

    @staticmethod
    def _label(result: DiagnosisResult) -> str:
        d = result.diagnosis
        return {"correct": "Diagnosis: work verified correct",
                "misconception_found": f"Diagnosis: {d.misconception_label if d else 'misconception found'}",
                "incorrect": "Diagnosis: verified incorrect (no specific misconception shown)",
                "insufficient_evidence": "Diagnosis: more working needed"}[result.status][:300]

    @staticmethod
    def _fill(row: DiagnosisSession, result: DiagnosisResult) -> None:
        d = result.diagnosis
        row.status, row.concept_id = result.status, result.concept_id
        row.misconception_category = d.misconception_category if d else None
        row.misconception_label = d.misconception_label if d else None
        row.confidence, row.result = result.confidence, result.model_dump(mode="json")
        row.provider, row.model = result.provider, result.model

    def create_diagnosis(self, learner_id: int, subject: str, topic: str, question: str, answer: str,
                         reasoning: str, result: DiagnosisResult) -> tuple[DiagnosisSession, bool]:
        """Idempotent on identical input. A non-final earlier result (insufficient/incorrect) for the SAME
        input is refreshed in place, so a retry is never stuck behind a stale record. Returns (session, created)."""
        h = request_hash(subject, topic, question, answer, reasoning)
        with self._scope() as s:
            existing = s.scalars(select(DiagnosisSession).where(
                DiagnosisSession.learner_id == learner_id, DiagnosisSession.request_hash == h)).first()
            if existing:
                if existing.status in self.FINAL_STATUSES or existing.status == result.status:
                    return existing, False
                had_mastery = existing.status in ("incorrect", "misconception_found", "correct")
                self._fill(existing, result)
                if result.concept_id and result.status != "insufficient_evidence" and not had_mastery:
                    self._apply(s, learner_id, result.concept_id, False if result.status != "correct" else True,
                                "diagnosis", 0, existing.id)
                s.add(Activity(learner_id=learner_id, kind="diagnosis", detail=self._label(result),
                               session_id=existing.id))
                return existing, False
            row = DiagnosisSession(learner_id=learner_id, request_hash=h, subject=subject, topic=topic,
                                   question=question, answer=answer, reasoning=reasoning, status=result.status,
                                   result={})
            self._fill(row, result)
            s.add(row)
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                row = s.scalars(select(DiagnosisSession).where(
                    DiagnosisSession.learner_id == learner_id, DiagnosisSession.request_hash == h)).one()
                return row, False
            if result.status != "insufficient_evidence" and result.concept_id:
                self._apply(s, learner_id, result.concept_id, result.status == "correct", "diagnosis", 0, row.id)
            s.add(Activity(learner_id=learner_id, kind="diagnosis", detail=self._label(result), session_id=row.id))
            return row, True

    def find_session(self, learner_id: int, subject: str, topic: str, question: str, answer: str,
                     reasoning: str) -> Optional[DiagnosisSession]:
        h = request_hash(subject, topic, question, answer, reasoning)
        with self._scope() as s:
            return s.scalars(select(DiagnosisSession).where(
                DiagnosisSession.learner_id == learner_id, DiagnosisSession.request_hash == h)).first()

    def get_session(self, session_id: int, learner_id: int) -> Optional[DiagnosisSession]:
        with self._scope() as s:
            return s.scalars(select(DiagnosisSession).where(
                DiagnosisSession.id == session_id, DiagnosisSession.learner_id == learner_id)).first()

    def list_sessions(self, learner_id: int, limit: int = 50) -> list[DiagnosisSession]:
        with self._scope() as s:
            return list(s.scalars(select(DiagnosisSession).where(DiagnosisSession.learner_id == learner_id)
                                  .order_by(DiagnosisSession.created_at.desc(), DiagnosisSession.id.desc()).limit(limit)))

    # ---------------------------------------------------------------- practice
    def add_practice_set(self, session_id: int, learner_id: int, concept_id: Optional[str],
                         items: list[VerifiedItem]) -> list[PracticeQuestion]:
        """Idempotent: if questions already exist for the session they are returned unchanged."""
        with self._scope() as s:
            sess = s.scalars(select(DiagnosisSession).where(
                DiagnosisSession.id == session_id, DiagnosisSession.learner_id == learner_id)).first()
            if sess is None:
                raise LookupError("Session not found.")
            existing = list(s.scalars(select(PracticeQuestion).where(PracticeQuestion.session_id == session_id)
                                      .order_by(PracticeQuestion.position)))
            if existing:
                return existing
            rows = [PracticeQuestion(session_id=session_id, position=i, kind=it.kind, question=it.question,
                                     expected_answer=it.expected_answer, hints=it.hints, difficulty=it.difficulty,
                                     concept_id=concept_id) for i, it in enumerate(items)]
            s.add_all(rows)
            s.add(Activity(learner_id=learner_id, kind="mission_started",
                           detail=f"Repair mission created ({len(rows)} questions)", session_id=session_id))
            return rows

    def get_questions(self, session_id: int) -> list[tuple[PracticeQuestion, Optional[PracticeAttempt]]]:
        with self._scope() as s:
            qs = list(s.scalars(select(PracticeQuestion).where(PracticeQuestion.session_id == session_id)
                                .order_by(PracticeQuestion.position)))
            atts = {a.question_id: a for a in s.scalars(select(PracticeAttempt).where(
                PracticeAttempt.question_id.in_([q.id for q in qs])))} if qs else {}
            return [(q, atts.get(q.id)) for q in qs]

    def reveal_hint(self, question_id: int, learner_id: int) -> int:
        """Reveal the next hint (max 2). Not allowed after an attempt or on transfer questions."""
        with self._scope() as s:
            q = s.get(PracticeQuestion, question_id)
            sess = s.get(DiagnosisSession, q.session_id) if q else None
            if q is None or sess is None or sess.learner_id != learner_id:
                raise LookupError("Question not found.")
            if q.kind == "transfer" or s.scalars(select(PracticeAttempt.id).where(
                    PracticeAttempt.question_id == q.id)).first():
                return q.hints_revealed
            if q.hints_revealed < len(q.hints):
                q.hints_revealed += 1
            return q.hints_revealed

    def record_attempt(self, question_id: int, learner_id: int, answer: str, correct: bool,
                       feedback: Optional[dict]) -> AttemptOutcome:
        """Idempotent: a question has at most one scored attempt."""
        with self._scope() as s:
            q = s.get(PracticeQuestion, question_id)
            sess = s.get(DiagnosisSession, q.session_id) if q else None
            if q is None or sess is None or sess.learner_id != learner_id:
                raise LookupError("Question not found.")
            existing = s.scalars(select(PracticeAttempt).where(PracticeAttempt.question_id == q.id)).first()
            if existing:
                return AttemptOutcome(existing, False, sess.mission_completed_at is not None)
            att = PracticeAttempt(question_id=q.id, learner_id=learner_id, answer=answer, correct=correct,
                                  hints_used=q.hints_revealed if q.kind == "practice" else 0, feedback=feedback)
            s.add(att)
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                att = s.scalars(select(PracticeAttempt).where(PracticeAttempt.question_id == question_id)).one()
                return AttemptOutcome(att, False, False)
            if q.concept_id:
                self._apply(s, learner_id, q.concept_id, correct, q.kind, att.hints_used, sess.id)
            s.add(Activity(learner_id=learner_id, kind=q.kind,
                           detail=f"{'Transfer' if q.kind == 'transfer' else 'Practice'}: {'correct' if correct else 'incorrect'}",
                           session_id=sess.id))
            total = s.scalar(select(func.count(PracticeQuestion.id)).where(PracticeQuestion.session_id == sess.id))
            done = s.scalar(select(func.count(PracticeAttempt.id)).join(PracticeQuestion).where(
                PracticeQuestion.session_id == sess.id))
            complete = bool(total) and done >= total
            if complete and sess.mission_completed_at is None:
                from database.models import utcnow
                sess.mission_completed_at = utcnow()
                s.add(Activity(learner_id=learner_id, kind="mission_completed",
                               detail="Repair mission completed", session_id=sess.id))
            return AttemptOutcome(att, True, complete)

    # ----------------------------------------------------------------- mastery
    def _apply(self, s: Session, learner_id: int, concept_id: str, correct: bool, source: str,
               hints_used: int, session_id: Optional[int]) -> None:
        row = s.scalars(select(ConceptMastery).where(
            ConceptMastery.learner_id == learner_id, ConceptMastery.concept_id == concept_id)).first()
        if row is None:
            row = ConceptMastery(learner_id=learner_id, concept_id=concept_id, attempts=0, correct_count=0,
                                 weighted_credit=0.0, weighted_total=0.0, mastery=0.5)
            s.add(row)
        w = M.ATTEMPT_WEIGHT.get(source, 1.0)
        row.attempts += 1
        row.correct_count += int(correct)
        row.weighted_total += w
        row.weighted_credit += w * M.credit(correct, hints_used)
        row.mastery = M.estimate(row.weighted_credit, row.weighted_total)
        s.add(MasteryHistory(learner_id=learner_id, concept_id=concept_id, mastery=row.mastery,
                             source=source, session_id=session_id))

    def mastery_rows(self, learner_id: int) -> list[ConceptMastery]:
        with self._scope() as s:
            return list(s.scalars(select(ConceptMastery).where(ConceptMastery.learner_id == learner_id)))

    # --------------------------------------------------------------- analytics
    def attempts_frame(self, learner_id: int) -> pd.DataFrame:
        with self._scope() as s:
            rows = s.execute(
                select(PracticeAttempt.created_at, PracticeAttempt.correct, PracticeAttempt.hints_used,
                       PracticeQuestion.kind, PracticeQuestion.concept_id, PracticeQuestion.session_id)
                .join(PracticeQuestion, PracticeQuestion.id == PracticeAttempt.question_id)
                .where(PracticeAttempt.learner_id == learner_id).order_by(PracticeAttempt.created_at)).all()
        return pd.DataFrame(rows, columns=["created_at", "correct", "hints_used", "kind", "concept_id", "session_id"])

    def sessions_frame(self, learner_id: int) -> pd.DataFrame:
        cols = ["id", "created_at", "status", "concept_id", "misconception_category", "misconception_label",
                "confidence", "mission_completed_at"]
        with self._scope() as s:
            rows = s.execute(select(*[getattr(DiagnosisSession, c) for c in cols])
                             .where(DiagnosisSession.learner_id == learner_id)
                             .order_by(DiagnosisSession.created_at)).all()
        return pd.DataFrame(rows, columns=cols)

    def mastery_history_frame(self, learner_id: int) -> pd.DataFrame:
        with self._scope() as s:
            rows = s.execute(select(MasteryHistory.created_at, MasteryHistory.concept_id, MasteryHistory.mastery,
                                    MasteryHistory.source).where(MasteryHistory.learner_id == learner_id)
                             .order_by(MasteryHistory.created_at)).all()
        return pd.DataFrame(rows, columns=["created_at", "concept_id", "mastery", "source"])

    def recent_activity(self, learner_id: int, limit: int = 8) -> list[Activity]:
        with self._scope() as s:
            return list(s.scalars(select(Activity).where(Activity.learner_id == learner_id)
                                  .order_by(Activity.created_at.desc(), Activity.id.desc()).limit(limit)))

    def open_mission(self, learner_id: int) -> Optional[DiagnosisSession]:
        """Most recent session whose mission has questions but is not completed."""
        with self._scope() as s:
            q = (select(DiagnosisSession).where(DiagnosisSession.learner_id == learner_id,
                                                DiagnosisSession.mission_completed_at.is_(None),
                                                DiagnosisSession.id.in_(select(PracticeQuestion.session_id)))
                 .order_by(DiagnosisSession.created_at.desc()).limit(1))
            return s.scalars(q).first()

    def dashboard(self, learner_id: int) -> dict:
        sessions = self.sessions_frame(learner_id)
        att = self.attempts_frame(learner_id)
        mastery_rows = self.mastery_rows(learner_id)
        done = sessions[sessions["status"].isin(["correct", "misconception_found", "incorrect"])] if len(sessions) else sessions
        assessed = [r for r in mastery_rows if M.is_assessed(r.attempts)]
        ranked = sorted(assessed, key=lambda r: r.mastery)
        return {
            "diagnoses": int(len(done)),
            "attempts": int(len(att)),
            "accuracy": float(att["correct"].mean()) if len(att) else None,
            "mastery": mastery_rows,
            "strongest": [r for r in reversed(ranked) if r.mastery >= 0.5][:3],
            "weakest": [r for r in ranked if r.mastery < 0.75][:3],
            "recent": self.recent_activity(learner_id),
            "open_mission": self.open_mission(learner_id),
        }

    def recommend_next(self, learner_id: int, dash: Optional[dict] = None) -> dict:
        dash = dash or self.dashboard(learner_id)
        if dash["open_mission"] is not None:
            return {"action": "mission", "text": "Finish your open repair mission.", "session_id": dash["open_mission"].id}
        if dash["weakest"]:
            w = dash["weakest"][0]
            return {"action": "diagnose",
                    "text": f"Run a new diagnosis on {concept_name(w.concept_id)} (mastery {w.mastery:.0%}, {w.attempts} attempts)."}
        if dash["diagnoses"] == 0:
            return {"action": "diagnose", "text": "Start your first diagnosis to begin building a mastery profile."}
        return {"action": "diagnose",
                "text": "Not enough attempts yet to rank concepts. Try another problem to build evidence."}
