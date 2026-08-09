"""
schemas.py
Pydantic schemas for creating and returning Users and Notes.
"""
from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


# ---------- User ----------

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must not be empty or whitespace-only")
        return v


class UserOut(BaseModel):
    # NOTE: password is intentionally excluded from the response schema.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    created_at: datetime


# ---------- Note ----------

class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)
    tag: Optional[str] = None
    owner_id: int


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    content: Optional[str] = Field(default=None, min_length=1)
    tag: Optional[str] = None


class AISuggestion(BaseModel):
    tags: List[str]
    summary: str


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    tag: Optional[str] = None
    owner_id: int
    created_at: datetime


class NoteCreateResponse(NoteOut):
    ai_suggestion: Optional[AISuggestion] = None