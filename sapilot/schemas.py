"""Shared Pydantic schemas for SAPILOT actions, observations, and evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tier(str, Enum):
    T1_SANDBOX = "T1_SANDBOX"
    T2_SUPERVISED = "T2_SUPERVISED"
    T3_OBSERVE = "T3_OBSERVE"


class Channel(str, Enum):
    GUI = "gui"
    API = "api"
    HYBRID = "hybrid"


class ActionType(str, Enum):
    SET_TEXT = "setText"
    PRESS = "press"
    SELECT = "select"
    SET_FOCUS = "setFocus"
    SEND_VKEY = "sendVKey"
    READ_TABLE = "readTable"
    READ_CONFIG = "readConfig"
    RESOLVE_MESSAGE = "resolveMessage"
    CHECK_AUTH = "checkAuth"
    SET_BREAKPOINT = "setBreakpoint"
    READ_VARIABLES = "readVariables"
    PROPOSE_CONFIG = "proposeConfig"
    APPLY_CONFIG = "applyConfig"
    VERIFY = "verify"
    ESCALATE = "escalate"
    DONE = "done"


class ObservationStatus(str, Enum):
    OK = "OK"
    GROUNDING_ERROR = "GROUNDING_ERROR"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    DENIED = "DENIED"
    SAP_ERROR = "SAP_ERROR"
    TIMEOUT = "TIMEOUT"
    LOOP_DETECTED = "LOOP_DETECTED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    ESCALATED = "ESCALATED"
    DONE = "DONE"


class GuiElement(BaseModel):
    id: str
    type: str = "GuiComponent"
    name: str = ""
    text: str = ""
    changeable: bool = False
    highlighted: bool = False
    tooltip: str = ""
    children: list[GuiElement] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    def collect_ids(self) -> set[str]:
        ids = {self.id} if self.id else set()
        for child in self.children:
            ids |= child.collect_ids()
        return ids

    def find(self, element_id: str) -> GuiElement | None:
        if self.id == element_id:
            return self
        for child in self.children:
            found = child.find(element_id)
            if found:
                return found
        return None


class ScreenSnapshot(BaseModel):
    tcode: str = ""
    program: str = ""
    screen_number: str = ""
    title: str = ""
    session_id: str = ""
    status_bar: str = ""
    elements: GuiElement
    captured_at: datetime = Field(default_factory=utcnow)
    degraded: bool = False
    notes: list[str] = Field(default_factory=list)

    def element_ids(self) -> set[str]:
        return self.elements.collect_ids()

    def has_element(self, element_id: str) -> bool:
        return element_id in self.element_ids()


class SapMessage(BaseModel):
    msgty: str = ""  # E/W/I/S/A
    msgid: str = ""
    msgno: str = ""
    msgv1: str = ""
    msgv2: str = ""
    msgv3: str = ""
    msgv4: str = ""
    short_text: str = ""
    long_text: str = ""
    raw_status_bar: str = ""

    @property
    def signature(self) -> str:
        return f"{self.msgid}/{self.msgno}"

    @property
    def is_error(self) -> bool:
        return self.msgty.upper() in {"E", "A", "X"}


class Action(BaseModel):
    type: ActionType
    target: str = ""
    value: str = ""
    expect: str = ""
    channel: Channel | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class PlannedStep(BaseModel):
    assessment: str
    gap: str
    action: Action
    justification_ref: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("justification_ref")
    @classmethod
    def non_empty_justification(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("justification_ref is mandatory")
        return v.strip()


class Observation(BaseModel):
    status: ObservationStatus
    message: str = ""
    screen: ScreenSnapshot | None = None
    sap_message: SapMessage | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    policy_reason: str = ""
    timestamp: datetime = Field(default_factory=utcnow)


class CriticVerdict(str, Enum):
    APPROVE = "APPROVE"
    REVISE = "REVISE"
    BLOCK = "BLOCK"


class CriticResult(BaseModel):
    verdict: CriticVerdict
    reasons: list[str] = Field(default_factory=list)


class TerminalOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    HARD_FAIL = "HARD_FAIL"
    ESCALATE = "ESCALATE"
    RUNNING = "RUNNING"


class BudgetState(BaseModel):
    max_steps: int = 80
    max_wall_seconds: int = 1800
    max_tokens: int = 500_000
    max_sap_round_trips: int = 200
    max_remediation_per_signature: int = 2
    steps_used: int = 0
    wall_seconds_used: float = 0.0
    tokens_used: int = 0
    sap_round_trips: int = 0
    remediation_counts: dict[str, int] = Field(default_factory=dict)

    def remaining_steps(self) -> int:
        return max(0, self.max_steps - self.steps_used)


class ConfigDiff(BaseModel):
    table: str
    key: dict[str, str]
    field: str
    before: str | None
    after: str | None
    business_justification: str = ""
    transport: str = "SAPILOT_AUTOCFG"
    reversal_script: str = ""


class EvidencePack(BaseModel):
    run_id: str
    goal: str
    tier: Tier
    outcome: TerminalOutcome
    reguv_status: str | None = None
    regup_count: int | None = None
    fi_documents: list[str] = Field(default_factory=list)
    config_diffs: list[ConfigDiff] = Field(default_factory=list)
    exceptions_before: list[dict[str, Any]] = Field(default_factory=list)
    exceptions_after: list[dict[str, Any]] = Field(default_factory=list)
    remediation_steps: int = 0
    elapsed_seconds: float = 0.0
    notes: list[str] = Field(default_factory=list)
    table_evidence: dict[str, Any] = Field(default_factory=dict)


class DiagnosisFinding(BaseModel):
    entity_type: str  # vendor | item | config | run
    entity_key: dict[str, str]
    symptom: str
    cause_table: str
    cause_key: dict[str, str]
    cause_field: str
    current_value: str | None
    recommended_value: str | None
    confidence: float = 0.8
    message_signature: str = ""
    remediation: str = ""
    severity: Literal["blocker", "warning", "info"] = "blocker"


class DiagnosisReport(BaseModel):
    company_code: str
    payment_method: str
    run_date: str | None = None
    run_id: str | None = None
    findings: list[DiagnosisFinding] = Field(default_factory=list)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    vendors_checked: list[str] = Field(default_factory=list)
    summary: str = ""
    generated_at: datetime = Field(default_factory=utcnow)
