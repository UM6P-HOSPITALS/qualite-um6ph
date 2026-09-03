from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    intitule = Column(String(255), nullable=False)
    type_document = Column(String(100), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    statut = Column(String(50), nullable=False, default="en_attente_examen")
    version_courante = Column(Integer, nullable=False, default=1)
    perimetre = Column(Text, nullable=True)
    confidentialite = Column(String(50), nullable=True)  # "public", "restreint", "confidentiel"
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service")
    assignments = relationship("DocumentAssignment", back_populates="document")


class DocumentAssignment(Base):
    """Un rédacteur, vérificateur ou approbateur assigné à un document.
    Plusieurs lignes possibles par document (ex: 2 vérificateurs)."""

    __tablename__ = "document_assignments"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_document = Column(String(20), nullable=False)  # "redacteur", "verificateur", "approbateur"

    document = relationship("Document", back_populates="assignments")
    user = relationship("User")


class DocumentRequest(Base):
    __tablename__ = "document_requests"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    nature = Column(String(20), nullable=False)  # "creation" ou "modification"
    justification = Column(Text, nullable=False)
    demandeur_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    responsable_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    statut = Column(String(50), nullable=False, default="en_attente_examen")
    pieces_jointes = Column(JSON, nullable=True)
    motif_rejet = Column(Text, nullable=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document")
    demandeur = relationship("User", foreign_keys=[demandeur_id])
    responsable = relationship("User", foreign_keys=[responsable_id])