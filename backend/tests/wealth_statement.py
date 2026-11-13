"""The signed-off "reconciled" wealth statement (tests/wealth/worked_examples.yaml), shared by
005's API tests and 008's PDF tests."""

from typing import Any

STATEMENT: dict[str, Any] = {
    "previous_net_assets": "2100000",
    "assets": [
        {"category": "bank_account", "description": "Savings account", "amount": "1350000"},
        {"category": "motor_vehicle", "description": "Car", "amount": "1400000"},
    ],
    "liabilities": [{"description": "Car loan", "creditor": "Bank", "amount": "200000"}],
    "other_exempt_income": "0",
    "foreign_remittance": "0",
    "inheritance": "0",
    "gifts_received": "0",
    "family_contribution": "0",
    "gifts_given": "0",
    "expenses": {"rent": "600000", "electricity": "150000", "other_household": "768000"},
}
