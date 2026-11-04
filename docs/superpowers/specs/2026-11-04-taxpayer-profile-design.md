# 009 Taxpayer Profile: Design

**Date:** 2026-11-04 · **Status:** Proposed · **Feature:** 009 (README milestone 2 increment) ·
**Governed by:** [Constitution v1.2.0](../../../.specify/memory/constitution.md)

## Intent

The README's MVP has "one taxpayer profile, one configurable tax year (TY2026)". Earlier
features are waiting for it: 004 asks ATL status on the tax page "until the taxpayer-profile
increment exists", 003 stamps uploads with a "configured" tax year that nothing configures, and
006's MCP tool takes ATL as an input. 007's workflow reads the profile, so it must exist first.
This feature gives each account one profile holding its tax year and ATL status, and makes the
earlier features read from it once they are built.

## Scope

- **Profile fields:** tax year (a choice with one option, 2025-26 / TY2026, the only year with
  FBR rates) and ATL status (on FBR's Active Taxpayers' List: yes or no). Both are required;
  there is no "not sure" answer. Next to the ATL question, a link to FBR's online ATL check lets
  people find out (decided by Saifullah).
- **One profile per account**, editable at any time. A change applies to the next calculation;
  nothing already saved is recalculated or deleted.
- **When it's filled in:** on first login, a short "set up your profile" step appears before
  anything else. Pages that need the profile show a "finish your profile" link if it is missing.
- **Residency notice:** a one-line notice on the profile step: the app covers people who live in
  Pakistan and earn a salary. Residency is not asked or stored (decided by Saifullah:
  non-residents are outside the MVP, so storing an answer adds nothing).
- **Earlier features read the profile.** 003–006's documents are **not** edited (they were
  written expecting this increment). Instead, 009's own tasks make the follow-up changes to their
  code once it exists:
  - **003:** uploads are stamped with the profile's tax year; the consistency check compares the
    certificate's tax year with it.
  - **004:** ATL status comes from the profile; the tax page's ATL question and the `atl` query
    parameter are removed. If the user has no profile yet, the result stays blocked
    (`needs_atl_answer`), now with a link to the profile.
  - **005:** the wealth statement opens on the profile's tax year.
  - **006:** the MCP calculation tool reads ATL status and tax year from the token owner's
    profile instead of taking them as inputs.
  - **007:** reads the profile (noted in its design when it is brainstormed).

## Out of scope

Name, CNIC, NTN or any identity field (Principle V: synthetic data only); residency, filer
category or other taxpayer details; more than one tax year; more than one profile per account;
history of profile changes.

## Approaches

| Approach | Trade-off | Outcome |
|---|---|---|
| **A. Separate profile table, one row per account** | One more table; keeps 002's login table as designed; matches "one profile, one tax year" exactly | **Chosen** (Saifullah) |
| B. Columns on the `users` table | Slightly less code; mixes tax answers into the login table and reopens 002's design | Rejected |
| C. One set of answers per tax year | Real-life accurate (ATL and residency are yearly) and ready for TY2027; builds for many years when the MVP has one, adds "which year" to every reader | Rejected for now; A → C later is a small migration |

## Decisions

- Approach A; residency as a notice, not a field; first-login setup step; ATL required with a
  link to FBR's ATL check (Saifullah).
- **003–006 stay as written; 009's tasks carry the follow-up changes** (Saifullah: don't
  reopen PRs under review). 009 branches from 002, which it builds on, and is built after
  003–006, whose code its follow-up tasks change. The cost is small throwaway work: 004's tax
  page ATL question is built, then removed by 009.
- The `needs_atl_answer` blocked reason keeps its name; only its message changes, so 004's
  contract and tests change as little as possible. *(Builder's call.)*
- Tax year stays in the API paths (`/api/tax/{tax_year}`, `/api/wealth/{tax_year}`); the
  frontend fills it from the profile. *(Builder's call.)*
- Follow-up changes 009's tasks must cover: 003's `TAX_YEAR` setting (becomes the list of
  supported years, used for the profile's choice), 004's `atl` input and tax-page ATL question,
  and 006's calculation-tool inputs. *(Builder's call.)*
- **The backend enforces the profile, not only the UI.** With no profile: 003 refuses an upload
  with "set up your profile first"; 004 and 006 return `needs_atl_answer`. *(Builder's call.)*
- 006's `validate_salary_information` keeps its `tax_year` input (it is the certificate's year)
  and checks it against the token owner's profile, like 003's rule. *(Builder's call.)*

## Done when

- A new demo user is sent to the profile step on first login and can't skip past it to the
  other pages; after saving, they reach the app.
- The profile can be changed later; the next tax calculation uses the new ATL status.
- The tax page no longer asks ATL; with no profile it shows the blocked message with a profile
  link.
- Uploads carry the profile's tax year; the MCP tool works without ATL or tax year inputs.
- No identity fields are stored.

## Left to the plan

Table and migration, endpoint shapes (read and save the profile), how the frontend detects a
missing profile, and the exact follow-up tasks for 003–006.
