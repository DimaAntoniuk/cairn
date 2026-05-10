from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .entity__types import Confidence
from .shared__utils import _new_id, _utcnow
from .source__types import SourceRef


class ExtractedFact(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("fact"))
    fact_type: Literal["entity", "relationship", "attribute", "decision", "constraint"]
    payload: dict[str, Any]
    source_ref: SourceRef
    confidence: Confidence
    extracted_at: datetime = Field(default_factory=_utcnow)


__all__ = ["ExtractedFact"]
