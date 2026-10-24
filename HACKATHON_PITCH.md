# MINDTRACE AI: Hackathon Pitch

**Tagline:** Don't just correct the answer. Discover the misconception.

## Problem
Wrong answers are corrected, but the idea that produced them is rarely named. Learners repeat the same error on the next problem. Generic chatbots also make a second problem: they can state wrong maths confidently and invent a story about what the student "must have been thinking".

## Target users
Middle- and high-school algebra learners, self-study students, and tutors who want to see recurring error patterns rather than a pile of marked-wrong answers.

## Solution
MindTrace reads the learner's actual working, locates the first step that breaks, proposes a likely misconception tied to quoted evidence, verifies all maths symbolically, and runs a repair mission that ends with an unseen transfer question.

## Core innovation: the Misconception Trace Engine
1. **Verify** every submitted line with sympy (same solution set as the original problem?).
2. **Detect signals** deterministically (e.g. `2x = 14` equals `11 + 3`: the constant was added instead of subtracted).
3. **Diagnose** with an LLM constrained by those verified facts and a Pydantic schema.
4. **Ground** the answer: evidence quotes not found in the learner's text are discarded; confidence is capped when support is thin; unverifiable problems are marked low confidence.
5. **Repair**: practice items are AI-written but sympy-verified; grading is deterministic; the transfer question gets no hints.
6. **Record**: mastery updates only from stored, evaluated attempts.

## Versus a generic AI chatbot
| | Generic chatbot | MindTrace |
|---|---|---|
| Maths correctness | Trusts the model | sympy verifies steps, answers, practice |
| Explanation basis | Free text | Quoted evidence, evidence vs inference separated |
| Not enough information | Often guesses | Says it cannot diagnose and asks for working |
| After the explanation | Conversation ends | Targeted practice, transfer test, persistent mastery |
| Progress | None | Saved attempts, knowledge map, analytics |

## Two-minute live script
**0:00** "A student solves 2x + 3 = 11 and writes `2x = 14`, `x = 7`. A chatbot says 'the answer is 4'. That fixes this problem, not the student."
**0:20** Open Diagnosis workspace, press *Load sample input*, then *Analyse my work*. "This is the real pipeline: sympy checks each line, then the AI diagnoses."
**0:45** On Results: "It finds the likely error: 3 was added to the right side instead of subtracted from both sides. It quotes `2x = 14` as evidence, labels this as inference, and shows a confidence level, not certainty." Show the independent math checks panel.
**1:10** Start the repair mission. Show a hint, answer one question wrong: "verified feedback, no invented answer". Finish; the transfer question `3x + 5 = 20` has no hints.
**1:40** Open Knowledge map and Analytics: "Every number here comes from saved attempts. With little data it says so."
**1:55** "Don't just correct the answer. Discover the misconception."

## Measurable evaluation criteria
- Diagnosis grounding rate: share of diagnoses whose evidence quotes all appear in the submission.
- First-error localisation accuracy against a hand-labelled set of wrong solutions.
- Verification coverage: share of generated practice items accepted by sympy on first attempt.
- Appropriate-abstention rate on bare-answer inputs.
- Transfer-question accuracy after a mission, compared with accuracy before (needs a controlled study to claim any effect).

None of these have been measured yet; no learning-outcome claim is made.

## Limitations and future development
- Only algebra is machine-verified; other subjects are planned through the concept registry and provider-agnostic AI layer.
- No authentication; anonymous learner codes only.
- Live AI behaviour has not been evaluated in this build; misconception quality depends on the model chosen.
- Next: labelled benchmark, adaptive difficulty, teacher view of class-wide misconception patterns, Alembic migrations, accounts.
