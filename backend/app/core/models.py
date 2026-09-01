import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    # Auth classique pour l'instant (email/mot de passe). Nullable car on
    # basculera plus tard vers Microsoft Entra ID, où il n'y aura pas de mot
    # de passe stocké chez nous.
    password_hash = Column(String(255), nullable=True)
    actif = Column(Boolean, default=True, nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow, nullable=False)

    roles = relationship("UserRole", back_populates="user")


class Site(Base):
    __tablename__ = "sites"

    id = Column(Integer, primary_key=True)
    nom = Column(String(150), unique=True, nullable=False)

    services = relationship("Service", back_populates="site")


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    nom = Column(String(150), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)

    site = relationship("Site", back_populates="services")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    nom = Column(String(50), unique=True, nullable=False)


class UserRole(Base):
    """Un utilisateur peut avoir plusieurs lignes ici : un même user peut être
    rédacteur sur le Service A ET vérificateur sur le Service B, par exemple."""

    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    # Nullable : certains rôles (ex: direction_generale) ne sont pas liés à
    # un service précis.
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)

    user = relationship("User", back_populates="roles")
    role = relationship("Role")
    service = relationship("Service")


class ObjectType(str, enum.Enum):
    document = "document"
    event = "event"
    audit = "audit"


class StatusHistory(Base):
    """Table générique réutilisée par les 3 modules métier : chaque
    changement de statut d'un document, d'un événement ou d'un audit
    laisse une trace ici."""

    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True)
    object_type = Column(Enum(ObjectType), nullable=False)
    object_id = Column(Integer, nullable=False)
    ancien_statut = Column(String(100), nullable=True)
    nouveau_statut = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    commentaire = Column(Text, nullable=True)

    user = relationship("User")


class Permission(Base):
    """Permissions configurables par rôle/module/action — pas de droits
    codés en dur dans le code. Ex: role_id=qualite, module="documentaire",
    action="publish", autorise=True."""

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    module = Column(String(50), nullable=False)  # "documentaire", "evenements", "audits", "admin"
    action = Column(String(50), nullable=False)  # "create", "read", "publish", "manage_users"...
    autorise = Column(Boolean, default=True, nullable=False)

    role = relationship("Role")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    titre = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    lien = Column(String(500), nullable=True)
    lu = Column(Boolean, default=False, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
