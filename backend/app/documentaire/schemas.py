from datetime import datetime

from pydantic import BaseModel, EmailStr


class DocumentRequestCreate(BaseModel):
    intitule: str
    nature: str
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


class DocumentRequestPendingOut(BaseModel):
    id: int
    document_id: int
    intitule: str
    nature: str
    type_document: str
    justification: str
    demandeur_email: str
    date: datetime

    class Config:
        from_attributes = True


class DocumentAcceptRequest(BaseModel):
    redacteur_emails: list[str]
    verificateur_emails: list[str]
    approbateur_emails: list[str] = []
    perimetre: str
    confidentialite: str


class DocumentRejectRequest(BaseModel):
    motif: str


class ServiceOut(BaseModel):
    id: int
    nom: str
    site_id: int

    class Config:
        from_attributes = True


class DocumentTemplateCreate(BaseModel):
    type_document: str
    nom: str
    contenu_structure: str


class DocumentTemplateOut(BaseModel):
    id: int
    type_document: str
    nom: str
    contenu_structure: str
    date_creation: datetime

    class Config:
        from_attributes = True


class DocumentTemplateUpdate(BaseModel):
    nom: str | None = None
    contenu_structure: str | None = None


class DraftSave(BaseModel):
    contenu: str


class DocumentDetailOut(BaseModel):
    id: int
    intitule: str
    type_document: str
    statut: str
    contenu: str | None
    perimetre: str | None
    confidentialite: str | None

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    contenu: str


class CommentOut(BaseModel):
    id: int
    user_email: str
    contenu: str
    date: datetime

    class Config:
        from_attributes = True


class SignatureConfirm(BaseModel):
    nom_signature: str
    password: str
    certification: bool


class SignatureOut(BaseModel):
    id: int
    user_email: str
    role_signataire: str
    nom_signature: str
    date: datetime

    class Config:
        from_attributes = True