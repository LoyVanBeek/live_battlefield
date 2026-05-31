import os

IS_CI = os.environ.get("GITHUB_ACTIONS") == "true"

HTTPX_TIMEOUT = 90 if IS_CI else 30
PLAYWRIGHT_TIMEOUT = 90_000 if IS_CI else 30_000

