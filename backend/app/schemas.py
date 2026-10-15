from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class EventOut(BaseModel):
    id: int
    title: str
    description: str
    category: str
    location: str
    price: int
    total_tickets: int
    available_tickets: int
    popularity: int
    event_date: datetime
    model_config = ConfigDict(from_attributes=True)

class ProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    preferred_category: str | None = Field(default=None, max_length=80)
    profile_picture_url: str | None = Field(default=None, max_length=500)

class EventUpdateIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    important: bool = False

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
