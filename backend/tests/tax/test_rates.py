"""The rates module: every rule sourced, the salary table self-consistent (feature 004, T006).

Research R10: each band's fixed amount must equal the tax at the top of the band below. This
would have caught FBR Circular 01 of 2025-26's two wrong amounts (345,000 and 615,000).
"""

import re
from dataclasses import fields, replace
from datetime import date
from decimal import Decimal

import pytest

from app.tax.engine import TaxInputs, band_for, calculate
from app.tax.rates import RATES, rates_for
from app.tax.rates.model import Band, Rule, Source, TaxYearRates

YEARS = sorted(RATES)


def sources_of(rates: TaxYearRates) -> list[tuple[str, Source]]:
    """Every source in a year's rates, labelled by the rule it belongs to."""
    found: list[tuple[str, Source]] = []
    for field in fields(rates):
        value = getattr(rates, field.name)
        if isinstance(value, Source):
            found.append((field.name, value))
        elif isinstance(value, Rule):
            found.append((field.name, value.source))
        elif isinstance(value, tuple):
            found += [(f"{field.name}[{i}]", band.source) for i, band in enumerate(value)]
    return found


def test_tax_year_2025_26_is_registered() -> None:
    """Fails if the profile's only supported year has no rates (feature 002, research R13)."""
    assert rates_for("2025-26").tax_year == "2025-26"


def test_an_unknown_year_has_no_rates() -> None:
    """Fails if a year without FBR rates is answered with another year's."""
    with pytest.raises(KeyError):
        rates_for("2024-25")


@pytest.mark.parametrize("tax_year", YEARS)
def test_every_rule_names_its_source(tax_year: str) -> None:
    """Fails if any rule lacks its FBR document, location or Finance Act (Principle II)."""
    found = sources_of(RATES[tax_year])

    assert len(found) >= 6
    for rule, source in found:
        assert source.document.strip(), rule
        assert source.location.strip(), rule
        assert source.finance_act.strip(), rule


# Both tables of First Schedule, Part I, Division I: clause (2), salaried (004), and clause (1),
# everyone else (010, research R2).
TABLES = ("salary_bands", "non_salaried_bands")


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("tax_year", YEARS)
def test_bands_join_up_from_zero_with_an_open_top(tax_year: str, table: str) -> None:
    """Fails if a band is missing, overlaps another, or the table doesn't cover every income."""
    bands = getattr(RATES[tax_year], table)

    assert bands[0].lower == 0
    for below, above in zip(bands, bands[1:], strict=False):
        assert below.upper == above.lower
    assert all(band.upper is not None for band in bands[:-1])
    assert bands[-1].upper is None


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("tax_year", YEARS)
def test_each_fixed_amount_is_the_tax_at_the_top_of_the_band_below(
    tax_year: str, table: str
) -> None:
    """Fails on a typo in a fixed amount, like the circular's 345,000 for 346,000 (R10, FR-009;
    010's FR-006 for the non-salaried table)."""
    bands = getattr(RATES[tax_year], table)

    assert bands[0].fixed == 0
    for below, above in zip(bands, bands[1:], strict=False):
        assert below.upper is not None
        assert above.fixed == below.fixed + below.rate * (below.upper - below.lower)


def test_the_continuity_check_catches_the_circulars_typo() -> None:
    """Fails if the check above couldn't tell 345,000 from 346,000 (it must, or it's useless)."""
    bands = list(rates_for("2025-26").salary_bands)
    row5 = bands[4]
    bands[4] = Band(row5.lower, row5.upper, Decimal("345000"), row5.rate, row5.source)

    below, above = bands[3], bands[4]
    assert below.upper is not None
    assert above.fixed != below.fixed + below.rate * (below.upper - below.lower)


@pytest.mark.parametrize("tax_year", YEARS)
def test_all_amounts_are_exact_decimals(tax_year: str) -> None:
    """Fails if any rate or limit is a float (Principle I: exact decimal arithmetic)."""
    rates = RATES[tax_year]
    numbers = [
        value
        for table in TABLES
        for band in getattr(rates, table)
        for value in (band.fixed, band.rate)
    ]
    numbers += [
        getattr(rates, f.name).value
        for f in fields(rates)
        if isinstance(getattr(rates, f.name), Rule)
    ]

    assert all(isinstance(number, Decimal) for number in numbers)


def test_a_new_tax_year_is_data_only() -> None:
    """Fails if a second year's rates can't change the result without touching engine.py
    (FR-008). The made-up year lives in a test-only registry; the real one is unchanged."""
    real = rates_for("2025-26")
    flat_ten_percent = Band(
        Decimal(0), None, Decimal(0), Decimal("0.10"), real.salary_bands[0].source
    )
    registry = {
        **RATES,
        "2099-00": replace(real, tax_year="2099-00", salary_bands=(flat_ten_percent,)),
    }
    inputs = TaxInputs(
        "2099-00", True, Decimal(1800000), Decimal(60000), Decimal(0), Decimal(0), True
    )

    made_up = calculate(inputs, registry["2099-00"])
    actual = calculate(replace(inputs, tax_year="2025-26"), registry["2025-26"])

    assert made_up.salary_tax == Decimal(180000)
    assert actual.salary_tax == Decimal(72000)
    assert "2099-00" not in RATES


# ---- Feature 010: the calculator's TY2026 rules (task T005; research R1-R8) --------------------


def test_ty2026_non_salaried_table_is_the_ordinance_s() -> None:
    """Fails if a row of clause (1) differs from the Ordinance (amended up to 31.07.2025,
    p. 490): 0 / 15% / 90,000 + 20% / 170,000 + 30% / 650,000 + 40% / 1,610,000 + 45%."""
    rows = [
        (band.lower, band.upper, band.fixed, band.rate)
        for band in rates_for("2025-26").non_salaried_bands
    ]

    assert rows == [
        (Decimal(0), Decimal(600000), Decimal(0), Decimal(0)),
        (Decimal(600000), Decimal(1200000), Decimal(0), Decimal("0.15")),
        (Decimal(1200000), Decimal(1600000), Decimal(90000), Decimal("0.20")),
        (Decimal(1600000), Decimal(3200000), Decimal(170000), Decimal("0.30")),
        (Decimal(3200000), Decimal(5600000), Decimal(650000), Decimal("0.40")),
        (Decimal(5600000), None, Decimal(1610000), Decimal("0.45")),
    ]


def test_ty2026_calculator_rules() -> None:
    """Fails if a calculator rule differs from research.md: surcharge 10% without salary (s.4AB),
    repairs allowance one-fifth (s.15A(1)(a)), dividends 15% (Division III(b)), deductions 15%
    and 20% (Part III Divisions I(b) and IA(a)), +100% not on the ATL (Tenth Schedule rule 1)."""
    rates = rates_for("2025-26")

    assert rates.surcharge_rate_other.value == Decimal("0.10")
    assert rates.repairs_allowance.value == Decimal("0.20")
    assert rates.dividend_rate.value == Decimal("0.15")
    assert rates.dividend_deduction_rate.value == Decimal("0.15")
    assert rates.profit_deduction_rate.value == Decimal("0.20")
    assert rates.non_atl_increase.value == Decimal("1.00")


def test_ty2026_rules_take_effect_on_1_july_2025() -> None:
    """Fails if TY2026 doesn't record the date its rules apply from (constitution 1.3.0,
    Principle II; research R8)."""
    assert rates_for("2025-26").effective_from == date(2025, 7, 1)


@pytest.mark.parametrize("tax_year", YEARS)
def test_every_location_gives_printed_and_pdf_pages(tax_year: str) -> None:
    """Fails if a rule's location doesn't name both page numbers, so a reader can find it in the
    pinned FBR file (research R8)."""
    for rule, source in sources_of(RATES[tax_year]):
        assert re.search(r"p\. \d+", source.location), rule
        assert re.search(r"PDF p\. \d+", source.location), rule


@pytest.mark.parametrize(
    ("income", "row"),
    [("600000", 0), ("600000.01", 1), ("1600000", 2), ("5600000", 4), ("5600001", 5)],
)
def test_band_for_uses_does_not_exceed_on_either_table(income: str, row: int) -> None:
    """Fails if the row lookup isn't the same "does not exceed" rule for the non-salaried table
    as for the salaried one (010, task T007)."""
    bands = rates_for("2025-26").non_salaried_bands

    assert band_for(bands, Decimal(income)) is bands[row]
