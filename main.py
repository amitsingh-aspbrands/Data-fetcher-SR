"""
Shiprocket Data Fetcher — Main Entry Point.

THIS IS THE FILE YOU RUN:
    python main.py

WHAT IT DOES (in order):
1. Sets up logging
2. Authenticates with Shiprocket API (gets a token)
3. PIPELINE 1 — E360 Marketing Automation:
   - Fetches last 7 days of automation data
   - Updates/appends to CSV (counters can change retroactively)
4. PIPELINE 2 — Pickrr Dashboard:
   - Gets Pickrr token + session from SR token
   - Fetches yesterday's dashboard data
   - Appends to CSV (one new row per day)
5. Logs success/failure and how long it took

TWO SEPARATE PIPELINES, ONE JOB:
- Both use the same Shiprocket auth token as their starting point
- They write to separate CSV files (different data, different structure)
- If one fails, the other still runs (independent error handling)
"""

import logging
import sys
import time
from datetime import datetime, timedelta

from config.settings import LOG_DIR, LOOKBACK_DAYS
from src.auth import get_auth_token
from src.fetcher import fetch_automation_data_for_date
from src.storage import save_records
from src.pickrr_auth import get_pickrr_token, get_session_id
from src.pickrr_fetcher import fetch_dashboard_data_for_date
from src.pickrr_storage import save_dashboard_record


def setup_logging() -> None:
    """
    Configure logging to write to both console and a daily log file.

    Log levels explained:
    - INFO: Normal operations (started, succeeded, how many records)
    - WARNING: Something odd but not broken (e.g., 0 records returned)
    - ERROR: Something went wrong (API failed, file write failed)
    """
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"fetcher_{today}.log"

    # Create a formatter that shows timestamp, level, and message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler 1: Write to log file
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Handler 2: Write to console (so you can see output when testing)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_date_range() -> list[str]:
    """
    Generate the list of dates to fetch for E360 (last N days, not including today).

    Example with LOOKBACK_DAYS=7 and today being Aug 20:
    Returns: ["2026-08-19", "2026-08-18", ..., "2026-08-13"]
    """
    today = datetime.now().date()
    dates = []
    for days_back in range(1, LOOKBACK_DAYS + 1):
        date = today - timedelta(days=days_back)
        dates.append(date.strftime("%Y-%m-%d"))
    return dates


def get_yesterday() -> str:
    """Get yesterday's date as YYYY-MM-DD string (for Pickrr)."""
    yesterday = datetime.now().date() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def run_e360_pipeline(token: str, logger: logging.Logger) -> None:
    """
    Pipeline 1: Fetch E360 marketing automation data for last 7 days.

    WHY 7 DAYS:
    - Shiprocket counters (clicks, orders, revenue) update retroactively
    - By re-fetching 7 days, we catch those late updates
    - Storage layer handles deduplication (updates existing rows)
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("PIPELINE 1: E360 Marketing Automation")
    logger.info("=" * 60)

    dates = get_date_range()
    logger.info(
        "Fetching %d days: %s to %s",
        len(dates),
        dates[-1],  # oldest
        dates[0],   # newest (yesterday)
    )

    all_records = []
    for i, date_str in enumerate(dates, 1):
        logger.info("  Fetching day %d/%d: %s", i, len(dates), date_str)
        day_records = fetch_automation_data_for_date(token, date_str)
        all_records.extend(day_records)

    logger.info("Fetched %d total records. Saving to CSV...", len(all_records))
    output_file = save_records(all_records)
    logger.info("E360 data saved to: %s", output_file)


def run_pickrr_pipeline(token: str, logger: logging.Logger) -> None:
    """
    Pipeline 2: Fetch Pickrr dashboard data for yesterday.

    WHY ONLY YESTERDAY:
    - Dashboard data is final once the day ends (no retroactive changes)
    - One new row appended per morning
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("PIPELINE 2: Pickrr Dashboard")
    logger.info("=" * 60)

    # Step A: Get Pickrr-specific credentials
    logger.info("Getting Pickrr auth token...")
    token1 = get_pickrr_token()

    logger.info("Creating Pickrr session...")
    session_id = get_session_id()

    # Step B: Fetch yesterday's data
    yesterday = get_yesterday()
    logger.info("Fetching dashboard data for: %s", yesterday)
    record = fetch_dashboard_data_for_date(token1, session_id, yesterday)

    # Step C: Save to CSV
    if record:
        logger.info("Saving Pickrr data...")
        output_file = save_dashboard_record(record)
        logger.info("Pickrr data saved to: %s", output_file)
    else:
        logger.warning("No Pickrr data returned for %s.", yesterday)


def main() -> None:
    """Main entry point: authenticate → run both pipelines."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Shiprocket Data Fetcher — Starting run")
    logger.info("Time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    start_time = time.time()
    pipeline_results = {"e360": "not started", "pickrr": "not started"}

    try:
        # Step 1: Authenticate with Shiprocket (shared by both pipelines)
        logger.info("Authenticating with Shiprocket...")
        token = get_auth_token()

        # Step 2: Run E360 pipeline
        try:
            run_e360_pipeline(token, logger)
            pipeline_results["e360"] = "SUCCESS"
        except SystemExit as e:
            logger.error("E360 pipeline failed: %s", e)
            pipeline_results["e360"] = f"FAILED: {e}"

        # Step 3: Run Pickrr pipeline
        try:
            run_pickrr_pipeline(token, logger)
            pipeline_results["pickrr"] = "SUCCESS"
        except SystemExit as e:
            logger.error("Pickrr pipeline failed: %s", e)
            pipeline_results["pickrr"] = f"FAILED: {e}"

        # Summary
        elapsed = time.time() - start_time
        logger.info("")
        logger.info("=" * 60)
        logger.info("RUN COMPLETE in %.1f seconds", elapsed)
        logger.info("  E360 Pipeline:  %s", pipeline_results["e360"])
        logger.info("  Pickrr Pipeline: %s", pipeline_results["pickrr"])
        logger.info("=" * 60)

        # Exit with error code if any pipeline failed
        if "FAILED" in pipeline_results["e360"] or "FAILED" in pipeline_results["pickrr"]:
            sys.exit(1)

    except SystemExit as e:
        # Auth failure — neither pipeline can run
        elapsed = time.time() - start_time
        logger.error("=" * 60)
        logger.error("FATAL: Authentication failed after %.1f seconds: %s", elapsed, e)
        logger.error("Neither pipeline could run.")
        logger.error("=" * 60)
        sys.exit(1)

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("=" * 60)
        logger.error("UNEXPECTED ERROR after %.1f seconds: %s", elapsed, e)
        logger.error("=" * 60, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
