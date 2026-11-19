"""Refusing rather than guessing (feature 004, task T021; research R4, FR-012, FR-013)."""

from decimal import Decimal
from typing import Any

import pytest
from test_sign_off import EXAMPLES
from test_worked_examples import FIGURES, inputs_from

from app.tax.engine import TaxInputs, TaxResult, calculate
from app.tax.rates import rates_for

BLOCKED = [e for e in EXAMPLES if e["expected"]["blocked_reason"] is not None]


@pytest.mark.parametrize("example", BLOCKED, ids=[e["id"] for e in BLOCKED])
def test_blocked_example_gives_its_reason_and_no_figures(example: dict[str, Any]) -> None:
    """Fails if a blocked case is calculated anyway, or the reason differs from the example."""
    result = calculate(inputs_from(example), rates_for("2025-26"))

    assert result.blocked_reason == example["expected"]["blocked_reason"]
    assert all(getattr(result, name) is None for name in FIGURES)
    assert not result.steps


def test_there_is_a_blocked_example_for_every_reason() -> None:
    """Fails if the blocked cases stop covering all three reasons in the contract (provisional
    rule 3's two were removed on 2026-11-17: s.8(1)(a))."""
    assert len({e["expected"]["blocked_reason"] for e in BLOCKED}) == 3


@pytest.mark.parametrize("salary", ["1200000", "2423450", "9900000", "10000000", "12000000"])
@pytest.mark.parametrize("profit", ["400000", "1000000", "5000000"])
def test_bank_profit_never_changes_the_salary_side(salary: str, profit: str) -> None:
    """Fails if bank profit moves the salary tax, the surcharge or the table: it is a final tax
    outside taxable income (s.8(1)(a); amended 2026-11-17, provisional rule 3 removed)."""

    def tax(gross_profit: str) -> TaxResult:
        inputs = TaxInputs(
            tax_year="2025-26",
            atl=True,
            taxable_salary=Decimal(salary),
            tax_deducted=Decimal(0),
            gross_profit=Decimal(gross_profit),
            tax_withheld=Decimal(0),
            has_salary_certificate=True,
        )
        return calculate(inputs, rates_for("2025-26"))

    without, with_profit = tax("0"), tax(profit)

    assert with_profit.blocked_reason is None
    assert (with_profit.salary_tax, with_profit.surcharge) == (
        without.salary_tax,
        without.surcharge,
    )
