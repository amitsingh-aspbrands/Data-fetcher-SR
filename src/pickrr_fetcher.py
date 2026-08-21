"""
Data Fetcher for Pickrr Reporting Dashboard API.

WHAT THIS DOES:
- Calls the Pickrr dashboard report endpoint for yesterday's date
- Parses the response and flattens it into a single row of metrics
- Returns a flat dictionary ready for CSV storage

THE RESPONSE HAS THREE USEFUL SECTIONS:
1. overallStats — high-level metrics (Total Sales, Orders, COD%, etc.)
2. abandonCartStats — funnel numbers (cart, otp, orders, prepaid, etc.)
3. checkoutConversionStats — conversion steps with percentages

WE FLATTEN ALL THREE INTO ONE ROW because:
- A single row per date is easiest for dashboards (one row = one day)
- Wide tables (many columns) are fine for analytics tools
- It avoids complex joins later when building dashboards

FETCH LOGIC:
- Only fetches yesterday (data is final once the day ends)
- Append-only — no need to update past rows
"""

import logging
from typing import Any

import requests

from config.settings import PICKRR_BASE_URL

logger = logging.getLogger(__name__)


def fetch_dashboard_data_for_date(
    token1: str, session_id: str, date_str: str
) -> dict[str, Any]:
    """
    Fetch and flatten dashboard data from Pickrr for a single date.

    Args:
        token1: The x-auth token (from fetch-sr-checkout-accounts).
        session_id: The session ID (from create/session).
        date_str: Date in YYYY-MM-DD format (e.g., "2026-08-19").

    Returns:
        A flat dictionary with all metrics for that date, ready for CSV.
        Returns None if no data found for the date.

    Raises:
        SystemExit: If the API call fails.
    """
    url = f"{PICKRR_BASE_URL}/dashboard-service/report/dashboard"

    headers = {
        "x-auth": token1,
        "Content-Type": "application/json",
        "authentication-info": session_id,
    }

    params = {
        "from": date_str,
        "to": date_str,
        "duration": "daily",
        "channelSource": "all",
        "shopifySessionData": "true",
    }

    logger.info("Fetching Pickrr dashboard data for: %s", date_str)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()

        raw_data = response.json()

        if not raw_data.get("status"):
            logger.error("Pickrr dashboard API returned status=false: %s", raw_data)
            raise SystemExit("Pickrr fetch failed: API returned failure status.")

        # Parse and flatten the response into a single row
        flat_record = _flatten_dashboard_response(raw_data["data"], date_str)

        logger.info("Pickrr dashboard data fetched and flattened for %s.", date_str)
        return flat_record

    except requests.exceptions.Timeout:
        logger.error("Pickrr dashboard request timed out for %s.", date_str)
        raise SystemExit("Pickrr fetch failed: Request timed out.")

    except requests.exceptions.HTTPError as e:
        logger.error("Pickrr dashboard request failed: %s", e)
        logger.error("Response: %s", e.response.text if e.response else "N/A")
        raise SystemExit(f"Pickrr fetch failed: {e}")

    except requests.exceptions.RequestException as e:
        logger.error("Pickrr dashboard fetch error: %s", e)
        raise SystemExit(f"Pickrr fetch failed: {e}")


def _flatten_dashboard_response(data: dict, date_str: str) -> dict[str, Any]:
    """
    Flatten the nested dashboard response into a single flat dictionary.

    WHAT WE EXTRACT:

    From overallStats (high-level metrics):
        - total_sales, total_orders, cod_percent, cart_abandonment_rate

    From abandonCartStats (funnel raw numbers):
        - cart, otp_request, otp_verified, order_screen,
          payment_initiated, orders, prepaid_payment_count, etc.

    From checkoutConversionStats (conversion percentages):
        - checkout_initiated, otp_initiated, logged_in, order_screen_conversion,
          payment_screen_opened, order_placed, prepaid_percent
    """
    flat = {"date": date_str}

    # --- Section 1: overallStats ---
    # These are title-value pairs. We map titles to clean column names.
    overall_stats = data.get("overallStats", [])
    overall_title_map = {
        "Total Sales Through Fastrr": "total_sales",
        "Total Orders Through Fastrr": "total_orders",
        "Fastrr Customers": "fastrr_customers",
        "COD% : Prepaid%": "cod_prepaid_ratio",
        "Cart Abandonment Rate": "cart_abandonment_rate",
    }

    for stat in overall_stats:
        col_name = overall_title_map.get(stat.get("title"))
        if col_name:
            flat[col_name] = stat.get("curValue", 0)
            # Also store the delta (% change from previous period)
            flat[f"{col_name}_delta"] = stat.get("delta", 0)

    # --- Section 2: abandonCartStats (raw funnel numbers) ---
    # These come from the first item in combinedCheckoutConversionStats
    combined = data.get("combinedCheckoutConversionStats", [])
    if combined:
        abandon_stats = combined[0].get("abandonCartStats", {})

        # Map API field names to clean CSV column names
        abandon_fields = {
            "cart": "funnel_cart",
            "otpRequest": "funnel_otp_request",
            "otpVerified": "funnel_otp_verified",
            "orderScreen": "funnel_order_screen",
            "paymentInitiated": "funnel_payment_initiated",
            "order": "funnel_orders",
            "nativeFlow": "funnel_native_flow",
            "addressScreen": "funnel_address_screen",
            "prepaidPaymentCount": "funnel_prepaid_count",
            "existingCustomer": "funnel_existing_customer",
        }

        for api_key, col_name in abandon_fields.items():
            flat[col_name] = abandon_stats.get(api_key, 0)

    # --- Section 3: checkoutConversionStats (conversion percentages) ---
    if combined:
        conversion_stats = combined[0].get("checkoutConversionStats", [])

        conversion_title_map = {
            "Checkout Initiated": "conv_checkout_initiated",
            "OTP Initiated": "conv_otp_initiated",
            "Logged In": "conv_logged_in",
            "Order Screen": "conv_order_screen",
            "Native Flow": "conv_native_flow",
            "Payment Screen Opened": "conv_payment_screen_opened",
            "Order Placed": "conv_order_placed",
            "Prepaid Percent": "conv_prepaid_percent",
        }

        for stat in conversion_stats:
            col_name = conversion_title_map.get(stat.get("title"))
            if col_name:
                flat[col_name] = stat.get("curValue", 0)
                # Delta here is the conversion % from previous step
                flat[f"{col_name}_pct"] = stat.get("delta", 0)

    return flat
