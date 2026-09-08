"""Moteur statut/historique/notifications, version complète : transitions
validées, endpoint d'historique, email, templates."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.email import send_email
from app.core.models import Notification, ObjectType, StatusHistory
from app.core.security import get_current_user

router = APIRouter()

# Transitions autorisées par type d'objet. À enrichir au fur et à mesure
# que chaque module métier (documentaire, evenements, audits) est codé.
ALLOWED_TRANSITIONS: dict[ObjectType, dict[str, list[str]]] = {
        ObjectType.document: {
        "en_attente_examen": ["en_cours_redaction", "rejetee"],
        "en_cours_redaction": ["en_cours_verification"],
        "en_cours_verification": ["en_cours_redaction", "verifie"],
        "verifie": ["en_attente_validation"],
        "en_attente_validation": ["valide"],
        "valide": ["diffuse"],
        "diffuse": ["a_reviser"],
        "a_reviser": ["en_cours_redaction"],
    },
    ObjectType.event: {
        "declare": ["en_analyse"],
        "en_analyse": ["actions_definies"],
        "actions_definies": ["cloture"],
    },
    ObjectType.audit: {
        "planifie": ["en_cours"],
        "en_cours": ["cloture"],
    },
}

# Templates de notification de base. À enrichir par événement au fur et à
# mesure des besoins réels de chaque module.
TEMPLATES = {
    "nouvelle_demande": "Une nouvelle demande a été soumise : {objet}",
    "a_verifier": "Un document est prêt à être vérifié : {objet}",
    "action_assignee": "Une action corrective vous a été assignée : {objet}",
}


def change_status(
    db: Session,
    object_type: ObjectType,
    object_id: int,
    ancien_statut: str | None,
    nouveau_statut: str,
    user_id: int,
    commentaire: str | None = None,
) -> StatusHistory:
    """Vérifie que la transition est autorisée, puis l'enregistre dans
    l'historique générique. L'appelant reste responsable de mettre à jour
    le champ `statut` sur l'objet lui-même."""
    rules = ALLOWED_TRANSITIONS.get(object_type, {})

    if ancien_statut is not None:
        allowed_next = rules.get(ancien_statut, [])
        if nouveau_statut not in allowed_next:
            raise HTTPException(
                status_code=400,
                detail=f"Transition non autorisée : {ancien_statut} -> {nouveau_statut}",
            )

    entry = StatusHistory(
        object_type=object_type,
        object_id=object_id,
        ancien_statut=ancien_statut,
        nouveau_statut=nouveau_statut,
        user_id=user_id,
        commentaire=commentaire,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def notify(
    db: Session,
    user_id: int,
    template_name: str,
    context: dict,
    lien: str | None = None,
    send_email_too: bool = False,
    user_email: str | None = None,
) -> Notification:
    """Crée une notification in-app à partir d'un template, et envoie un
    email en plus si demandé (nécessite user_email)."""
    message = TEMPLATES.get(template_name, template_name).format(**context)

    notification = Notification(
        user_id=user_id, titre=template_name, message=message, lien=lien
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    if send_email_too and user_email:
        send_email(to=user_email, subject=template_name, body=message)

    return notification


@router.get("/{object_type}/{object_id}/history")
def get_history(
    object_type: ObjectType,
    object_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    entries = (
        db.query(StatusHistory)
        .filter(
            StatusHistory.object_type == object_type,
            StatusHistory.object_id == object_id,
        )
        .order_by(StatusHistory.date)
        .all()
    )
    return [
        {
            "ancien_statut": e.ancien_statut,
            "nouveau_statut": e.nouveau_statut,
            "user_id": e.user_id,
            "date": e.date,
            "commentaire": e.commentaire,
        }
        for e in entries
    ]
