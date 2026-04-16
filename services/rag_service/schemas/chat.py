from pydantic import BaseModel, Field
from typing import Optional

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)

class LoginRequest(BaseModel):
    email: str
    password: str

class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    session_id: Optional[str] = None
    is_incognito: bool = False

class EditMessageRequest(BaseModel):
    message_id: int
    new_content: str

class FeedbackRequest(BaseModel):
    message_id: int
    feedback_type: str

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    is_incognito: bool = False
