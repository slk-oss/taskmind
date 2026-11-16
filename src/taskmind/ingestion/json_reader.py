import json
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from taskmind.domain.events import Event, EventResult, EventType


REQUIRED_FIELDS = {
    "schema_version",
    "event_id",
    "timestamp",
    "sequence_number",
    "user_id",
    "session_id",
    "case_id",
    "application",
    "event_type",
    "element_id",
    "element_text",
    "result",
}

STRING_FIELDS = {
    "event_id",
    "timestamp",
    "user_id",
    "session_id",
    "case_id",
    "application",
    "event_type",
    "element_id",
    "element_text",
    "result",
}

EVENT_TYPES = {"click", "input", "navigate", "export"}
EVENT_RESULTS = {"success", "failure", "unknown"}


def parse_event(record: object) -> Event:
    """Validate one JSON record and convert it into an event."""
    if not isinstance(record, dict):
        raise ValueError("expected a JSON object")

    missing = REQUIRED_FIELDS - record.keys()
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")

    unknown = record.keys() - REQUIRED_FIELDS
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")

    for field in STRING_FIELDS:
        value = record[field]

        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")

        if field != "element_text" and not value.strip():
            raise ValueError(f"{field} must not be empty")

    # bool is a subclass of int, so use an exact type check here.
    if type(record["schema_version"]) is not int:
        raise ValueError("schema_version must be an integer")

    if record["schema_version"] != 1:
        raise ValueError("unsupported schema_version")

    sequence_number = record["sequence_number"]
    if type(sequence_number) is not int or sequence_number < 0:
        raise ValueError("sequence_number must be a non-negative integer")

    if record["event_type"] not in EVENT_TYPES:
        raise ValueError("unsupported event_type")

    if record["result"] not in EVENT_RESULTS:
        raise ValueError("unsupported result")

    try:
        timestamp = datetime.fromisoformat(record["timestamp"])
    except ValueError as error:
        raise ValueError("timestamp must be a valid ISO 8601 datetime") from error

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")

    return Event(
        schema_version=record["schema_version"],
        event_id=record["event_id"],
        timestamp=timestamp.astimezone(timezone.utc),
        sequence_number=sequence_number,
        user_id=record["user_id"],
        session_id=record["session_id"],
        case_id=record["case_id"],
        application=record["application"],
        event_type=cast(EventType, record["event_type"]),
        element_id=record["element_id"],
        element_text=record["element_text"],
        result=cast(EventResult, record["result"]),
    )


def read_events(path: Path) -> list[Event]:
    """Read a non-empty event log and validate dataset-level constraints."""
    with path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError("event log must be a JSON array")

    if not records:
        raise ValueError("event log must not be empty")

    events: list[Event] = []
    event_ids: set[str] = set()
    session_positions: set[tuple[str, int]] = set()
    case_owners: dict[str, tuple[str, str]] = {}

    for record_number, record in enumerate(records, start=1):
        try:
            event = parse_event(record)

            if event.event_id in event_ids:
                raise ValueError(f"duplicate event_id: {event.event_id}")

            position = (event.session_id, event.sequence_number)
            if position in session_positions:
                raise ValueError("duplicate sequence_number within a session")

            owner = (event.user_id, event.session_id)
            if event.case_id in case_owners:
                if case_owners[event.case_id] != owner:
                    raise ValueError("case_id belongs to multiple users or sessions")

        except ValueError as error:
            raise ValueError(f"record {record_number}: {error}") from error

        event_ids.add(event.event_id)
        session_positions.add(position)
        case_owners[event.case_id] = owner
        events.append(event)

    return events