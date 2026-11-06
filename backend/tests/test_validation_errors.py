"""422 replies never echo what was sent (security rule: no secrets or personal data in errors).

FastAPI's default validation reply includes each rejected value as `input`, so a malformed
login would send the password back and a profile save with extra fields would send back a CNIC.
"""

import pytest
from httpx2 import AsyncClient

pytestmark = pytest.mark.anyio

SECRET_PASSWORD = "do-not-echo-" + "x" * 1030
SYNTHETIC_CNIC = "00000-0000000-0"


async def test_login_validation_error_does_not_echo_the_password(client: AsyncClient) -> None:
    """Fails if a too-long password comes back in the error reply."""
    response = await client.post(
        "/api/auth/login", json={"email": "someone@example.com", "password": SECRET_PASSWORD}
    )

    assert response.status_code == 422
    assert "do-not-echo" not in response.text
    # Still says which field failed and why.
    [error] = response.json()["detail"]
    assert error["loc"] == ["body", "password"]
    assert error["msg"] == "String should have at most 1024 characters"
    assert "input" not in error


@pytest.mark.usefixtures("logged_in_user")
async def test_profile_validation_error_does_not_echo_extra_fields(client: AsyncClient) -> None:
    """Fails if an unexpected identity field comes back in the error reply."""
    response = await client.put(
        "/api/profile", json={"tax_year": "2025-26", "on_atl": True, "cnic": SYNTHETIC_CNIC}
    )

    assert response.status_code == 422
    assert SYNTHETIC_CNIC not in response.text
    [error] = response.json()["detail"]
    assert error["loc"] == ["body", "cnic"]
    assert "input" not in error
