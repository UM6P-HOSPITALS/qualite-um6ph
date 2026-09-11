from datetime import datetime

from pydantic import BaseModel


class AdverseEventCreate(BaseModel):
    date_evenement: datetime
    lieu: str
    service_id: int
    description: str
    personnes_impliquees: str | None = None
    gravite: str  # "mineure", "majeure", "critique"
    actions_immediates: str | None = None
    pieces_jointes: list[str] | None = None


class AdverseEventOut(BaseModel):
    id: int
    numero_suivi: str
    date_evenement: datetime
    lieu: str
    service_nom: str
    description: str
    personnes_impliquees: str | None
    gravite: str
    actions_immediates: str | None
    declarant_email: str
    statut: str
    date_declaration: datetime
    pieces_jointes: list[str] | None = None

    class Config:
        from_attributes = True

class AssignAnalystsRequest(BaseModel):
    analyst_emails: list[str]


class AnalystOut(BaseModel):
    user_email: str
    date_assignation: datetime

    class Config:
        from_attributes = True


class AnalysisEntryCreate(BaseModel):
    contenu: str


class AnalysisEntryOut(BaseModel):
    id: int
    user_email: str
    contenu: str
    date: datetime

    class Config:
        from_attributes = True