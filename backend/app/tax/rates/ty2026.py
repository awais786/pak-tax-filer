"""Tax year 2026 (1 July 2025 to 30 June 2026, "2025-26") rates (feature 004, task T007).

Every value is from the Income Tax Ordinance, 2001 as amended up to 31.07.2025, FBR's own text:
https://download1.fbr.gov.pk/Docs/2025881983148210Income-Tax-Ordinance,-2001-Amended-upto-31.07.2025.pdf
Locations give "p." (the printed page) and "PDF p." (the page in the file pinned by SHA-256 in
app/rag/sources.yaml). Feature 004 cited "PDF page" numbers one above the printed page; feature 010
corrected them to this scheme on 2026-11-14 (research R8; figures unchanged). The rules were checked
by Saifullah Khan on 2026-11-09 (004) and accepted provisionally on 2026-11-14 (010); all are to be
revised when a tax practitioner reviews the app.
Note: FBR Circular 01 of 2025-26 prints two wrong fixed amounts (345,000 and 615,000); the
Ordinance's 346,000 and 616,000 are the only values consistent with the bands, and the statute
prevails. Never use the superseded tables printed in the Ordinance's footnotes.
"""

from datetime import date
from decimal import Decimal

from app.tax.rates.model import Band, Rule, Source, TaxYearRates

ORDINANCE = "Income Tax Ordinance, 2001 (amended up to 31.07.2025)"
TABLE = "First Schedule, Part I, Division I, clause (2)"
# Feature 010: the table for everyone else (research R2). Its pages, and every page cited for
# feature 010's rules, are "p." as printed and "PDF p." as the page in the file pinned by SHA-256
# in app/rag/sources.yaml (research R8).
OTHER_TABLE = "First Schedule, Part I, Division I, clause (1)"


def _row(number: int) -> Source:
    return Source(
        document=ORDINANCE,
        location=f"{TABLE}, row {number} (p. 492, PDF p. 511)",
        finance_act="Finance Act 2025 (table substituted)",
    )


def _other_row(number: int) -> Source:
    return Source(
        document=ORDINANCE,
        location=f"{OTHER_TABLE}, row {number} (p. 490, PDF p. 509)",
        finance_act="Finance Act 2024 (table substituted); unchanged by Finance Act 2025",
    )


RATES = TaxYearRates(
    tax_year="2025-26",
    salary_bands=(
        Band(Decimal("0"), Decimal("600000"), Decimal("0"), Decimal("0"), _row(1)),
        Band(Decimal("600000"), Decimal("1200000"), Decimal("0"), Decimal("0.01"), _row(2)),
        Band(Decimal("1200000"), Decimal("2200000"), Decimal("6000"), Decimal("0.11"), _row(3)),
        Band(Decimal("2200000"), Decimal("3200000"), Decimal("116000"), Decimal("0.23"), _row(4)),
        Band(Decimal("3200000"), Decimal("4100000"), Decimal("346000"), Decimal("0.30"), _row(5)),
        Band(Decimal("4100000"), None, Decimal("616000"), Decimal("0.35"), _row(6)),
    ),
    salary_share_threshold=Rule(
        Decimal("0.75"),
        Source(
            ORDINANCE,
            f"{TABLE}: the salaried table applies where salary exceeds 75% of taxable income "
            "(p. 491, PDF p. 510)",
            "Finance Act 2025",
        ),
    ),
    surcharge_rate=Rule(
        Decimal("0.09"),
        Source(
            ORDINANCE,
            "Section 4AB, proviso: nine percent of the Division I tax for an individual with "
            "income under the head Salary (p. 33, PDF p. 52)",
            "Finance Act 2025 (proviso added; section 4AB inserted by Finance Act 2024)",
        ),
    ),
    surcharge_threshold=Rule(
        Decimal("10000000"),
        Source(
            ORDINANCE,
            "Section 4AB: where the taxable income exceeds rupees ten million (p. 33, PDF p. 52)",
            "Finance Act 2024 (section 4AB inserted)",
        ),
    ),
    profit_rate=Rule(
        Decimal("0.20"),
        Source(
            ORDINANCE,
            "Section 7B(1)-(2) on the gross profit on debt (p. 39-40, PDF p. 58-59), at First "
            "Schedule, Part I, Division IIIA(a): 20% of profit paid by a banking company "
            "(p. 500, PDF p. 519)",
            "Finance Act 2025 (Division IIIA substituted)",
        ),
    ),
    profit_limit=Rule(
        Decimal("5000000"),
        Source(
            ORDINANCE,
            "Section 7B(3)(b): section 7B does not apply to profit on debt exceeding five million "
            "rupees (p. 40, PDF p. 59)",
            'Finance Act 2019 (sub-section (3)); "five" substituted by Finance Act 2021',
        ),
    ),
    rounding=Source(
        ORDINANCE,
        "Section 219: tax or refund to the nearest rupee; fractions of fifty paisa or more count "
        "as one rupee (p. 436, PDF p. 455)",
        "Income Tax Ordinance, 2001 (original)",
    ),
    # ---- Feature 010: the simple calculator (specs/010-income-tax-engine/research.md) ----
    # Tax year 2026 is 1 July 2025 to 30 June 2026; these rules apply from its first day (R8).
    effective_from=date(2025, 7, 1),
    non_salaried_bands=(
        Band(Decimal("0"), Decimal("600000"), Decimal("0"), Decimal("0"), _other_row(1)),
        Band(Decimal("600000"), Decimal("1200000"), Decimal("0"), Decimal("0.15"), _other_row(2)),
        Band(
            Decimal("1200000"), Decimal("1600000"), Decimal("90000"), Decimal("0.20"), _other_row(3)
        ),
        Band(
            Decimal("1600000"),
            Decimal("3200000"),
            Decimal("170000"),
            Decimal("0.30"),
            _other_row(4),
        ),
        Band(
            Decimal("3200000"),
            Decimal("5600000"),
            Decimal("650000"),
            Decimal("0.40"),
            _other_row(5),
        ),
        Band(Decimal("5600000"), None, Decimal("1610000"), Decimal("0.45"), _other_row(6)),
    ),
    surcharge_rate_other=Rule(
        Decimal("0.10"),
        Source(
            ORDINANCE,
            "Section 4AB: ten percent of the Division I tax where the taxable income exceeds "
            "rupees ten million, for an individual without income under the head Salary "
            "(p. 33, PDF p. 52)",
            "Finance Act 2024 (section 4AB inserted)",
        ),
    ),
    repairs_allowance=Rule(
        Decimal("0.20"),
        Source(
            ORDINANCE,
            "Section 15A(1)(a): an allowance for repairs equal to one-fifth of the rent "
            "(p. 57, PDF p. 76); rent is income under the head Income from Property, section "
            "15(1) (p. 56, PDF p. 75), taxed with other taxable income since section 15(6) and "
            "Part I, Division VIA were omitted (p. 57 and p. 503, PDF p. 76 and 522)",
            "Finance Act 2013 (section 15A inserted); Finance Act 2021 (applied to every "
            "person; section 15(6) and Division VIA omitted)",
        ),
    ),
    dividend_rate=Rule(
        Decimal("0.15"),
        Source(
            ORDINANCE,
            "Section 5(1)-(2) on the gross dividend (p. 35, PDF p. 54), at First Schedule, "
            "Part I, Division III(b): 15% (p. 499, PDF p. 518); a final tax outside taxable "
            "income, section 8(1) (p. 44-45, PDF p. 63-64)",
            "Finance Act 2025 (clause (b) substituted)",
        ),
    ),
    dividend_deduction_rate=Rule(
        Decimal("0.15"),
        Source(
            ORDINANCE,
            "Section 150, at First Schedule, Part III, Division I(b): 15% deducted from the "
            "gross dividend (p. 519, PDF p. 538)",
            "Finance Act 2025 (clause (b) substituted)",
        ),
    ),
    profit_deduction_rate=Rule(
        Decimal("0.20"),
        Source(
            ORDINANCE,
            "Section 151(1)(b), at First Schedule, Part III, Division IA(a): 20% deducted from "
            "profit paid by a banking company (p. 521, PDF p. 540)",
            "Finance Act 2025 (Division IA substituted)",
        ),
    ),
    non_atl_increase=Rule(
        Decimal("1.00"),
        Source(
            ORDINANCE,
            "Tenth Schedule, rule 1: for a person not on the active taxpayers' list, the rate of "
            "tax to be deducted is increased by hundred percent (p. 761, PDF p. 780)",
            "Finance Act 2019 (Tenth Schedule inserted); Finance Act 2024 (rule 1 amended)",
        ),
    ),
    bonus_is_salary=Source(
        ORDINANCE,
        "Section 12(2)(a): salary includes any pay, wages or other remuneration, including "
        "bonus (p. 48, PDF p. 67)",
        "Income Tax Ordinance, 2001 (section 12 as enacted)",
    ),
    salary_withholding=Source(
        ORDINANCE,
        "Section 149(1): an employer deducts tax from each salary payment at the employee's "
        "average rate on the estimated income under the head Salary, including section 4AB "
        "(p. 308, PDF p. 327)",
        "Income Tax Ordinance, 2001 (section 149 as amended up to 31.07.2025)",
    ),
)
