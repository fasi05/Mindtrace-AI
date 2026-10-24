import pytest
from services.math_verifier import (MathParseError, analyze_work, canonical_steps, evaluate_answer, extract_math,
                                    parse_math, verify_practice_question)

Q = 'Solve "2x + 3 = 11"'


def test_required_scenario_detects_slip():
    a = analyze_work(Q, "2x = 14\nx = 7")
    assert a.verifiable and a.correct_answer == "x = 4"
    assert a.final_answer_correct is False
    assert a.first_inconsistent_step == 0
    assert any("added to the right side" in s for s in a.signals)


def test_correct_work_passes():
    a = analyze_work(Q, "2x = 8\nx = 4")
    assert a.final_answer_correct is True and a.first_inconsistent_step is None


def test_canonical_solution_matches_spec():
    assert canonical_steps(Q) == ["2x + 3 = 11", "2x = 11 - 3", "2x = 8", "x = 8 / 2", "x = 4"]


def test_transfer_question():
    assert verify_practice_question("Solve 3x + 5 = 20") == "x = 5"
    assert evaluate_answer("Solve 3x + 5 = 20", "x = 5")[0] is True
    assert evaluate_answer("Solve 3x + 5 = 20", "6")[0] is False
    assert evaluate_answer("Solve 3x + 5 = 20", "5")[0] is True


@pytest.mark.parametrize("q,expected", [("Solve for x: 2x+3=11", "2x+3=11"), ('Solve "x - 4 = 1"', "x - 4 = 1"),
                                        ("Simplify 3(x+2) - x", "3(x+2) - x")])
def test_extract_math(q, expected):
    assert extract_math(q) == expected


def test_negative_and_fraction_solutions():
    assert verify_practice_question("Solve 3x - 5 = 20") == "x = 25/3"
    assert verify_practice_question("Solve -2x + 1 = 9") == "x = -4"


def test_sign_error_signal():
    a = analyze_work("Solve x + 4 = 9", "x = 4 - 9\nx = -5")
    assert a.final_answer_correct is False


def test_expression_equivalence_and_distribution():
    assert analyze_work("Simplify 3(x+2) - x", "2x + 6").final_answer_correct is True
    wrong = analyze_work("Simplify 3(x+2) - x", "3x + 2 - x")
    assert wrong.final_answer_correct is False and wrong.first_inconsistent_step == 0


def test_unverifiable_is_flagged_not_guessed():
    a = analyze_work("Explain photosynthesis", "plants eat light")
    assert a.verifiable is False and a.final_answer_correct is None


@pytest.mark.parametrize("bad", ["__import__('os').system('x')", "x = open('f')", "2x + 3 = 11; import os", "9**9**9", "sin(x)"])
def test_unsafe_input_never_evaluated(bad):
    with pytest.raises(MathParseError):
        parse_math(bad)


def test_no_final_answer_reported():
    a = analyze_work(Q, "2x = 8")
    assert a.final_answer_correct is None and a.first_inconsistent_step is None
