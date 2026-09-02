from datetime import datetime

from pydantic import BaseModel, EmailStr


class DocumentRequestCreate(BaseModel):
    intitule: str
    nature: str  # "creation" ou "modification"
    type_document: str
    justification: str
    service_id: int
    responsable_email: EmailStr
    pieces_jointes: list[str] | None = None


class DocumentRequestOut(BaseModel):
    id: int
    document_id: int
    nature: str
    justification: str
    statut: str
    date: datetime

    class Config:
        from_attributes = True


class ServiceOut(BaseModel):
    id: int
    nom: str
    site_id: int

    class Config:
        from_attributes = True
