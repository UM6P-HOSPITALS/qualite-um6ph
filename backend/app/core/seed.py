"""Peuple la base avec les données de départ : les 3 sites, les 9 rôles,
et quelques services de test. À lancer une fois après la première
migration.

Usage : python -m app.core.seed
"""

from app.core.database import SessionLocal
from app.core.models import Role, Service, Site

SITES = [
    "Hôpital Général",
    "Hôpital de Réhabilitation",
    "Hôpital de Gériatrie",
]

ROLES = [
    "redacteur",
    "verificateur",
    "approbateur",
    "responsable_service",
    "qualite",
    "direction_generale",
    "direction_medicale",
    "direction_financiere",
    "direction_rh",
]

# Services de TEST pour continuer le développement — à remplacer par la
# vraie liste fournie par le service Qualité avant la mise en production.
SERVICES_TEST = [
    ("Service Qualité", "Hôpital Général"),
    ("Cardiologie", "Hôpital Général"),
    ("Chirurgie", "Hôpital Général"),
]


def run():
    db = SessionLocal()
    try:
        for nom in SITES:
            if not db.query(Site).filter_by(nom=nom).first():
                db.add(Site(nom=nom))
        db.commit()

        for nom in ROLES:
            if not db.query(Role).filter_by(nom=nom).first():
                db.add(Role(nom=nom))
        db.commit()

        for service_nom, site_nom in SERVICES_TEST:
            site = db.query(Site).filter_by(nom=site_nom).first()
            if site and not db.query(Service).filter_by(nom=service_nom).first():
                db.add(Service(nom=service_nom, site_id=site.id))
        db.commit()

        print(f"Seed terminé : {len(SITES)} sites, {len(ROLES)} rôles, {len(SERVICES_TEST)} services.")
    finally:
        db.close()


if __name__ == "__main__":
    run()