from datetime import datetime

from pydantic import BaseModel


class AdverseEventCreate(BaseModel):
    date_evenement: datetime
    lieu: str
    service_id: int
    professionnel_identifiant: str | None = None
    contact_professionnel: str | None = None
    categorie: list[str]
    description: str
    gravite: str  # "mineur", "majeur", "grave"
    actions_immediates: str | None = None
    personnes_impliquees: str | None = None
    pieces_jointes: list[str] | None = None

class MajorCompletionRequest(BaseModel):
    signalement_effectue_a: list[str]
    visa: str


class AdverseEventOut(BaseModel):
    id: int
    numero_suivi: str
    date_evenement: datetime
    lieu: str
    service_nom: str
    professionnel_identifiant: str | None
    contact_professionnel: str | None
    categorie: list[str] | None
    description: str
    personnes_impliquees: str | None
    gravite: str
    actions_immediates: str | None
    signalement_effectue_a: list[str] | None
    visa_major: str | None
    declarant_email: str
    statut: str
    date_declaration: datetime
    pieces_jointes: list[str] | None

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
class ActionCreate(BaseModel):
    description: str
    responsable_email: str
    echeance: datetime
    priorite: str  # "basse", "moyenne", "haute"
    criticite: str  # "mineure", "majeure", "critique"


class ActionStatusUpdate(BaseModel):
    statut: str  # "a_faire", "en_cours", "realisee"


class ActionOut(BaseModel):
    id: int
    event_id: int
    description: str
    responsable_email: str
    echeance: datetime
    priorite: str
    criticite: str
    statut: str
    date_creation: datetime

    class Config:
        from_attributes = True

class EfficacyEvaluationRequest(BaseModel):
    contenu: str


class DashboardEIOut(BaseModel):
    total_evenements: int
    taux_cloture: float
    delai_moyen_jours: float
    repartition_gravite: dict
    repartition_par_service: dict
    tendance_mensuelle: list