"""
Application configuration values.
These settings are used across the backend services.
"""

import os


# WLAN / API security
API_KEY: str = os.environ.get("PNP_API_KEY", "dev-key-change-me")


# camera
CAMERA_DEVICE_INDEX: int = int(os.environ.get("PNP_CAMERA_INDEX", "0"))


# demo mode (set DEMO_MODE=false for real hardware)
DEMO_MODE: bool = os.environ.get("DEMO_MODE", "true").lower() == "true"
