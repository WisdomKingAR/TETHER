"""Pydantic request/response models."""
from __future__ import annotations
from pydantic import BaseModel, Field


class Ok(BaseModel):
    ok: bool = True


class Health(BaseModel):
    ok: bool
    version: str
    env: str
    agents: int
    events: int
    clients: int
    mode: str


class ModeIn(BaseModel):
    enforce: bool


class SimIn(BaseModel):
    paused: bool | None = None
    speed: float | None = Field(None, ge=0.25, le=8.0)


class AutoIn(BaseModel):
    on: bool
    interval: float | None = Field(None, ge=4, le=60, description="seconds between red-team attacks")


class SpawnIn(BaseModel):
    template: str = Field("procurement", description="role template: procurement | hr_help | code_review | finance_recon")
    name: str | None = Field(None, max_length=60)


class AttackIn(BaseModel):
    scenario: str
    agent: str | None = Field(None, description="override the scenario's default target agent")


class PlayIn(BaseModel):
    agent: str = "procurement"
    text: str = Field(..., min_length=1, max_length=20000, description="document text the agent will read")


class ExchangeIn(BaseModel):
    agent: str
    scope: list[str]
    ttl: int = Field(300, ge=30, le=3600)


class ApprovalIn(BaseModel):
    approve: bool


class CanaryIn(BaseModel):
    value: str = Field(..., min_length=3, max_length=500)


class ContractPatch(BaseModel):
    allow_tools: list[str] | None = None
    allow_classes: list[str] | None = None
    deny_classes: list[str] | None = None
    egress: list[str] | None = None
    decoys: list[str] | None = None
    delegate_to: list[str] | None = None
    rate_per_min: float | None = Field(None, gt=0)
    max_bytes_out: float | None = Field(None, gt=0)
