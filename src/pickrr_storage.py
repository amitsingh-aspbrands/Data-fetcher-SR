"""
Pickrr Dashboard Data Storage — append-only daily CSV.

WHY APPEND-ONLY (unlike E360 which updates):
- Pickrr dashboard data is final once the day ends
- We only fetch yesterday's data each morning
- No retroactive changes, so once a row is written, it's done
- We still check for duplicates (in case the job runs twice)

HOW IT WORKS:
1. Check if the CSV file exists
2. If it does, check if yesterday's date is already in it (duplicate check)
3. If not a duplicate, append the new row
4. If file doesn't exist, create it with headers + the new row

FILE: output/pickrr_dashboard.csv
One row per day, growing over time.
"""

import csv
import logging
from pathlib import Path
from typing import Any

from config.settings import OUTPUT_DIR

logger = logging.getLogger(__name__)

CSV_FILENAME = "pickrr_dashboard.csv"

# Column order for the CSV — defines what appears and in what order
# This must match the keys produced by pickrr_fetcher._flatten_dashboard_response
CSV_COLUMNS = [
    "date",
    # Overall Stats
    "total_sales",
    "total_sales_delta",
    "total_orders",
    "total_orders_delta",
    "fastrr_customers",
    "fastrr_customers_delta",
    "cod_prepaid_ratio",
    "cod_prepaid_ratio_delta",
    "cart_abandonment_rate",
    "cart_abandonment_rate_delta",
    # Funnel raw numbers (abandonCartStats)
    "funnel_cart",
    "funnel_otp_request",
    "funnel_otp_verified",
    "funnel_order_screen",
    "funnel_payment_initiated",
    "funnel_orders",
    "funnel_native_flow",
    "funnel_address_screen",
    "funnel_prepaid_count",
    "funnel_existing_customer",
    # Conversion stats (checkoutConversionStats)
    "conv_checkout_initiated",
    "conv_checkout_initiated_pct",
    "conv_otp_initiated",
    "conv_otp_initiated_pct",
    "conv_logged_in",
    "conv_logged_in_pct",
    "conv_order_screen",
    "conv_order_screen_pct",
    "conv_native_flow",
    "conv_native_flow_pct",
    "conv_payment_screen_opened",
    "conv_payment_screen_opened_pct",
    "conv_order_placed",
    "conv_order_placed_pct",
    "conv_prepaid_percent",
    "conv_prepaid_percent_pct",
]


def save_dashboard_record(record: dict[str, Any]) -> Path:
    """
    Append a single day's dashboard record to the CSV.

    - Skips if the date already exists (duplicate protection)
    - Creates the file with headers if it doesn't exist yet

    Args:
        record: Flat dictionary from pickrr_fetcher (one day's data).

    Returns:
        Path to the CSV file.
    """
    if not record:
        logger.warning("No Pickrr record to save.")
        return None

    filepath = OUTPUT_DIR / CSV_FILENAME
    date_to_save = record.get("date")

    # Check for duplicates if file already exists
    if filepath.exists():
        existing_dates = _get_existing_dates(filepath)
        if date_to_save in existing_dates:
            logger.info(
                "Date %s already exists in Pickrr CSV. Skipping (no duplicates).",
                date_to_save,
            )
            return filepath

    # If file doesn't exist, create it with headers
    file_is_new = not filepath.exists()

    try:
        with open(filepath, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(
                csvfile, fieldnames=CSV_COLUMNS, extrasaction="ignore"
            )

            # Write header only if this is a new file
            if file_is_new:
                writer.writeheader()

            writer.writerow(record)

        logger.info("Appended Pickrr data for %s to: %s", date_to_save, filepath)
        return filepath

    except OSError as e:
        logger.error("Failed to write Pickrr CSV: %s", e)
        raise SystemExit(f"Pickrr storage failed: Could not write to {filepath}")


def _get_existing_dates(filepath: Path) -> set[str]:
    """Read the CSV and return a set of all dates already stored."""
    try:
        with open(filepath, mode="r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            return {row["date"] for row in reader if row.get("date")}
    except OSError as e:
        logger.error("Failed to read existing Pickrr CSV: %s", e)
        return set()
