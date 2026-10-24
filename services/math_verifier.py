"""Deterministic mathematics verification (sympy). No LLM, no code execution.

Input is whitelisted to a tiny arithmetic/algebra alphabet before it reaches the
parser, so learner- or model-supplied text can never run arbitrary code.
"""
from __future__ import annotations

import re
from typing import Optional

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from models.schemas import StepCheck, WorkAnalysis

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
_LOCALS = {c: sp.Symbol(c) for c in "abcdefghijklmnopqrstuvwxyz"}
_REPLACE = {"−": "-", "–": "-", "—": "-", "×": "*", "·": "*", "÷": "/", "²": "^2", "³": "^3",
            "“": "", "”": "", '"': "", "'": "", "`": "", "$": ""}
_ALLOWED = re.compile(r"^[a-z0-9\s+\-*/^().=]+$")
MAX_LEN = 120


class MathParseError(ValueError):
    """Text could not be safely parsed as algebra."""


def _normalize(text: str) -> str:
    for k, v in _REPLACE.items():
        text = text.replace(k, v)
    return re.sub(r"\s+", " ", text.lower()).strip().strip(".").strip()


def _safe_text(text: str) -> str:
    s = _normalize(text)
    if not s:
        raise MathParseError("Empty expression.")
    if len(s) > MAX_LEN:
        raise MathParseError("Expression is too long.")
    if not _ALLOWED.match(s):
        raise MathParseError("Only numbers, one-letter variables and + - * / ^ ( ) = are supported.")
    if re.search(r"[a-z]{2,}", s):
        raise MathParseError("Use single-letter variables (write x*y, not xy).")
    if re.search(r"\d{7,}", s) or s.count("^") > 2 or s.count("**") > 0:
        raise MathParseError("Numbers or exponents are too large to verify.")
    return s


def parse_math(text: str) -> sp.Expr:
    s = _safe_text(text)
    if "=" in s:
        raise MathParseError("Expected an expression, found '='.")
    try:
        return parse_expr(s, local_dict=dict(_LOCALS), transformations=_TRANSFORMS)
    except Exception as exc:  # sympy raises many types
        raise MathParseError(f"Could not read '{text.strip()}' as math.") from exc


def parse_equation(text: str) -> tuple[sp.Expr, sp.Expr]:
    s = _safe_text(text)
    if s.count("=") != 1:
        raise MathParseError("Expected exactly one '=' sign.")
    left, right = s.split("=")
    if not left.strip() or not right.strip():
        raise MathParseError("Both sides of '=' are required.")
    return parse_math(left), parse_math(right)


def fmt(expr: sp.Expr) -> str:
    """Readable string: 2*x + 6 -> '2x + 6'."""
    s = str(expr).replace("**", "^")
    s = re.sub(r"(?<=\d)\*(?=[a-z(])", "", s)
    return s.replace("*", "")


def extract_math(question: str) -> str:
    """Pull the math out of 'Solve "2x + 3 = 11"' / 'Solve for x: 2x+3=11'."""
    q = _normalize(question)
    if ":" in q:
        q = q.rsplit(":", 1)[1].strip()
    q = re.split(r",| where | if | and ", q)[0]
    q = re.sub(r"^(?:[a-z]{2,}\s*)+", "", q)  # leading words (solve, the, equation ...)
    q = re.sub(r"(?:\s+[a-z]{2,})+$", "", q)  # trailing words (for x ...)
    return q.strip(" .?")


# ---------------------------------------------------------------- equations ---
def _solve(lhs: sp.Expr, rhs: sp.Expr) -> tuple[sp.Symbol, list[sp.Expr]]:
    expr = sp.simplify(lhs - rhs)
    syms = sorted(expr.free_symbols, key=str)
    if len(syms) != 1:
        raise MathParseError("Only equations with exactly one variable can be verified.")
    var = syms[0]
    sols = sp.solve(expr, var)
    return var, [sp.nsimplify(s) for s in sols if s.is_real is not False]


def _same(a: sp.Expr, b: sp.Expr) -> bool:
    try:
        return sp.simplify(a - b) == 0
    except Exception:
        return False


def _linear_parts(lhs, rhs, var):
    """Return (a, b, c) when the equation is a*var + b = c with c free of var."""
    if rhs.has(var):
        return None
    try:
        poly = sp.Poly(sp.expand(lhs), var)
    except sp.PolynomialError:
        return None
    if poly.degree() != 1:
        return None
    a, b = poly.coeff_monomial(var), poly.coeff_monomial(1)
    return a, b, rhs


def _term(a: sp.Expr, var: sp.Symbol) -> str:
    if a == 1:
        return str(var)
    if a == -1:
        return f"-{var}"
    return f"{fmt(a)}{var}"


def canonical_steps(question: str) -> Optional[list[str]]:
    """Deterministic correct solution for a*x + b = c style equations, else None."""
    try:
        lhs, rhs = parse_equation(extract_math(question))
        var, sols = _solve(lhs, rhs)
        parts = _linear_parts(lhs, rhs, var)
    except (MathParseError, Exception):
        return None
    if parts is None or len(sols) != 1:
        return None
    a, b, c = parts
    steps = [f"{fmt(lhs)} = {fmt(rhs)}"]
    cur_rhs = c
    if b != 0:
        verb = "-" if b > 0 else "+"
        steps.append(f"{_term(a, var)} = {fmt(c)} {verb} {fmt(abs(b))}")
        cur_rhs = c - b
        steps.append(f"{_term(a, var)} = {fmt(cur_rhs)}")
    if a != 1:
        steps.append(f"{var} = {fmt(cur_rhs)} / {fmt(a)}")
        steps.append(f"{var} = {fmt(sols[0])}")
    elif b == 0:
        steps.append(f"{var} = {fmt(sols[0])}")
    return steps


def linear_signals(lhs, rhs, var, step_eqs: list[tuple[str, sp.Expr, sp.Expr]]) -> list[str]:
    """Known slips for a*x + b = c, found by exact algebraic comparison to the learner's steps."""
    parts = _linear_parts(lhs, rhs, var)
    if parts is None:
        return []
    a, b, c = parts
    out: list[str] = []
    for text, L, R in step_eqs:
        try:
            if b != 0 and _same(L, a * var) and _same(R, c + b) and b > 0:
                out.append(f'"{text}": {fmt(b)} was added to the right side; the inverse of +{fmt(b)} is subtracting {fmt(b)} from both sides.')
            elif b != 0 and _same(L, a * var) and _same(R, c + b) and b < 0:
                out.append(f'"{text}": {fmt(abs(b))} was subtracted on the right side; the inverse of -{fmt(abs(b))} is adding it to both sides.')
            elif b != 0 and _same(L, a * var) and _same(R, b - c):
                out.append(f'"{text}": the constant was moved with reversed subtraction order ({fmt(b)} - {fmt(c)} instead of {fmt(c)} - {fmt(b)}).')
            elif a != 1 and b != 0 and _same(L, var) and _same(R, c - b):
                out.append(f'"{text}": the constant was removed but the result was not divided by the coefficient {fmt(a)}.')
            elif a != 1 and b != 0 and _same(L, var) and _same(R, c / a - b):
                out.append(f'"{text}": only the right-hand side was divided by {fmt(a)}, and the constant was then subtracted afterwards.')
            elif a != 1 and _same(L, var) and _same(R, (c - b) * a):
                out.append(f'"{text}": the result was multiplied by the coefficient {fmt(a)} instead of divided.')
        except Exception:
            continue
    return out


# ------------------------------------------------------------------ analysis --
def _split_lines(answer: str) -> list[str]:
    # Newlines, semicolons, arrows, and commas that separate statements ("2x=8, x=4"; not "1,000").
    parts = re.split(r"[\n;]+|\s*(?:->|=>|→|⇒)\s*|,\s+|,(?=[a-z])", answer)
    return [p.strip() for p in parts if p and p.strip()]


def _bare_number(text: str) -> Optional[sp.Expr]:
    try:
        v = parse_math(text)
    except MathParseError:
        return None
    return v if not v.free_symbols else None


def _final_value(line: str, var: sp.Symbol) -> Optional[sp.Expr]:
    """Value from 'x = 7' / '7' (None if the line is not a final answer)."""
    if "=" in line:
        try:
            L, R = parse_equation(line)
        except MathParseError:
            return None
        if L == var and not R.free_symbols:
            return sp.nsimplify(R)
        if R == var and not L.free_symbols:
            return sp.nsimplify(L)
        return None
    return _bare_number(line)


def analyze_work(question: str, answer: str) -> WorkAnalysis:
    """Check each submitted line and the final answer against the question."""
    math_text = extract_math(question)
    result = WorkAnalysis(math_text=math_text)
    lines = _split_lines(answer)
    try:
        if "=" in math_text:
            return _analyze_equation(result, math_text, lines)
        return _analyze_expression(result, math_text, lines)
    except MathParseError as exc:
        result.problem_type = "unknown"
        result.notes.append(f"Automatic verification unavailable: {exc}")
        result.steps = [StepCheck(text=l, parsed=False) for l in lines]
        return result


def _analyze_equation(result: WorkAnalysis, math_text: str, lines: list[str]) -> WorkAnalysis:
    lhs, rhs = parse_equation(math_text)
    var, sols = _solve(lhs, rhs)
    if not sols:
        raise MathParseError("The equation has no real solution to verify against.")
    result.problem_type, result.verifiable = "equation", True
    result.correct_answer = ", ".join(f"{var} = {fmt(s)}" for s in sols)
    step_eqs: list[tuple[str, sp.Expr, sp.Expr]] = []
    final: Optional[sp.Expr] = None
    for i, line in enumerate(lines):
        if "=" not in line:
            val = _bare_number(line)
            if val is None:
                result.steps.append(StepCheck(text=line, parsed=False, note="Not a recognizable math step."))
                continue
            ok = any(_same(val, s) for s in sols)
            result.steps.append(StepCheck(text=line, parsed=True, consistent=ok,
                                          note="Bare value matches the solution." if ok else "Bare value is not the solution."))
            final = val
            if not ok and result.first_inconsistent_step is None:
                result.first_inconsistent_step = i
            continue
        try:
            L, R = parse_equation(line)
        except MathParseError as exc:
            result.steps.append(StepCheck(text=line, parsed=False, note=str(exc)))
            continue
        free = (L - R).free_symbols
        if not free:
            ok = _same(L, R)
            note = "Arithmetic statement is true." if ok else "Arithmetic statement is false."
        elif free != {var}:
            result.steps.append(StepCheck(text=line, parsed=True, consistent=None,
                                          note="Uses a different variable; cannot verify."))
            continue
        else:
            try:
                _, line_sols = _solve(L, R)
            except MathParseError:
                line_sols = []
            ok = bool(line_sols) and len(line_sols) == len(sols) and all(
                any(_same(a, b) for b in sols) for a in line_sols)
            note = ("Has the same solution as the original equation." if ok
                    else "Does not have the same solution as the original equation.")
            step_eqs.append((line, L, R))
        result.steps.append(StepCheck(text=line, parsed=True, consistent=ok, note=note))
        if not ok and result.first_inconsistent_step is None:
            result.first_inconsistent_step = i
        fv = _final_value(line, var)
        if fv is not None:
            final = fv
    result.signals = linear_signals(lhs, rhs, var, step_eqs)
    if final is None:
        result.notes.append("No final answer of the form x = number was found.")
    else:
        result.final_answer_text = fmt(final)
        result.final_answer_correct = any(_same(final, s) for s in sols)
    return result


def _is_simplified(final: sp.Expr, original: sp.Expr) -> bool:
    if not original.free_symbols:
        return final.is_Atom
    expanded = sp.expand(original)
    return sp.count_ops(final) <= sp.count_ops(expanded)


def _analyze_expression(result: WorkAnalysis, math_text: str, lines: list[str]) -> WorkAnalysis:
    expr = parse_math(math_text)
    result.problem_type, result.verifiable = "expression", True
    target = sp.expand(expr) if expr.free_symbols else sp.nsimplify(sp.simplify(expr))
    result.correct_answer = fmt(target)
    final: Optional[sp.Expr] = None
    for i, line in enumerate(lines):
        text = line.lstrip("= ").strip()
        try:
            val = parse_math(text)
        except MathParseError as exc:
            result.steps.append(StepCheck(text=line, parsed=False, note=str(exc)))
            continue
        ok = _same(val, expr)
        result.steps.append(StepCheck(
            text=line, parsed=True, consistent=ok,
            note="Equivalent to the original expression." if ok else "Not equivalent to the original expression."))
        if not ok and result.first_inconsistent_step is None:
            result.first_inconsistent_step = i
        final = val
    if final is None:
        result.notes.append("No expression was found to check.")
    else:
        result.final_answer_text = fmt(final)
        equivalent = _same(final, expr)
        simplified = _is_simplified(final, expr)
        result.final_answer_correct = equivalent and simplified
        if equivalent and not simplified:
            result.notes.append("The final expression is equivalent but not fully simplified.")
    return result


def evaluate_answer(question: str, answer: str) -> tuple[Optional[bool], WorkAnalysis]:
    """Judge a learner's final answer for a practice/transfer question."""
    analysis = analyze_work(question, answer)
    return analysis.final_answer_correct, analysis


def verify_practice_question(question: str) -> Optional[str]:
    """Return the verified expected answer, or None if the question cannot be machine-verified."""
    analysis = analyze_work(question, "")
    if not analysis.verifiable or not analysis.correct_answer:
        return None
    if analysis.problem_type == "equation" and "," in analysis.correct_answer:
        return None  # require a single unambiguous solution
    return analysis.correct_answer
