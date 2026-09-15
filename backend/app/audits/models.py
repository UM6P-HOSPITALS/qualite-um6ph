from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditProgram(Base):
    __tablename__ = "audit_programs"

    id = Column(Integer, primary_key=True)
    annee = Column(Integer, nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    processus = Column(String(255), nullable=True)
    thematique = Column(String(255), nullable=True)
    responsable_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date_debut_prevue = Column(Date, nullable=False)
    date_fin_prevue = Column(Date, nullable=False)
    statut = Column(String(20), nullable=False, default="planifie")
    notes = Column(Text, nullable=True)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)
    rapport_verrouille = Column(Boolean, nullable=False, default=False)
    date_cloture = Column(DateTime, nullable=True)

    service = relationship("Service")
    responsable = relationship("User")


class AuditGrid(Base):
    """Grille de critères pour un programme d'audit précis. Créée par
    Qualité, ses critères sont ensuite remplis par l'auditeur."""

    __tablename__ = "audit_grids"

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("audit_programs.id"), nullable=False)
    nom = Column(String(255), nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    program = relationship("AuditProgram")


class AuditGridCriteria(Base):
    """Un critère scorable de la grille, avec sa pondération (points)."""

    __tablename__ = "audit_grid_criteria"

    id = Column(Integer, primary_key=True)
    grid_id = Column(Integer, ForeignKey("audit_grids.id"), nullable=False)
    libelle = Column(String(500), nullable=False)
    ponderation = Column(Integer, nullable=False)  # points, la somme des critères d'une grille définit le total


class AuditFinding(Base):
    """Le constat de l'auditeur sur un critère précis de la grille."""

    __tablename__ = "audit_findings"

    id = Column(Integer, primary_key=True)
    grid_id = Column(Integer, ForeignKey("audit_grids.id"), nullable=False)
    criteria_id = Column(Integer, ForeignKey("audit_grid_criteria.id"), nullable=False)
    conforme = Column(Boolean, nullable=False)
    classification = Column(String(20), nullable=True)  # "mineure", "majeure", "critique" — si non conforme
    observation = Column(Text, nullable=True)
    preuves = Column(JSON, nullable=True)  # noms de fichiers (photos)
    auteur_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    auteur = relationship("User")

class AuditAction(Base):
    """Action corrective liée à une non-conformité relevée sur un
    critère précis de la grille."""

    __tablename__ = "audit_actions"

    id = Column(Integer, primary_key=True)
    finding_id = Column(Integer, ForeignKey("audit_findings.id"), nullable=False)
    description = Column(Text, nullable=False)
    responsable_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    echeance = Column(Date, nullable=False)
    statut = Column(String(20), nullable=False, default="a_faire")  # a_faire, en_cours, realisee
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    finding = relationship("AuditFinding")
    responsable = relationship("User")