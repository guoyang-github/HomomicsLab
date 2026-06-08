from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid as _uuid


def utc_now():
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_HUMAN = "awaiting_human"
    ABORTED = "aborted"


class MessageType(str, Enum):
    TEXT = "text"
    TODO_LIST = "todo_list"
    HITL_REQUEST = "hitl_request"
    TOOL_CALL = "tool_call"
    RESULT_PREVIEW = "result_preview"
    PARAMETER_FORM = "parameter_form"
    FILE_REFERENCE = "file_reference"
    ERROR = "error"
    SYSTEM = "system"


class AgentType(str, Enum):
    PLANNER = "planner"
    BIOINFO = "bioinfo"
    VIZ = "viz"
    EXPERIMENT = "experiment"
    QA = "qa"
    REPORT = "report"


class HITLTrigger(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    HIGH_COST = "high_cost"
    HIGH_RISK = "high_risk"
    POLICY = "policy"
    ANOMALY = "anomaly"


class Option(BaseModel):
    id: str
    label: str
    description: Optional[str] = None


class HITLCheckpoint(BaseModel):
    id: str = Field(default_factory=lambda: str(_uuid.uuid4()))
    trigger_reason: HITLTrigger
    context_summary: str
    options: list[Option]
    default_option: Optional[Option] = None
    timeout_minutes: int = 60 * 24


class ChatMessage(BaseModel):
    id: str
    type: MessageType = MessageType.TEXT
    content: Any
    sender: str
    timestamp: datetime = Field(default_factory=utc_now)
    task_id: Optional[str] = None
    skill_id: Optional[str] = None
    related_files: list[str] = Field(default_factory=list)


class AgentMessage(BaseModel):
    from_agent: str
    to_agent: Optional[str] = None
    content: str
    timestamp: datetime = Field(default_factory=utc_now)
