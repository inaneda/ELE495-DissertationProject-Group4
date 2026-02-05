"""
File Name       : security.py
Author          : Eda
Project         : ELE 496 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-05
Last Modified   : 2026-02-05

Description:
Simple API key security for WLAN usage.
Clients must send header:
    X-API-Key: <secret>
The secret is configured in src/app/core/config.py or via environment variable.
"""

from fastapi import Header, HTTPException
from src.app.core.config import API_KEY


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
