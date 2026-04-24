from pydantic import BaseModel, Field

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)

class LoginRequest(BaseModel):
    email: str
    password: str

