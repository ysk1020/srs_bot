import os 
from datetime import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

def _required_env(key: str) -> str:
    val=os.getenv(key)
    if not val:
        raise ValueError(f"Missing required env var: {key}")
    return val

TELEGRAM_BOT_TOKEN = _required_env("TELEGRAM_BOT_TOKEN")

# Adjust to your actual timezone / daily schedule.
TIMEZONE = ZoneInfo("Europe/Vilnius")
SEND_TIMES = [time(9, 0), time(20, 0)]

# Inactivity nudge: fire if no answer within this many hours (spec range: 48-72h).
NUDGE_THRESHOLD_HOURS = 60

# Retry-with-backoff for a failed send.
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = [5, 15, 45]

DB_PATH = "data.db"