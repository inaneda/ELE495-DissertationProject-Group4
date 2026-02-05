"""
File Name       : plan.py
Author          : Eda
Project         : ELE 496 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-05
Last Modified   : 2026-02-05

Description:
This module defines endpoints to receive and store the placement plan
(pick/place pairing order) sent from the dashboard UI.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List

from src.app.routers.status import SYSTEM_STATE

router = APIRouter(prefix="/api", tags=["Plan"])


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

    # Store plan in state (later this can be persisted to file/db)
    SYSTEM_STATE["plan"] = [item.model_dump() for item in req.items]

    # Log
    SYSTEM_STATE["logs"].append(f"Plan received: {len(req.items)} steps")

    return {"ok": True, "count": len(req.items)}
