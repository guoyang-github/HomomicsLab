"""Shared API response models used across routers.

These are intentionally small and generic so that endpoints which only
return a status/message/id do not need to define their own models.
"""

from typing import Any, Dict, List, TypeVar, Generic

from pydantic import BaseModel


class StatusResponse(BaseModel):
    status: str


class MessageResponse(BaseModel):
    message: str


class IdResponse(BaseModel):
    id: str


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    items: List[T]


class CountResponse(BaseModel):
    count: int


class GenericResponse(BaseModel):
    """Fallback for endpoints that return a heterogeneous JSON object."""

    data: Dict[str, Any]
