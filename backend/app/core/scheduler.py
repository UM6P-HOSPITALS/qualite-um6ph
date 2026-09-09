from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.core.email import send_email
from app.core.models import Role, User, UserRole
from app.core.status_engine import ObjectType, notify
from app.documentaire.models import (
    AttendanceList,
    AttendanceParticipant,
    Document,
    DocumentAssignment,
    Quiz,
    QuizAttempt,
)

scheduler = BackgroundScheduler()


@scheduler.scheduled_job("cron", hour=7)
def relance_evaluations_non_faites():
    """Chaque jour à 7h : identifie les participants qui n'ont pas encore
    passé le quiz de leur formation, et relance leur responsable de
    service (faute d'un vrai lien hiérarchique dans le modèle actuel)."""
    db = SessionLocal()
    try:
        attendance_lists = db.query(AttendanceList).all()
        for attendance in attendance_lists:
            quiz = db.query(Quiz).filter(Quiz.document_id == attendance.document_id).first()
            if not quiz:
                continue

            participants = (
                db.query(AttendanceParticipant)
                .filter(AttendanceParticipant.attendance_list_id == attendance.id)
                .all()
            )

            done_user_ids = {
                a.user_id
                for a in db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).all()
            }

            missing_users = [
                db.query(User).filter(User.id == p.user_id).first()
                for p in participants
                if p.user_id not in done_user_ids
            ]
            missing_users = [u for u in missing_users if u is not None]
            if not missing_users:
                continue

            role = db.query(Role).filter(Role.nom == "responsable_service").first()
            if not role:
                continue

            services_concernes = {ur.service_id for u in missing_users for ur in u.roles}
            for service_id in services_concernes:
                if service_id is None:
                    continue
                responsables = (
                    db.query(UserRole)
                    .filter(UserRole.role_id == role.id, UserRole.service_id == service_id)
                    .all()
                )
                noms = ", ".join(
                    u.email for u in missing_users
                    if any(ur.service_id == service_id for ur in u.roles)
                )
                for resp in responsables:
                    responsable_user = db.query(User).filter(User.id == resp.user_id).first()
                    if responsable_user:
                        send_email(
                            to=responsable_user.email,
                            subject="Relance : évaluations non complétées",
                            body=f"Les personnes suivantes n'ont pas encore complété leur évaluation : {noms}",
                        )
    finally:
        db.close()


@scheduler.scheduled_job("cron", hour=8)
def detecter_revisions_a_venir():
    """Chaque jour à 8h : détecte les documents diffusés depuis presque
    un an (J-15 avant échéance), notifie Qualité et le(s) rédacteur(s)
    une seule fois par échéance grâce à revision_notifiee."""
    db = SessionLocal()
    try:
        documents = (
            db.query(Document)
            .filter(
                Document.statut == "diffuse",
                Document.revision_notifiee.is_(False),
                Document.date_diffusion.isnot(None),
            )
            .all()
        )

        qualite_role = db.query(Role).filter(Role.nom == "qualite").first()
        qualite_user_ids = []
        if qualite_role:
            qualite_user_ids = [
                ur.user_id
                for ur in db.query(UserRole).filter(UserRole.role_id == qualite_role.id).all()
            ]

        for document in documents:
            echeance = document.date_diffusion + timedelta(days=365)
            jours_restants = (echeance - datetime.utcnow()).days

            if jours_restants <= 15:
                for uid in qualite_user_ids:
                    notify(
                        db,
                        user_id=uid,
                        template_name="a_verifier",
                        context={"objet": f"Révision à prévoir : {document.intitule}"},
                        lien=f"/documents/{document.id}",
                    )

                redacteurs = (
                    db.query(DocumentAssignment)
                    .filter(
                        DocumentAssignment.document_id == document.id,
                        DocumentAssignment.role_document == "redacteur",
                    )
                    .all()
                )
                for r in redacteurs:
                    notify(
                        db,
                        user_id=r.user_id,
                        template_name="a_verifier",
                        context={"objet": f"Révision à prévoir : {document.intitule}"},
                        lien=f"/documents/{document.id}",
                    )

                document.revision_notifiee = True

        db.commit()
    finally:
        db.close()


def start_scheduler():
    scheduler.start()