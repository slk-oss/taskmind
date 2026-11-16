from dataclasses import dataclass
from datetime import datetime
from typing import Literal


EventType = Literal["click", "input", "navigate", "export"]
EventResult = Literal["success", "failure", "unknown"]


@dataclass(frozen=True)
class Event:
    schema_version: int
    event_id: str
    timestamp: datetime
    sequence_number: int
    user_id: str
    session_id: str
    case_id: str
    application: str
    event_type: EventType
    element_id: str
    element_text: str
    result: EventResult