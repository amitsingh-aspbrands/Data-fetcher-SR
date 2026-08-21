"""
Pickrr Reporting API Authentication.

WHAT'S NEEDED FOR THE DASHBOARD API:
1. x-auth token — STATIC, stored in .env (doesn't change)
2. session_id — obtained fresh each run by calling create/session

WHY session_id IS FETCHED DYNAMICALLY:
- Sessions can expire, so we create a fresh one each run
- It's a lightweight call (no auth needed, just company-id header)
"""

import logging
import requests

from config.settings import (
    PICKRR_BASE_URL,
    PICKRR_COMPANY_ID,
    PICKRR_DOMAIN,
    PICKRR_XAUTH_TOKEN,
    SHIPROCKET_EMAIL,
)

logger = logging.getLogger(__name__)


def get_pickrr_token() -> str:
    """
    Return the static Pickrr x-auth token from config.

    This token doesn't change — it's stored in .env.
    We keep this as a function (rather than importing directly)
    so the calling code stays consistent and we can easily
    switch back to dynamic fetching if needed later.
    """
    logger.info("Using static Pickrr x-auth token from config.")
    return PICKRR_XAUTH_TOKEN


def get_session_id() -> str:
    """
    Create a Pickrr session and return the session_id.

    This is a simple call — no auth token needed, just company-id header
    and email/domain as query parameters.

    Returns:
        str: The session_id to use as 'authentication-info' header.

    Raises:
        SystemExit: If the call fails.
    """
    url = f"{PICKRR_BASE_URL}/dashboard-service/user/create/session"

    headers = {
        "company-id": PICKRR_COMPANY_ID,
    }

    params = {
        "email": SHIPROCKET_EMAIL,
        "domain": PICKRR_DOMAIN,
    }

    logger.info("Creating Pickrr session for %s @ %s...", SHIPROCKET_EMAIL, PICKRR_DOMAIN)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Response structure:
        # { "status": true, "data": "e45bee72-3e41-4daa-b2cd-d2b9be881a34" }
        # The session_id is directly in the "data" field as a string
        if not data.get("status"):
            logger.error("Session API returned status=false: %s", data)
            raise SystemExit("Pickrr session failed: API returned failure status.")

        session_id = data.get("data")

        if not session_id:
            logger.error("No session_id in response: %s", data)
            raise SystemExit("Pickrr session failed: No session_id in response.")

        logger.info("Pickrr session created successfully.")
        return session_id

    except requests.exceptions.HTTPError as e:
        logger.error("Pickrr session creation failed: %s", e)
        logger.error("Response: %s", e.response.text if e.response else "N/A")
        raise SystemExit(f"Pickrr session failed: {e}")

    except requests.exceptions.RequestException as e:
        logger.error("Pickrr session creation error: %s", e)
        raise SystemExit(f"Pickrr session failed: {e}")
