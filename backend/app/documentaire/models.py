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
    document_parent_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    revision_notifiee = Column(Boolean, nullable=False, default=False)
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
class TrainingCapsule(Base):
    """Capsule vidéo de sensibilisation, liée à une procédure (document)."""

    __tablename__ = "training_capsules"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    titre = Column(String(255), nullable=False)
    url_video = Column(String(500), nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document")


class CapsuleView(Base):
    """Traçabilité : qui a visionné quelle capsule, et quand."""

    __tablename__ = "capsule_views"
    __table_args__ = (UniqueConstraint("capsule_id", "user_id", name="uq_capsule_view_user"),)

    id = Column(Integer, primary_key=True)
    capsule_id = Column(Integer, ForeignKey("training_capsules.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)


class Quiz(Base):
    """Un quiz par procédure, pour évaluer l'efficacité de la formation."""

    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    titre = Column(String(255), nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    question = Column(Text, nullable=False)
    choix = Column(JSON, nullable=False)  # liste de textes de réponses
    bonne_reponse_index = Column(Integer, nullable=False)


class QuizAttempt(Base):
    """Un résultat d'évaluation : une tentative par utilisateur par quiz."""

    __tablename__ = "quiz_attempts"
    __table_args__ = (UniqueConstraint("quiz_id", "user_id", name="uq_quiz_attempt_user"),)

    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Integer, nullable=False)  # nombre de bonnes réponses
    total = Column(Integer, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)


class AttendanceList(Base):
    """Liste de présence à une formation, liée à une procédure."""

    __tablename__ = "attendance_lists"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document")


class AttendanceParticipant(Base):
    __tablename__ = "attendance_participants"

    id = Column(Integer, primary_key=True)
    attendance_list_id = Column(Integer, ForeignKey("attendance_lists.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)