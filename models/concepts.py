"""Concept graph for the mathematics subject (extend for new subjects)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:
    id: str
    name: str
    prerequisites: tuple[str, ...] = ()


_LIST = [
    Concept("sign_rules", "Sign rules"),
    Concept("inverse_operations", "Inverse operations"),
    Concept("equation_balancing", "Equation balancing"),
    Concept("combining_like_terms", "Combining like terms"),
    Concept("distributive_property", "Distributive property"),
    Concept("one_step_equations", "One-step equations", ("inverse_operations", "equation_balancing")),
    Concept("two_step_equations", "Two-step equations", ("one_step_equations", "sign_rules")),
    Concept("simplifying_expressions", "Simplifying expressions",
            ("combining_like_terms", "distributive_property")),
    Concept("multi_step_equations", "Multi-step equations",
            ("two_step_equations", "simplifying_expressions")),
]
CONCEPTS: dict[str, Concept] = {c.id: c for c in _LIST}

MISCONCEPTION_CATEGORIES = [
    "inverse_operation_error",
    "sign_error",
    "distribution_error",
    "combining_terms_error",
    "balancing_error",
    "arithmetic_slip",
    "order_of_operations",
    "other",
]

# Subjects: only mathematics is fully supported; the registry lets others be added.
SUBJECTS = {
    "Mathematics (Algebra)": {
        "supported": True,
        "topics": [
            "One-step equations",
            "Two-step equations",
            "Multi-step equations",
            "Simplifying expressions",
            "Distributive property",
            "Sign errors",
        ],
    },
}
PLANNED_SUBJECTS = ["Physics", "Chemistry", "Programming"]


def concept_name(concept_id: str) -> str:
    c = CONCEPTS.get(concept_id)
    return c.name if c else concept_id.replace("_", " ").capitalize()
