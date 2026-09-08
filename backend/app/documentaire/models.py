from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
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
    confidentialite = Column(String(50), nullable=True)
    contenu = Column(Text, nullable=True)
    verrouille = Column(Boolean, nullable=False, default=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    service = relationship("Service")
    assignments = relationship("DocumentAssignment", back_populates="document")


class DocumentAssignment(Base):
    __tablename__ = "document_assignments"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_document = Column(String(20), nullable=False)

    document = relationship("Document", back_populates="assignments")
    user = relationship("User")


class DocumentRequest(Base):
    __tablename__ = "document_requests"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    nature = Column(String(20), nullable=False)
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


class DocumentTemplate(Base):
    __tablename__ = "document_templates"

    id = Column(Integer, primary_key=True)
    type_document = Column(String(100), nullable=False)
    nom = Column(String(150), nullable=False)
    contenu_structure = Column(Text, nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)


class DocumentComment(Base):
    __tablename__ = "document_comments"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    contenu = Column(Text, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document")
    user = relationship("User")


class DocumentSignature(Base):
    __tablename__ = "document_signatures"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_signataire = Column(String(20), nullable=False)
    nom_signature = Column(String(150), nullable=False)
    hash_contenu = Column(String(64), nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document")
    user = relationship("User")


class ValidationCircuit(Base):
    """Config : pour un type de document donné, quelles directions doivent
    valider. Ex: type_document='procedure', role_direction='direction_medicale'."""

    __tablename__ = "validation_circuits"

    id = Column(Integer, primary_key=True)
    type_document = Column(String(100), nullable=False)
    role_direction = Column(String(50), nullable=False)


class DocumentValidation(Base):
    """Une signature de validation par une direction, sur un document précis."""

    __tablename__ = "document_validations"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_direction = Column(String(50), nullable=False)
    nom_signature = Column(String(150), nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document")
    user = relationship("User")