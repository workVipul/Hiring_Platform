from dataclasses import dataclass
from typing import Literal

Operator = Literal["and", "or"]


@dataclass(frozen=True)
class CriteriaCondition:
    field: str
    operator: str
    value: str

    def serialize(self) -> str:
        return f"(({self.field}:{self.operator}:{escape_criteria_value(self.value)}))"


@dataclass(frozen=True)
class CriteriaGroup:
    operator: Operator
    children: list["CriteriaNode"]

    def serialize(self) -> str:
        serialized = [child.serialize() for child in self.children if child.serialize()]
        if not serialized:
            return ""
        if len(serialized) == 1:
            return serialized[0]
        return "(" + self.operator.join(serialized) + ")"


CriteriaNode = CriteriaCondition | CriteriaGroup


def and_group(*children: CriteriaNode | None) -> CriteriaGroup:
    return CriteriaGroup("and", [child for child in children if child is not None])


def or_group(*children: CriteriaNode | None) -> CriteriaGroup:
    return CriteriaGroup("or", [child for child in children if child is not None])


def contains(field: str, value: str | None) -> CriteriaCondition | None:
    if not value or not str(value).strip():
        return None
    return CriteriaCondition(field=field, operator="contains", value=str(value).strip())


def greater_or_equal(field: str, value: float | int | None) -> CriteriaCondition | None:
    if value is None:
        return None
    return CriteriaCondition(field=field, operator="greater_equal", value=f"{value:g}")


def less_or_equal(field: str, value: float | int | None) -> CriteriaCondition | None:
    if value is None:
        return None
    return CriteriaCondition(field=field, operator="less_equal", value=f"{value:g}")


def escape_criteria_value(value: str) -> str:
    return str(value).replace("(", " ").replace(")", " ").strip()


def serialize_criteria(node: CriteriaNode | None) -> str:
    return node.serialize() if node else ""
