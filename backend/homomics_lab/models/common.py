import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
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
    PLAN_REQUEST = "plan_request"
    DEBATE_REQUEST = "debate_request"
    TOOL_CALL = "tool_call"
    RESULT_PREVIEW = "result_preview"
    PARAMETER_FORM = "parameter_form"
    FILE_REFERENCE = "file_reference"
    PLOT = "plot"
    PLOT_DATA = "plot_data"
    ERROR = "error"
    SYSTEM = "system"


class AgentType(str, Enum):
    PLANNER = "planner"
    BIOINFO = "bioinfo"
    VIZ = "viz"
    EXPERIMENT = "experiment"
    QA = "qa"
    REPORT = "report"
    SUPERVISOR = "supervisor"
    WORKER = "worker"
    REVIEWER = "reviewer"


class HITLTrigger(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    HIGH_COST = "high_cost"
    HIGH_RISK = "high_risk"
    POLICY = "policy"
    ANOMALY = "anomaly"
    PHASE_GATE_FAIL = "phase_gate_fail"
    REVIEWER_REJECT = "reviewer_reject"
    WORKER_FAILURE = "worker_failure"


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
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    id: str
    type: MessageType = MessageType.TEXT
    content: Any
    sender: str
    timestamp: datetime = Field(default_factory=utc_now)
    task_id: Optional[str] = None
    skill_id: Optional[str] = None
    related_files: list[str] = Field(default_factory=list)


@dataclass
class PlotAttachment:
    """A plot attachment that can be embedded into chat messages.

    Supports two rendering modes:
    - plot_data: interactive Plotly JSON (rendered by react-plotly.js)
    - image_base64: static PNG image (rendered as <img>)
    - file_path: path to image file in workspace (converted to base64 on demand)
    """

    plot_type: str
    title: str
    caption: str = ""
    data: Optional[Dict[str, Any]] = None          # plot_data mode
    image_base64: Optional[str] = None             # plot mode
    file_path: Optional[str] = None                # lazy conversion mode

    def to_chat_content(self) -> Dict[str, Any]:
        """Convert to content dict for ChatMessage."""
        if self.data:
            return {
                "plot_type": self.plot_type,
                "title": self.title,
                "caption": self.caption,
                "data": self.data,
            }
        elif self.image_base64:
            return {
                "plot_type": self.plot_type,
                "title": self.title,
                "caption": self.caption,
                "image_base64": self.image_base64,
            }
        elif self.file_path:
            return {
                "plot_type": self.plot_type,
                "title": self.title,
                "caption": self.caption,
                "image_base64": self._file_to_base64(self.file_path),
            }
        else:
            return {
                "plot_type": self.plot_type,
                "title": self.title,
                "caption": self.caption,
            }

    @staticmethod
    def _file_to_base64(file_path: str) -> Optional[str]:
        """Convert an image file to base64 string."""
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            return base64.b64encode(path.read_bytes()).decode("utf-8")
        except Exception:
            return None


class AgentMessage(BaseModel):
    from_agent: str
    to_agent: Optional[str] = None
    content: str
    timestamp: datetime = Field(default_factory=utc_now)
