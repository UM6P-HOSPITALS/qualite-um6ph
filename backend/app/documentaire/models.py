from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
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
    date_diffusion = Column(DateTime, nullable=True)

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
    __tablename__ = "validation_circuits"

    id = Column(Integer, primary_key=True)
    type_document = Column(String(100), nullable=False)
    role_direction = Column(String(50), nullable=False)


class DocumentValidation(Base):
    __tablename__ = "document_validations"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_direction = Column(String(50), nullable=False)
    nom_signature = Column(String(150), nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document")
    user = relationship("User")


class DocumentRead(Base):
    """Accusé de lecture : une ligne par (document, utilisateur). Rouvrir
    le même document ne crée pas de doublon (upsert dans l'endpoint)."""

    __tablename__ = "document_reads"
    __table_args__ = (UniqueConstraint("document_id", "user_id", name="uq_document_read_user"),)

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document")
    user = relationship("User")