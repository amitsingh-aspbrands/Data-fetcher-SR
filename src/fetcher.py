"""
Data Fetcher for Shiprocket E360 Marketing Automation API.

WHAT THIS DOES:
- Calls the E360 automation/list endpoint for a specific date
- Handles pagination (fetches all pages if there are many results)
- Filters results to only keep the event_rule_ids we care about
- Returns clean, flat records ready for CSV storage

KEY DIFFERENCE FROM AUTH API:
- Different base URL (e360-marketing-api.shiprocket.in vs apiv2.shiprocket.in)
- Needs extra headers: x-sr-token AND x-channel-id
- Uses POST with a JSON body (not GET)

WHY WE FETCH ONE DAY AT A TIME:
- The API takes from_date and to_date as filters
- We want per-day data so we can track trends in our dashboard
- main.py calls this function once per day in the lookback window
"""

import logging
from typing import Any

import requests

from config.settings import E360_BASE_URL, E360_CHANNEL_ID, EVENT_RULE_IDS

logger = logging.getLogger(__name__)


def fetch_automation_data_for_date(
    token: str, date_str: str
) -> list[dict[str, Any]]:
    """
    Fetch automation data from E360 API for a single date.

    Args:
        token: The Bearer auth token from the login step.
        date_str: Date in YYYY-MM-DD format (e.g., "2026-08-19").

    Returns:
        A list of flat dictionaries — one per automation rule found.
        Each dict contains the rule info + its counters, ready for CSV.
        Only includes rules matching EVENT_RULE_IDS from config.

    Raises:
        SystemExit: If the API call fails.
    """
    endpoint = f"{E360_BASE_URL}/automation/list"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "x-sr-token": token,
        "x-channel-id": E360_CHANNEL_ID,
    }

    # Build the date range for a single day (midnight to end of day)
    from_date = f"{date_str}T00:00:00.000Z"
    to_date = f"{date_str}T23:59:59.999Z"

    all_records = []
    current_page = 0
    total_pages = 1  # Will be updated after first response

    logger.info("Fetching automation data for date: %s", date_str)

    while current_page < total_pages:
        payload = {
            "page_request_info": {
                "current_page": current_page,
                "page_size": "50",  # Fetch 50 at a time (more efficient than 10)
            },
            "filter": {
                "from_date": from_date,
                "to_date": to_date,
                "rule_status": None,
                "event_rule_name": None,
                "enable_revenue": None,
                "audience_type": None,
            },
        }

        try:
            response = requests.post(
                endpoint, json=payload, headers=headers, timeout=60
            )
            response.raise_for_status()
            result = response.json()

            # Check API-level status
            if result.get("status") != "SUCCESS":
                logger.error(
                    "API returned non-success status: %s — %s",
                    result.get("status"),
                    result.get("message"),
                )
                raise SystemExit(
                    f"API error: {result.get('status')} — {result.get('message')}"
                )

            # Extract pagination info
            pagination = result["data"]["pagination_info"]
            total_pages = pagination["total_pages"]

            # Extract the automation records
            records = result["data"]["data"]

            # Filter to only the rule IDs we care about
            for record in records:
                if record["event_rule_id"] in EVENT_RULE_IDS:
                    flat_record = _flatten_record(record, date_str)
                    all_records.append(flat_record)

            current_page += 1

        except requests.exceptions.Timeout:
            logger.error("API request timed out (page %d).", current_page)
            raise SystemExit("Data fetch failed: Request timed out.")

        except requests.exceptions.HTTPError as e:
            logger.error("API request failed: %s", e)
            logger.error(
                "Response body: %s", e.response.text if e.response else "N/A"
            )
            raise SystemExit(f"Data fetch failed: {e}")

        except requests.exceptions.RequestException as e:
            logger.error("Unexpected network error: %s", e)
            raise SystemExit(f"Data fetch failed: {e}")

        except (KeyError, TypeError) as e:
            logger.error("Unexpected API response structure: %s", e)
            raise SystemExit(f"Data fetch failed: Unexpected response format — {e}")

    logger.info(
        "Date %s: Found %d matching records (out of %d total).",
        date_str,
        len(all_records),
        pagination.get("total_records", "?"),
    )
    return all_records


def _flatten_record(record: dict, date_str: str) -> dict[str, Any]:
    """
    Flatten a nested API record into a single-level dictionary for CSV.

    WHY FLATTEN:
    - CSV files are flat (no nesting) — each column is one value
    - The API returns counters as a nested object; we pull them up to top level
    - We also add the date so each row knows which day it belongs to

    BEFORE (nested):
        {"event_rule_name": "Cart", "counters": {"sent": 100, "clicked": 5}}

    AFTER (flat):
        {"date": "2026-08-19", "event_rule_name": "Cart", "sent": 100, "clicked": 5}
    """
    counters = record.get("counters", {})

    return {
        "date": date_str,
        "event_rule_id": record["event_rule_id"],
        "event_rule_name": record["event_rule_name"],
        "enabled": record["enabled"],
        "audience_type": record.get("audience_type", ""),
        # Counters (the metrics you'll use in dashboards)
        "sent": counters.get("sent", 0),
        "delivered": counters.get("delivered", 0),
        "read": counters.get("read", 0),
        "failed": counters.get("failed", 0),
        "open": counters.get("open", 0),
        "clicked": counters.get("clicked", 0),
        "orders": counters.get("orders", 0),
        "revenue": counters.get("revenue", 0),
        "roi": counters.get("roi", 0),
        "spent": counters.get("spent", 0),
    }
