from datetime import date, datetime

from pydantic import BaseModel


class AuditProgramCreate(BaseModel):
    annee: int
    service_id: int | None = None
    processus: str | None = None
    thematique: str | None = None
    responsable_email: str
    date_debut_prevue: date
    date_fin_prevue: date
    notes: str | None = None


class AuditProgramUpdate(BaseModel):
    date_debut_prevue: date | None = None
    date_fin_prevue: date | None = None
    statut: str | None = None
    notes: str | None = None


class AuditProgramOut(BaseModel):
    id: int
    annee: int
    service_nom: str | None
    processus: str | None
    thematique: str | None
    responsable_email: str
    date_debut_prevue: date
    date_fin_prevue: date
    statut: str
    notes: str | None
    date_creation: datetime

    class Config:
        from_attributes = True


class AssignResponsableRequest(BaseModel):
    responsable_email: str