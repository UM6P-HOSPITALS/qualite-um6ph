from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class AdverseEvent(Base):
    __tablename__ = "adverse_events"

    id = Column(Integer, primary_key=True)
    numero_suivi = Column(String(30), unique=True, nullable=False)

    date_evenement = Column(DateTime, nullable=False)
    lieu = Column(String(255), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    professionnel_identifiant = Column(String(255), nullable=True)
    contact_professionnel = Column(String(255), nullable=True)

    categorie = Column(JSON, nullable=True)
    description = Column(Text, nullable=False)
    gravite = Column(String(20), nullable=False)

    actions_immediates = Column(Text, nullable=True)

    signalement_effectue_a = Column(JSON, nullable=True)
    visa_major = Column(String(150), nullable=True)
    date_completion_major = Column(DateTime, nullable=True)

    efficacite_evaluee = Column(Boolean, nullable=False, default=False)
    evaluation_efficacite = Column(Text, nullable=True)
    date_cloture = Column(DateTime, nullable=True)

    personnes_impliquees = Column(Text, nullable=True)
    declarant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pieces_jointes = Column(JSON, nullable=True)
    statut = Column(String(50), nullable=False, default="declare")
    date_declaration = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service")
    declarant = relationship("User")


class AdverseEventAnalyst(Base):
    """Un analyste désigné par Qualité pour un événement précis — pas de
    rôle fixe, désignation au cas par cas."""

    __tablename__ = "adverse_event_analysts"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("adverse_events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date_assignation = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdverseEventAnalysisEntry(Base):
    """Traçabilité de l'analyse : chaque contribution horodatée, plutôt
    qu'un seul champ texte écrasé à chaque modification."""

    __tablename__ = "adverse_event_analysis_entries"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("adverse_events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    contenu = Column(Text, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")


class AdverseEventAction(Base):
    """Une action corrective/préventive associée à un événement indésirable."""

    __tablename__ = "adverse_event_actions"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("adverse_events.id"), nullable=False)
    description = Column(Text, nullable=False)
    responsable_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    echeance = Column(DateTime, nullable=False)
    priorite = Column(String(20), nullable=False)
    criticite = Column(String(20), nullable=False)
    statut = Column(String(20), nullable=False, default="a_faire")
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    event = relationship("AdverseEvent")
    responsable = relationship("User")