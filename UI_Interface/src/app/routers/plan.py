"""
File Name       : plan.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-05
Last Modified   : 2026-02-05

Description:
This module defines endpoints to receive and store the placement plan
(pick/place pairing order) sent from the dashboard UI.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List

from src.app.routers.status import SYSTEM_STATE

# API key
from fastapi import Depends
from src.app.security import require_api_key

router = APIRouter(
    prefix="/api",
    tags=["Plan"],
    dependencies=[Depends(require_api_key)] # API key
)


class PlanItem(BaseModel):
    part: str = Field(..., examples=["d1"])
    padName: str = Field(..., examples=["konum-a"])
    padLabel: str = Field(..., examples=["a"])


class PlanRequest(BaseModel):
    items: List[PlanItem]


@router.post("/plan")
def set_plan(req: PlanRequest):
    if len(req.items) == 0:
        raise HTTPException(status_code=400, detail="Plan is empty.")

    seen_parts = set()
    for it in req.items:
        p = it.part.lower().strip()
        if p in seen_parts:
            raise HTTPException(status_code=400, detail=f"Duplicate component in plan: {p}")
        seen_parts.add(p)

    SYSTEM_STATE["plan"] = [item.model_dump() for item in req.items]
    # zaman eklentisi
    SYSTEM_STATE["plan_received_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # log
    SYSTEM_STATE["logs"].append(f"[{SYSTEM_STATE['plan_received_at']}] Plan received: {len(req.items)} steps")

    return {"ok": True, "count": len(req.items), "received_at": SYSTEM_STATE["plan_received_at"]}
