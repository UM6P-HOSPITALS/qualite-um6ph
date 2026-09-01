from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Permission, Role, Service, User, UserRole
from app.core.permissions import require_permission

router = APIRouter()


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _=Depends(require_permission("admin", "manage_users")),
):
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "nom": u.nom,
            "prenom": u.prenom,
            "actif": u.actif,
            "roles": [
                {"role": ur.role.nom, "service": ur.service.nom if ur.service else None}
                for ur in u.roles
            ],
        }
        for u in users
    ]


@router.post("/users/{user_id}/roles", status_code=201)
def assign_role(
    user_id: int,
    role_nom: str,
    service_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("admin", "manage_users")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    role = db.query(Role).filter(Role.nom == role_nom).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Rôle inconnu : {role_nom}")

    if service_id is not None:
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service introuvable")

    user_role = UserRole(user_id=user_id, role_id=role.id, service_id=service_id)
    db.add(user_role)
    db.commit()
    return {"message": f"Rôle '{role_nom}' attribué à l'utilisateur {user_id}"}


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    _=Depends(require_permission("admin", "manage_permissions")),
):
    perms = db.query(Permission).all()
    return [
        {"id": p.id, "role": p.role.nom, "module": p.module, "action": p.action, "autorise": p.autorise}
        for p in perms
    ]


@router.post("/permissions", status_code=201)
def create_permission(
    role_nom: str,
    module: str,
    action: str,
    autorise: bool = True,
    db: Session = Depends(get_db),
    _=Depends(require_permission("admin", "manage_permissions")),
):
    role = db.query(Role).filter(Role.nom == role_nom).first()
    if not role:
        raise HTTPException(status_code=404, detail=f"Rôle inconnu : {role_nom}")

    perm = Permission(role_id=role.id, module=module, action=action, autorise=autorise)
    db.add(perm)
    db.commit()
    return {"message": f"Permission créée : {role_nom} peut '{action}' sur '{module}'"}
