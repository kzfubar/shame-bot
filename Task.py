from typing import List, TypedDict


class Label(TypedDict):
    id: int
    name: str


class DueOptions(TypedDict):
    string: str
    date: str


class Task(TypedDict, total=False):
    id: int
    content: str
    due: DueOptions
    labels: List[str]
