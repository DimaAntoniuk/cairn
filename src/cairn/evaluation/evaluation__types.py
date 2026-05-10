from pydantic import BaseModel


class ContradictionResponse(BaseModel):
    contradicts: bool
    explanation: str = ""


__all__ = ["ContradictionResponse"]
