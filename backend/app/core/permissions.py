from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Permission, User
from app.core.security import get_current_user


def require_permission(module: str, action: str):
    """Fabrique une dépendance FastAPI qui vérifie qu'un des rôles de
    l'utilisateur courant a le droit `action` sur `module`.

    Usage :
        @router.post("/documents/{id}/publish")
        def publish(..., _: User = Depends(require_permission("documentaire", "publish"))):
            ...
    """

    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        role_ids = [ur.role_id for ur in current_user.roles]
        if not role_ids:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Aucun rôle attribué")

        allowed = (
            db.query(Permission)
            .filter(
                Permission.role_id.in_(role_ids),
                Permission.module == module,
                Permission.action == action,
                Permission.autorise.is_(True),
            )
            .first()
        )
        if not allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Droit manquant : {module}.{action}",
            )
        return current_user

    return checker
