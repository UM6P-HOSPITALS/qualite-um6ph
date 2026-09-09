from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.core.email import send_email
from app.core.models import Role, User, UserRole
from app.documentaire.models import (
    AttendanceList,
    AttendanceParticipant,
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


def start_scheduler():
    scheduler.start()