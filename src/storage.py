"""
Data Storage — saves fetched data to CSV with append/update logic.

WHY APPEND/UPDATE (not overwrite):
- We fetch data for the last 7 days every morning
- Some of those days already have rows in the CSV from yesterday's run
- Shiprocket counters can update retroactively (e.g., someone clicks a link
  2 days after it was sent) — so we want to UPDATE existing rows
- New days (yesterday) should be APPENDED

HOW IT WORKS:
1. Read existing CSV into memory (if it exists)
2. For each new record, check if a row with the same (date + event_rule_id) exists:
   - YES → Replace that row with the new data (update)
   - NO → Add the row (append)
3. Write the full updated dataset back to the CSV
4. Sort by date (newest first) so the file is easy to read

THE KEY CONCEPT — "composite key":
- A row is uniquely identified by (date + event_rule_id) together
- This means you can have multiple rules on the same date (that's fine)
- But you can't have the SAME rule on the SAME date twice (that's a duplicate)
"""

import csv
import logging
from pathlib import Path
from typing import Any

from config.settings import OUTPUT_DIR

logger = logging.getLogger(__name__)

# The CSV file name (single file, growing over time)
CSV_FILENAME = "shiprocket_e360_automation.csv"

# Column order for the CSV (keeps things consistent)
CSV_COLUMNS = [
    "date",
    "event_rule_id",
    "event_rule_name",
    "enabled",
    "audience_type",
    "sent",
    "delivered",
    "read",
    "failed",
    "open",
    "clicked",
    "orders",
    "revenue",
    "roi",
    "spent",
]


def save_records(new_records: list[dict[str, Any]]) -> Path:
    """
    Save records to CSV with append/update logic.

    - If a row with the same (date, event_rule_id) exists, it gets UPDATED
    - If it's a new (date, event_rule_id), it gets APPENDED
    - The file is sorted by date descending (newest first)

    Args:
        new_records: List of flat dictionaries from the fetcher.

    Returns:
        Path to the CSV file.
    """
    filepath = OUTPUT_DIR / CSV_FILENAME

    if not new_records:
        logger.warning("No new records to save.")
        return filepath

    # Step 1: Load existing data (if the file already exists)
    existing_records = _load_existing_csv(filepath)
    logger.info(
        "Loaded %d existing records from CSV.", len(existing_records)
    )

    # Step 2: Merge new records into existing ones
    # We use a dict with (date, event_rule_id) as the key
    # This automatically handles updates (same key = overwrite)
    merged = {}

    # First, add all existing records
    for record in existing_records:
        key = (record["date"], str(record["event_rule_id"]))
        merged[key] = record

    # Then, add/overwrite with new records
    updated_count = 0
    appended_count = 0
    for record in new_records:
        key = (record["date"], str(record["event_rule_id"]))
        if key in merged:
            updated_count += 1
        else:
            appended_count += 1
        merged[key] = record

    logger.info(
        "Merge result: %d updated, %d appended.", updated_count, appended_count
    )

    # Step 3: Sort by date (newest first), then by rule_id
    sorted_records = sorted(
        merged.values(),
        key=lambda r: (r["date"], str(r["event_rule_id"])),
        reverse=True,
    )

    # Step 4: Write back to CSV
    _write_csv(filepath, sorted_records)

    logger.info(
        "CSV saved: %d total records in %s", len(sorted_records), filepath
    )
    return filepath


def _load_existing_csv(filepath: Path) -> list[dict[str, Any]]:
    """
    Read existing CSV file into a list of dictionaries.
    Returns empty list if file doesn't exist yet (first run).
    """
    if not filepath.exists():
        logger.info("No existing CSV found. Starting fresh.")
        return []

    try:
        with open(filepath, mode="r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            return list(reader)
    except OSError as e:
        logger.error("Failed to read existing CSV: %s", e)
        raise SystemExit(f"Storage error: Could not read {filepath}")


def _write_csv(filepath: Path, records: list[dict[str, Any]]) -> None:
    """Write records to CSV with consistent column ordering."""
    try:
        with open(filepath, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(records)
    except OSError as e:
        logger.error("Failed to write CSV file: %s", e)
        raise SystemExit(f"Storage error: Could not write to {filepath}")
