"""Bootstrap : attribue le rôle 'qualite' à un utilisateur, et donne à ce
rôle les permissions admin de base. À lancer UNE FOIS après avoir créé ton
premier compte via POST /auth/register, pour débloquer l'accès aux
endpoints /admin/* (protégés).

Usage : python -m app.core.bootstrap_admin ton.email@um6p.ma
"""

import sys

from app.core.database import SessionLocal
from app.core.models import Permission, Role, User, UserRole


def run(email: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Aucun utilisateur avec l'email {email}. Crée-le d'abord via /auth/register.")
            return

        qualite_role = db.query(Role).filter(Role.nom == "qualite").first()
        if not qualite_role:
            print("Rôle 'qualite' introuvable — relance d'abord python -m app.core.seed")
            return

        already = (
            db.query(UserRole)
            .filter(UserRole.user_id == user.id, UserRole.role_id == qualite_role.id)
            .first()
        )
        if not already:
            db.add(UserRole(user_id=user.id, role_id=qualite_role.id))

        base_permissions = [
            ("admin", "manage_users"),
            ("admin", "manage_permissions"),
        ]
        for module, action in base_permissions:
            exists = (
                db.query(Permission)
                .filter(
                    Permission.role_id == qualite_role.id,
                    Permission.module == module,
                    Permission.action == action,
                )
                .first()
            )
            if not exists:
                db.add(Permission(role_id=qualite_role.id, module=module, action=action, autorise=True))

        db.commit()
        print(f"{email} a maintenant le rôle 'qualite' avec les droits admin de base.")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage : python -m app.core.bootstrap_admin ton.email@um6p.ma")
        sys.exit(1)
    run(sys.argv[1])
