from enum import Enum

from pydantic import BaseModel


class TimeUnit(str, Enum):
    minute = "minute"
    day = "day"


class Due(BaseModel):
    date: str
    is_recurring: bool
    string: str

    datetime: str | None = None
    timezone: str | None = None


class Duration(BaseModel):
    amount: int
    unit: TimeUnit


class Task(BaseModel):
    assignee_id: str | None
    assigner_id: str | None
    comment_count: int
    is_completed: bool
    content: str
    created_at: str
    creator_id: str
    description: str
    due: Due | None
    id: str
    labels: list[str] | None
    order: int
    parent_id: str | None
    priority: int
    project_id: str
    section_id: str | None
    url: str
    duration: Duration | None
    sync_id: str | None = None


class Label(BaseModel):
    id: str
    name: str
    color: str
    order: int
    is_favorite: bool


class Filter:
    def __init__(
        self,
        filter_str: str | None = None,
        label: str | None = None,
        assigned_self: bool = False,
    ) -> None:
        filter_items = []
        if filter_str is not None:
            filter_items.append(filter_str)

        if label is not None:
            filter_items.append(f"@{label}")

        if assigned_self:
            filter_items.append("!(assigned to: others & assigned)")

        self.filter = " & ".join(filter_items)

    def __str__(self) -> str:
        return self.filter

    def __invert__(self) -> "Filter":
        return Filter(f"!({self.filter})")

    def __and__(self, other: "Filter") -> "Filter":
        return Filter(f"({self.filter} & {other.filter})")

    def __or__(self, other: "Filter") -> "Filter":
        return Filter(f"({self.filter} | {other.filter})")
