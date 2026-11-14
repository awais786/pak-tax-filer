# Research: Simple Income Tax Calculator (feature 010)

Every rule below is read from FBR's own text: the **Income Tax Ordinance, 2001 as amended up to
31.07.2025** (TY2026), the file the app's corpus already pins by SHA-256 in
`backend/app/rag/sources.yaml`
(`87e66ffa…df74`, https://download1.fbr.gov.pk/Docs/2025881983148210Income-Tax-Ordinance,-2001-Amended-upto-31.07.2025.pdf).
No third-party calculator, blog or article was used (Principle II). Text was extracted with
pypdf on 2026-11-14 and each passage read in context, including its amendment footnotes.

**Page numbers.** "p." is the page number printed on the page; "PDF p." is the page index in
this file (printed + 19; the file has no page labels). Feature 004's rates cite "PDF page" values
that equal printed + 1 (e.g. the salaried table as "PDF page 493"; in this file it is PDF p. 511,
printed p. 492). The sections and clauses 004 cites are right; only its page numbers disagree
with this file. See R8.

## R1. Rent: how an individual's property income is taxed in TY2026

**Decision:** rent is income under the head **"Income from Property"** (s.15(1), p. 56, PDF p. 75),
taxed in the **normal slabs** with the person's other taxable income. The taxable amount is the
rent minus the deductions in s.15A; the calculator applies only the automatic one, the **repairs
allowance of one-fifth of the rent** (s.15A(1)(a), p. 57, PDF p. 76). It is part of taxable
income, so it **counts toward the 75% salary test and the s.4AB Rs 10 million limit**.

**Rationale:**
- The separate rates for individuals' property income were removed: s.15(6) (tax at the rate in
  Division VIA) and s.15(7) were **omitted by the Finance Act, 2021** (footnotes 1 and 3, p. 57),
  and Division VIA of Part I ("Income from Property": the rates "in the case of individual and
  association of persons") was "omitted by the Finance Act, 2021" (footnote 2, p. 503, PDF p.
  522). Nothing replaces them, so property income joins total income under s.10(a)
  ("income under all heads", p. 46, PDF p. 65), and taxable income under s.9 is that total less
  deductible allowances (p. 46).
- s.15A applies to individuals again: FA2016 changed "person" to "company"; FA2021 changed
  "company" back to "person" (footnotes 5-14, p. 57). Its clause (a) is an *allowance* of one-fifth
  of the rent "computed before any deduction allowed under this section", not an expense to be
  proved, so it needs no extra input.
- The other s.15A deductions (insurance, local taxes, ground rent, mortgage profit, collection
  costs up to 4%, legal costs, irrecoverable rent) need amounts the simple form doesn't ask for:
  listed as not covered.
- The salaried table applies "where the income of an individual chargeable under the head
  'salary' exceeds seventy-five per cent of his taxable income" (First Schedule, Part I,
  Division I, clause (2), p. 491, PDF p. 510).

**Consequence (the lead's example):** salary Rs 250,000 × 12 = 3,000,000; rent Rs 140,000 × 12 =
1,680,000, less one-fifth 336,000 = property income 1,344,000; taxable income 4,344,000. Salary
share 3,000,000 / 4,344,000 = 69.06%, **not more than 75%**, so the **non-salaried table**
(clause (1)) applies to the whole 4,344,000: 650,000 + 40% × 1,144,000 = **Rs 1,107,600**. (On
the salaried table it would have been 701,400: the 75% test matters.)

**Alternatives considered:** taxing rent separately (as before FA2021) is no longer the law;
ignoring the repairs allowance would overstate the tax; asking for all s.15A deductions breaks
"simple".

## R2. The non-salaried table (TY2026)

**Decision:** First Schedule, Part I, Division I, clause (1), table substituted by the **Finance
Act, 2024** and unchanged by FA2025 (p. 490, PDF p. 509):

| Row | Taxable income | Tax |
|---|---|---|
| 1 | does not exceed 600,000 | 0% |
| 2 | exceeds 600,000, not 1,200,000 | 15% of the amount over 600,000 |
| 3 | exceeds 1,200,000, not 1,600,000 | 90,000 + 20% over 1,200,000 |
| 4 | exceeds 1,600,000, not 3,200,000 | 170,000 + 30% over 1,600,000 |
| 5 | exceeds 3,200,000, not 5,600,000 | 650,000 + 40% over 3,200,000 |
| 6 | exceeds 5,600,000 | 1,610,000 + 45% over 5,600,000 |

**Rationale:** consistent like the salaried table (600,000 × 15% = 90,000; + 400,000 × 20% =
170,000; + 1,600,000 × 30% = 650,000; + 2,400,000 × 40% = 1,610,000); the consistency test of
004 (FR-009) is extended to it. The proviso after it (45% → 40%) is for an association of persons
that is a professional firm: not individuals. The footnoted older tables (FA2023, FA2024's
predecessor) are never used.

## R3. Surcharge (s.4AB)

**Decision:** where **taxable income exceeds Rs 10 million**, a surcharge on the **Division I tax**
(the slab tax): **9%** for an individual deriving income under the head "Salary", **10%**
otherwise (s.4AB and its FA2025 proviso, p. 33, PDF p. 52). Taxable income here includes property
income (R1) and excludes dividends and bank profit (R4, R5).

**Rationale:** the proviso turns on deriving salary income at all, not on which table applies, so
a salaried person on the non-salaried table still pays 9%.

## R4. Dividends

**Decision:** tax under **s.5** at **15%** of the gross dividend (s.5(1)-(2), p. 35, PDF p. 54;
First Schedule, Part I, **Division III(b)**: "15% in the case of Real Estate Investment Trust and
cases other than those mentioned in clauses (a), (ba), (c) and (d)", substituted by FA2025, p. 499,
PDF p. 518). It is a **final tax** kept out of taxable income: s.8(1)(a) (the amount "shall not be
chargeable to tax under any head of income in computing the taxable income"), (c) and (d) (p. 44-45,
PDF p. 63-64). So dividends **don't count toward the 75% test or the Rs 10 million limit**.

The calculator's one dividends field is for ordinary dividends (clause (b)). The other cases are
listed as not covered: (a) 7.5% for IPP pass-through dividends, (ba) 25%/15% for mutual funds by
their debt/equity mix, (c) 0%/35% from a REIT special purpose vehicle, (d) 25% from a company paying
no tax.

**Filer vs non-filer:** the s.5 *tax* is 15% for everyone; what changes is the *deduction at
source*: s.150 deducts at First Schedule, Part III, Division I(b) **15%** (p. 519, PDF p. 538), and
for a person not on the active taxpayers' list the Tenth Schedule, rule 1 increases every deduction
rate "by hundred percent" (p. 761, PDF p. 780): **30%**. The comparison line says this: "a person
not on the ATL has 30% deducted instead of 15%"; whether the extra can be reclaimed is not
something the calculator states (as feature 004's FR-013: "needs confirmation").

## R5. Bank profit

**Decision:** unchanged from feature 004: **s.7B** separate tax at **20%** of gross profit paid by
a bank (Division IIIA(a), substituted by FA2025, p. 500, PDF p. 519); final under s.8 (s.7B is in
s.8(1)'s list, as substituted by FA2022/FA2025), so **out of taxable income**, the 75% test and
the surcharge limit. Above **Rs 5 million**, s.7B doesn't apply (s.7B(3)(b)): refused as in 004
(`profit_over_limit`).

**Filer vs non-filer:** s.151 deducts at Part III, **Division IA(a)** **20%** (p. 521, PDF p. 540);
the Tenth Schedule, rule 1 doubles it for a person not on the ATL: **40%**. Same wording as R4.

**Note for the lead (not changed here):** feature 004's Tax page still refuses
(`salary_share_ambiguous`, `surcharge_ambiguous`) when bank profit could change the 75% test or the
Rs 10 million limit. s.8(1)(a) answers that question: bank profit taxed under s.7B is not in
taxable income. The calculator follows the law; the Tax page is out of this feature's scope
(FR-005) and keeps its provisional refusal until the lead decides. Raised in the PR.

## R6. Bonus, and the order of the calculation

**Decision:** a bonus is salary: s.12(2)(a) lists "any pay, wages or other remuneration …
including … bonus" (p. 48, PDF p. 67). Salary income = monthly salary × 12 + bonus.

The calculation, all in exact `Decimal`:
1. Yearly amounts: salary × 12 + bonus; rent × 12; dividends; bank profit.
2. Property income = rent − rent / 5 (R1).
3. Taxable income = salary income + property income (dividends and bank profit excluded, R4-R5).
4. Table: salaried if salary income **exceeds** 75% of taxable income, else non-salaried (exactly
   75% is not "exceeds"; as 004's sign-off reading B). No taxable income (only dividends and/or
   bank profit): no slab tax.
5. Slab tax on taxable income from that table ("does not exceed" upper limits).
6. Surcharge (R3).
7. Dividend tax 15%; bank profit tax 20%.
8. Total tax = the sum of the rounded lines (slab tax, surcharge, dividend tax, profit tax), each
   rounded to the rupee under s.219 (p. 436, PDF p. 455), so the lines visibly add up.

**Alternatives considered:** rounding only the total (lines wouldn't add up on screen); applying
the table to salary alone and adding rent tax separately (not the law since FA2021).

## R7. The extras: monthly view, effective rate, bonus impact

**Decision:**
- **Monthly view** follows s.149(1) (p. 308, PDF p. 327): an employer deducts at "the employee's
  average rate of tax computed at the rates specified in Division I … on the estimated income of
  the employee chargeable under the head 'Salary' … including tax under section 4AB". So: tax on
  monthly salary × 12 alone (the salaried table, since salary is all of that income; plus 9%
  surcharge above Rs 10 million), divided by 12 and rounded; take-home = monthly salary − that.
  The bonus is left out (spec). Labelled "what your employer deducts each month on this salary".
  When rent moves the person to the non-salaried table, the full result's tax is higher than 12 ×
  the monthly deduction; the page says the difference is settled with the return (no figure for
  payable: out of scope).
- **Effective rate** = total tax ÷ total yearly gross income (salary × 12 + bonus + rent × 12 +
  dividends + bank profit) × 100, rounded half-up to one decimal place. A display ratio, not a
  tax figure.
- **Bonus impact** = total tax − total tax recalculated with the bonus at zero (same steps, so a
  table switch caused by the bonus shows up). Shown when salary and bonus are both above zero.
  It can be **negative**: the salaried table is never higher than the non-salaried one at the same
  income, so a bonus that lifts salary over 75% of taxable income lowers the total (worked example
  `bonus-tips-to-salaried`: a Rs 1 bonus lowers the tax by Rs 429,000). This cliff follows from the
  Ordinance's wording as read here; **for the tax practitioner to confirm** (backend review M1).

## R8. Effective dates, and 004's page numbers

**Decision:** every TY2026 rule applies to the tax year 2026, 1 July 2025 to 30 June 2026 (the
year the Ordinance amended to 31.07.2025 governs; FA2025 changes apply from it). The rates gain
one `effective_from` date per tax year, `2025-07-01`, shown with each rule's source (Principle II,
1.3.0). New rules cite printed and PDF pages of the pinned file; 004's page numbers are corrected
to the same scheme in this feature (a guarded change, asked for by the hook and called out in
review). The file pinned in `sources.yaml` is the reference because its checksum makes it
reproducible; Saifullah chose not to compare his own copy first (2026-11-14). All readings here
are provisional until a tax practitioner reviews the app.

## R9. Where the code goes

**Decision:** a new pure module `app/tax/calculator.py` (no database, network, clock or AI; added
to `.importlinter`'s source modules and 004's import test), reusing `engine.rupees`, `engine.Step`
and a band lookup generalised from `engine.salary_band`. Rates stay in `app/tax/rates/ty2026.py`
with new fields on `TaxYearRates`. The endpoint `POST /api/tax/calculator` (`current_user`,
`require_profile`, `require_json`; 200, nothing stored) lives in `app/tax/router.py`; the page is
`frontend/src/pages/CalculatorPage.tsx` at `/calculator`.

**Rationale:** one engine (anti-goal: two that disagree), 004's `calculate` untouched so its
worked examples can't change (SC-004); POST because the inputs are a body, though nothing is
created (no inputs in URLs or logs).
