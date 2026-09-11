from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class AdverseEvent(Base):
    __tablename__ = "adverse_events"

    id = Column(Integer, primary_key=True)
    numero_suivi = Column(String(30), unique=True, nullable=False)
    date_evenement = Column(DateTime, nullable=False)
    lieu = Column(String(255), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    description = Column(Text, nullable=False)
    personnes_impliquees = Column(Text, nullable=True)
    gravite = Column(String(20), nullable=False)  # "mineure", "majeure", "critique"
    actions_immediates = Column(Text, nullable=True)
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