from typing import Optional

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""
    confirm_password: Optional[str] = None  # defaults to `password` if the form has no confirm field


class LoginIn(BaseModel):
    email: str = ""
    password: str = ""


# Same bounds as the Streamlit widgets in profile_page().
class ProfileIn(BaseModel):
    cgpa: float = Field(ge=0.0, le=10.0)
    communication: int = Field(ge=1, le=10)
    logical_reasoning: int = Field(ge=1, le=10)
    projects_count: int = Field(ge=0, le=50)
    certifications_count: int = Field(ge=0, le=50)
    internship_count: int = Field(ge=0, le=10)
    interest_domain: str = ""


class CareerSelectIn(BaseModel):
    use_ai: bool = False
    career: Optional[str] = None
