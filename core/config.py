import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")


def load_env_vars():
    """Reads .env key-value pairs without requiring external third-party libraries."""
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
        except Exception:
            pass


load_env_vars()


def get_max_threads() -> int:
    """Dynamically returns MAX_THREADS from .env file, defaults to 1."""
    load_env_vars()
    try:
        return max(1, int(os.environ.get("MAX_THREADS", 1)))
    except Exception:
        return 1


def get_cooling_delay() -> int:
    """Dynamically returns DELAY_BETWEEN_ACCOUNTS in seconds from .env file, defaults to 5 seconds."""
    load_env_vars()
    try:
        val = os.environ.get("DELAY_BETWEEN_ACCOUNTS") or os.environ.get("COOLING_DELAY_SECONDS") or "5"
        return max(0, int(val))
    except Exception:
        return 5


def get_max_proxy_latency() -> int:
    """Dynamically returns MAX_PROXY_LATENCY_MS from .env file, defaults to 2500 ms."""
    load_env_vars()
    try:
        val = os.environ.get("MAX_PROXY_LATENCY_MS", 2500)
        return max(500, int(val))
    except Exception:
        return 2500


PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.txt")
RESULTS_FILE = os.path.join(BASE_DIR, "results.txt")
OUTPUT_FILE = os.path.join(BASE_DIR, "pipopay_links.txt")
PROXY_FILE = os.path.join(BASE_DIR, "proxy.txt")

MAX_THREADS = get_max_threads()

# Default 30D 7-Seat Offer constants
APP_ID = 348188
REGION = "ID"
PRODUCT_ID = "space_a_7seats_monthly_discount2_svip"
SKU_ID = "SKU263351853060"
SKU_PLAN_ID = "1352062469636"
PRICE = "121000"
CURRENCY = "IDR"

MONTH_NAMES_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
MONTH_NAMES_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]