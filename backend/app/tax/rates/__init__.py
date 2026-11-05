"""Tax rates, keyed by tax year (feature 004 fills this in).

Every value here MUST come from FBR's own gazetted documents (the Income Tax Ordinance 2001 as
amended by the relevant Finance Act, and FBR's guides) and record its source document, section
and tax year. Third-party calculators, blogs and news articles are never a source
(constitution, Principle II).

This module is guarded: the Claude Code tax-rates hook asks for human approval before any change
here, and every change must be called out in review.
"""
