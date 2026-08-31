"""Peuple la base avec les données de départ. Usage : python -m app.core.seed"""

from app.core.database import SessionLocal
from app.core.models import Role, Site

SITES = ["Hôpital Général", "Hôpital de Réhabilitation", "Hôpital de Gériatrie"]

ROLES = [
    "redacteur", "verificateur", "approbateur", "responsable_service",
    "qualite", "direction_generale", "direction_medicale",
    "direction_financiere", "direction_rh",
]


def run():
    db = SessionLocal()
    try:
        for nom in SITES:
            if not db.query(Site).filter_by(nom=nom).first():
                db.add(Site(nom=nom))
        for nom in ROLES:
            if not db.query(Role).filter_by(nom=nom).first():
                db.add(Role(nom=nom))
        db.commit()
        print(f"Seed terminé : {len(SITES)} sites, {len(ROLES)} rôles.")
    finally:
        db.close()


if __name__ == "__main__":
    run()