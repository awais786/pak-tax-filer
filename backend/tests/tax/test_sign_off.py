"""The worked examples are complete and signed off by a human (feature 004, task T004; FR-015).

Engine code is tested against these examples, so they must be checked by hand against the
Ordinance first (task T003). test_every_example_is_signed_off fails until that is done.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

EXAMPLES_FILE = Path(__file__).with_name("worked_examples.yaml")
FIGURES = (
    "salary_tax",
    "surcharge",
    "profit_tax",
    "salary_balance",
    "profit_balance",
    "non_atl_extra_withheld",
)
# specs/004-tax-engine/contracts/tax-api.md
BLOCKED_REASONS = {
    "needs_atl_answer",
    "no_confirmed_salary_certificate",
    "profit_over_limit",
    "salary_share_ambiguous",
    "surcharge_ambiguous",
}


def load_examples() -> list[dict[str, Any]]:
    """Every worked example in the file."""
    data = yaml.safe_load(EXAMPLES_FILE.read_text(encoding="utf-8"))
    examples: list[dict[str, Any]] = data["examples"]
    return examples


EXAMPLES = load_examples()


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["id"] for e in EXAMPLES])
def test_every_example_is_signed_off(example: dict[str, Any]) -> None:
    """Fails until a person has checked this example by hand and signed it (task T003)."""
    assert str(example.get("signed_off_by") or "").strip(), "signed_off_by is empty"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(example.get("signed_off_date") or "")), (
        "signed_off_date must be YYYY-MM-DD"
    )


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["id"] for e in EXAMPLES])
def test_every_example_is_complete(example: dict[str, Any]) -> None:
    """Fails if an example lacks inputs, its working, or any expected figure."""
    assert example["working"], "the hand working is missing"
    assert set(example["inputs"]) == {"atl", "salary_certificates", "bank_certificates"}
    assert set(example["expected"]) == {"blocked_reason", *FIGURES}
    blocked = example["expected"]["blocked_reason"]
    for figure in FIGURES:
        value = example["expected"][figure]
        if blocked is not None:
            assert value is None, f"a blocked example has no {figure}"
        elif figure != "non_atl_extra_withheld" or example["inputs"]["atl"] is False:
            assert re.fullmatch(r"-?\d+", str(value)), f"{figure} must be whole rupees"


def test_every_blocked_reason_has_an_example() -> None:
    """Fails if a blocked_reason in the contract has no worked example (FR-015)."""
    found = {e["expected"]["blocked_reason"] for e in EXAMPLES}

    assert BLOCKED_REASONS <= found
    assert found - {None} <= BLOCKED_REASONS


def test_ids_are_unique() -> None:
    """Fails if two examples share an id (one test would hide the other)."""
    ids = [e["id"] for e in EXAMPLES]

    assert len(ids) == len(set(ids))


# ---- Feature 010: the calculator's worked examples (task T004; FR-012) -------------------------

CALCULATOR_FILE = Path(__file__).with_name("calculator_examples.yaml")
CALCULATOR_INPUTS = {"atl", "salary_monthly", "bonus", "rent_monthly", "dividends", "bank_profit"}
CALCULATOR_FIGURES = {
    "taxable_income",
    "salary_share",
    "table",
    "slab_tax",
    "surcharge",
    "dividend_tax",
    "profit_tax",
    "total_tax",
    "effective_rate",
    "monthly",
    "bonus_impact",
    "filer_comparison",
}
# specs/010-income-tax-engine/contracts/calculator-api.md
CALCULATOR_BLOCKED = {"no_income", "profit_over_limit"}


def load_calculator_examples() -> list[dict[str, Any]]:
    """Every calculator example in the file."""
    data = yaml.safe_load(CALCULATOR_FILE.read_text(encoding="utf-8"))
    examples: list[dict[str, Any]] = data["examples"]
    return examples


CALCULATOR_EXAMPLES = load_calculator_examples()
CALCULATOR_IDS = [e["id"] for e in CALCULATOR_EXAMPLES]


@pytest.mark.parametrize("example", CALCULATOR_EXAMPLES, ids=CALCULATOR_IDS)
def test_every_calculator_example_is_signed_off(example: dict[str, Any]) -> None:
    """Fails until the author has checked this example by hand and signed it (010, T003)."""
    assert str(example.get("signed_off_by") or "").strip(), "signed_off_by is empty"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(example.get("signed_off_date") or "")), (
        "signed_off_date must be YYYY-MM-DD"
    )


@pytest.mark.parametrize("example", CALCULATOR_EXAMPLES, ids=CALCULATOR_IDS)
def test_every_calculator_example_is_complete(example: dict[str, Any]) -> None:
    """Fails if an example lacks its working, names an unknown input or figure, or gives a
    tax figure that isn't whole rupees. A blocked example states only its reason."""
    assert example["working"], "the hand working is missing"
    assert set(example["inputs"]) <= CALCULATOR_INPUTS
    expected = example["expected"]
    if "blocked_reason" in expected:
        assert expected == {"blocked_reason": expected["blocked_reason"]}
        return
    assert set(expected) <= CALCULATOR_FIGURES
    for figure in ("slab_tax", "surcharge", "dividend_tax", "profit_tax", "total_tax"):
        if figure in expected:
            assert re.fullmatch(r"\d+", str(expected[figure])), f"{figure} must be whole rupees"


def test_every_calculator_blocked_reason_has_an_example() -> None:
    """Fails if a blocked_reason in the contract has no worked example, or an example uses one
    the contract doesn't list."""
    found = {e["expected"].get("blocked_reason") for e in CALCULATOR_EXAMPLES} - {None}

    assert found == CALCULATOR_BLOCKED


def test_calculator_ids_are_unique() -> None:
    """Fails if two calculator examples share an id."""
    assert len(CALCULATOR_IDS) == len(set(CALCULATOR_IDS))
