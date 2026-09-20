from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.auth import LoginRequest


class UserCreate(LoginRequest):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128, repr=False)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime


RoleName = Literal["employee", "data_analyst", "security_engineer", "admin"]


class EmployeeCreate(UserCreate):
    role: RoleName = "employee"


class EmployeeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: RoleName
    is_active: bool


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128, repr=False)
    new_password: str = Field(min_length=8, max_length=128, repr=False)
