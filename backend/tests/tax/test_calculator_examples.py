"""The calculator gives the worked examples' figures exactly (feature 010, tasks T009, T015;
SC-001).

Every expected figure in calculator_examples.yaml is compared with the calculator's result; a
figure an example doesn't list takes the default its header states (no refusal, no surcharge,
dividend or profit tax, no bonus impact, no filer comparison). Amounts compare as Decimals, so
"4344000" equals 4344000.00.
"""

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.tax.calculator import CalculatorInputs, CalculatorResult, calculate_simple, percent_text
from app.tax.rates import rates_for

EXAMPLES_FILE = Path(__file__).with_name("calculator_examples.yaml")
DATA = yaml.safe_load(EXAMPLES_FILE.read_text(encoding="utf-8"))
EXAMPLES: list[dict[str, Any]] = DATA["examples"]
DEFAULTS: dict[str, Any] = {
    "blocked_reason": None,
    "surcharge": "0",
    "dividend_tax": "0",
    "profit_tax": "0",
    "bonus_impact": None,
    "filer_comparison": [],
}
MONEY_INPUTS = ("salary_monthly", "bonus", "rent_monthly", "dividends", "bank_profit")


def inputs_of(example: dict[str, Any]) -> CalculatorInputs:
    """The example's inputs; anything not listed is zero, and ATL is true unless listed."""
    given = example["inputs"]
    return CalculatorInputs(
        tax_year=DATA["tax_year"],
        atl=given.get("atl", True),
        **{name: Decimal(str(given.get(name, "0"))) for name in MONEY_INPUTS},
    )


def as_number(value: Any) -> Decimal | None:
    """A figure as a Decimal (None stays None)."""
    return None if value is None else Decimal(str(value))


def figures(result: CalculatorResult) -> dict[str, Any]:
    """The result in the examples' terms."""
    monthly = None
    if result.monthly is not None:
        monthly = {
            "salary_tax": result.monthly.salary_tax,
            "take_home": result.monthly.take_home,
        }
    return {
        "blocked_reason": result.blocked_reason,
        "taxable_income": result.taxable_income,
        "salary_share": result.salary_share,
        "table": result.table,
        "slab_tax": result.slab_tax,
        "surcharge": result.surcharge,
        "dividend_tax": result.dividend_tax,
        "profit_tax": result.profit_tax,
        "total_tax": result.total_tax,
        "effective_rate": result.effective_rate,
        "monthly": monthly,
        "bonus_impact": result.bonus_impact,
        "filer_comparison": [
            {
                "source": line.source,
                "your_rate": percent_text(line.your_rate),
                "other_rate": percent_text(line.other_rate),
                "your_deduction": line.your_deduction,
                "other_deduction": line.other_deduction,
                "difference": line.difference,
            }
            for line in result.filer_comparison
        ],
    }


def expected_of(example: dict[str, Any]) -> dict[str, Any]:
    """The example's expected figures, with the header's defaults filled in."""
    expected = dict(example["expected"])
    if "blocked_reason" in expected:
        return expected
    return {**DEFAULTS, **expected}


def same(actual: Any, expected: Any) -> bool:
    """Equal as Decimals where the expected value is a number, else exactly."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            same(actual.get(key), value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(same(a, e) for a, e in zip(actual, expected, strict=True))
        )
    if isinstance(actual, Decimal):
        return isinstance(expected, str) and actual == Decimal(expected)
    return bool(actual == expected)


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["id"] for e in EXAMPLES])
def test_the_calculator_gives_the_worked_figures(example: dict[str, Any]) -> None:
    """Fails if any figure differs from the signed worked example, to the rupee."""
    actual = figures(calculate_simple(inputs_of(example), rates_for(DATA["tax_year"])))

    for name, expected in expected_of(example).items():
        assert same(actual[name], expected), f"{name}: {actual[name]!r} != {expected!r}"
