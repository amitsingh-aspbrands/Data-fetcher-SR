"""
Configuration loader for the Shiprocket Data Fetcher.

WHY THIS FILE EXISTS:
- Keeps all configuration in one place (easy to find and change)
- Reads sensitive values (passwords, API keys) from environment variables
- Validates that required config is present before the app runs
- Makes it easy to switch between local/production settings

HOW IT WORKS:
- python-dotenv reads the .env file and loads values into environment variables
- We then read those environment variables here
- If any required value is missing, the app fails early with a clear error
  (instead of crashing halfway through with a confusing error)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Find the project root directory (one level up from this file)
PROJECT_ROOT = Path(__file__).parent.parent

# Load the .env file into environment variables
# This only affects this process — it doesn't change your system settings
load_dotenv(PROJECT_ROOT / ".env")


def _get_required(key: str) -> str:
    """Get an environment variable or exit with a helpful error."""
    value = os.getenv(key)
    if not value:
        print(f"ERROR: Missing required environment variable: {key}")
        print(f"Please set it in your .env file. See .env.example for reference.")
        sys.exit(1)
    return value


# --- Shiprocket Auth API (for getting the token) ---
SHIPROCKET_EMAIL = _get_required("SHIPROCKET_EMAIL")
SHIPROCKET_PASSWORD = _get_required("SHIPROCKET_PASSWORD")
SHIPROCKET_BASE_URL = os.getenv(
    "SHIPROCKET_BASE_URL", "https://apiv2.shiprocket.in/v1/external"
)

# --- E360 Marketing API (for fetching automation data) ---
# This is a DIFFERENT API from the main Shiprocket one
E360_BASE_URL = os.getenv(
    "E360_BASE_URL", "https://e360-marketing-api.shiprocket.in"
)
E360_CHANNEL_ID = _get_required("E360_CHANNEL_ID")

# --- Which automations to track ---
# Comma-separated list of event_rule_ids we care about
# Default: 65459 (Product Abandonment), 65461 (Cart Abandonment)
_rule_ids_raw = os.getenv("EVENT_RULE_IDS", "65459,65461")
EVENT_RULE_IDS = [int(x.strip()) for x in _rule_ids_raw.split(",")]

# --- Pickrr Reporting API (for dashboard/session data) ---
PICKRR_BASE_URL = os.getenv(
    "PICKRR_BASE_URL", "https://reporting.pickrr.com/api/ve1"
)
PICKRR_DOMAIN = os.getenv("PICKRR_DOMAIN", "includ.com")
PICKRR_COMPANY_ID = _get_required("PICKRR_COMPANY_ID")
# Static x-auth token for Pickrr dashboard API
PICKRR_XAUTH_TOKEN = _get_required("PICKRR_XAUTH_TOKEN")

# --- How many days back to fetch (not counting today) ---
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "7"))

# --- File/Directory Paths ---
OUTPUT_DIR = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "output")
LOG_DIR = PROJECT_ROOT / os.getenv("LOG_DIR", "logs")

# Create output and log directories if they don't exist
# exist_ok=True means "don't complain if the folder is already there"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
