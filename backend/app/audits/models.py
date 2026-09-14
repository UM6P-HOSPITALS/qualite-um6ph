from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditProgram(Base):
    """Programme d'audit annuel — un audit planifié pour un service, un
    processus ou une thématique précise. Modifiable en cours d'année."""

    __tablename__ = "audit_programs"

    id = Column(Integer, primary_key=True)
    annee = Column(Integer, nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    processus = Column(String(255), nullable=True)
    thematique = Column(String(255), nullable=True)
    responsable_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date_debut_prevue = Column(Date, nullable=False)
    date_fin_prevue = Column(Date, nullable=False)
    statut = Column(String(20), nullable=False, default="planifie")  # planifie, en_cours, realise
    notes = Column(Text, nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service")
    responsable = relationship("User")