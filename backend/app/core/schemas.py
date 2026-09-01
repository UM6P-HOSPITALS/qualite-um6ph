from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    email: EmailStr
    nom: str
    prenom: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleOut(BaseModel):
    nom: str
    service: str | None = None

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    email: str
    nom: str
    prenom: str
    actif: bool

    class Config:
        from_attributes = True
