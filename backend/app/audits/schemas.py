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
    rapport_verrouille: bool
    date_creation: datetime

    class Config:
        from_attributes = True


class AssignResponsableRequest(BaseModel):
    responsable_email: str


class AuditGridCriteriaCreate(BaseModel):
    libelle: str
    ponderation: int


class AuditGridCreate(BaseModel):
    program_id: int
    nom: str
    criteres: list[AuditGridCriteriaCreate]


class AuditGridCriteriaOut(BaseModel):
    id: int
    libelle: str
    ponderation: int

    class Config:
        from_attributes = True


class AuditGridOut(BaseModel):
    id: int
    program_id: int
    nom: str
    criteres: list[AuditGridCriteriaOut]
    date_creation: datetime


class FindingCreate(BaseModel):
    criteria_id: int
    conforme: bool
    classification: str | None = None
    observation: str | None = None
    preuves: list[str] | None = None


class FindingOut(BaseModel):
    id: int
    criteria_id: int
    criteria_libelle: str
    conforme: bool
    classification: str | None
    observation: str | None
    preuves: list[str] | None
    auteur_email: str
    date_creation: datetime

    class Config:
        from_attributes = True


class ConformiteOut(BaseModel):
    grid_id: int
    points_obtenus: int
    points_total: int
    taux_conformite: float
    nb_criteres_evalues: int
    nb_criteres_total: int

class AuditActionCreate(BaseModel):
    description: str
    responsable_email: str
    echeance: date


class AuditActionStatusUpdate(BaseModel):
    statut: str


class AuditActionOut(BaseModel):
    id: int
    finding_id: int
    description: str
    responsable_email: str
    echeance: date
    statut: str
    date_creation: datetime

    class Config:
        from_attributes = True

class DashboardAuditOut(BaseModel):
    total_programmes: int
    taux_realisation: float
    repartition_statuts: dict
    total_non_conformites: int
    repartition_non_conformites: dict
    taux_conformite_moyen: float
    repartition_par_service: dict