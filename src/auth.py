"""
Shiprocket API Authentication.

WHY THIS IS A SEPARATE FILE:
- Authentication is its own concern — it might change independently
  (e.g., Shiprocket might add 2FA, or change token format)
- Keeps the main data-fetching logic clean and focused
- Makes it easy to test auth separately from data fetching

HOW SHIPROCKET AUTH WORKS:
1. We POST email + password to the login endpoint
2. Shiprocket returns a JSON response with a "token" field
3. We use that token in all subsequent API calls as:
   Authorization: Bearer <token>
"""

import logging
import requests

from config.settings import SHIPROCKET_BASE_URL, SHIPROCKET_EMAIL, SHIPROCKET_PASSWORD

# Logger for this module — writes to both console and log file
logger = logging.getLogger(__name__)


def get_auth_token() -> str:
    """
    Authenticate with Shiprocket and return the access token.

    Returns:
        str: The Bearer token to use in subsequent API calls.

    Raises:
        SystemExit: If authentication fails (no point continuing without a token).
    """
    login_url = f"{SHIPROCKET_BASE_URL}/auth/login"

    payload = {
        "email": SHIPROCKET_EMAIL,
        "password": SHIPROCKET_PASSWORD,
    }

    headers = {
        "Content-Type": "application/json",
    }

    logger.info("Attempting to authenticate with Shiprocket API...")

    try:
        response = requests.post(login_url, json=payload, headers=headers, timeout=30)

        # This raises an error if the HTTP status code indicates failure (4xx, 5xx)
        response.raise_for_status()

        data = response.json()
        token = data.get("token")

        if not token:
            logger.error("Login succeeded but no token in response. Response: %s", data)
            raise SystemExit("Authentication failed: No token received.")

        logger.info(
            "Authentication successful for company_id: %s", data.get("company_id")
        )
        return token

    except requests.exceptions.Timeout:
        logger.error("Authentication request timed out after 30 seconds.")
        raise SystemExit("Authentication failed: Request timed out.")

    except requests.exceptions.HTTPError as e:
        logger.error("Authentication failed with HTTP error: %s", e)
        logger.error("Response body: %s", e.response.text if e.response else "N/A")
        raise SystemExit(f"Authentication failed: {e}")

    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to Shiprocket API. Check your internet.")
        raise SystemExit("Authentication failed: Connection error.")

    except requests.exceptions.RequestException as e:
        logger.error("Unexpected error during authentication: %s", e)
        raise SystemExit(f"Authentication failed: {e}")
