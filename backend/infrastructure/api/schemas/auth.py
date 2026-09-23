from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.domain.enums import UserRole


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class StaffResponse(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: UserRole


class CreateBuyerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    username: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9][A-Za-z0-9._@+-]*$")
    display_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("display_name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Display name must not be blank")
        return value.strip()


class RoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: UserRole
