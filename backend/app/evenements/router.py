from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Role, Service, User, UserRole
from app.core.permissions import require_permission
from app.core.security import get_current_user
from app.core.status_engine import ObjectType, change_status, notify
from app.evenements.models import AdverseEvent, AdverseEventAnalysisEntry, AdverseEventAnalyst
from app.evenements.schemas import (
    AdverseEventCreate,
    AdverseEventOut,
    AnalysisEntryCreate,
    AnalysisEntryOut,
    AnalystOut,
    AssignAnalystsRequest,
)

router = APIRouter()


def _generate_numero_suivi(db: Session) -> str:
    year = datetime.utcnow().year
    count = (
        db.query(AdverseEvent)
        .filter(AdverseEvent.numero_suivi.like(f"EI-{year}-%"))
        .count()
    )
    return f"EI-{year}-{count + 1:05d}"


@router.post("/", response_model=AdverseEventOut, status_code=201)
def declare_event(
    payload: AdverseEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = db.query(Service).filter(Service.id == payload.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service introuvable")

    if payload.gravite not in ("mineure", "majeure", "critique"):
        raise HTTPException(status_code=400, detail="Gravité invalide (mineure, majeure, critique)")

    numero_suivi = _generate_numero_suivi(db)

    event = AdverseEvent(
        numero_suivi=numero_suivi,
        date_evenement=payload.date_evenement,
        lieu=payload.lieu,
        service_id=payload.service_id,
        description=payload.description,
        personnes_impliquees=payload.personnes_impliquees,
        gravite=payload.gravite,
        actions_immediates=payload.actions_immediates,
        declarant_id=current_user.id,
        pieces_jointes=payload.pieces_jointes,
        statut="declare",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    change_status(
        db,
        object_type=ObjectType.event,
        object_id=event.id,
        ancien_statut=None,
        nouveau_statut="declare",
        user_id=current_user.id,
    )

    qualite_role = db.query(Role).filter(Role.nom == "qualite").first()
    direction_role = db.query(Role).filter(Role.nom == "direction_generale").first()

    notified_role_ids = [r.id for r in [qualite_role, direction_role] if r is not None]
    if notified_role_ids:
        recipients = (
            db.query(UserRole).filter(UserRole.role_id.in_(notified_role_ids)).all()
        )
        for r in recipients:
            notify(
                db,
                user_id=r.user_id,
                template_name="nouvelle_demande",
                context={"objet": f"Événement indésirable déclaré : {numero_suivi} ({service.nom})"},
                lien=f"/evenements/{event.id}",
            )

    return AdverseEventOut(
        id=event.id,
        numero_suivi=event.numero_suivi,
        date_evenement=event.date_evenement,
        lieu=event.lieu,
        service_nom=service.nom,
        description=event.description,
        personnes_impliquees=event.personnes_impliquees,
        gravite=event.gravite,
        actions_immediates=event.actions_immediates,
        declarant_email=current_user.email,
        statut=event.statut,
        date_declaration=event.date_declaration,
        pieces_jointes=event.pieces_jointes,
    )


def _is_qualite(db: Session, current_user: User) -> bool:
    return (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == current_user.id, Role.nom == "qualite")
        .first()
        is not None
    )


def _is_assigned_analyst(db: Session, event_id: int, user_id: int) -> bool:
    return (
        db.query(AdverseEventAnalyst)
        .filter(AdverseEventAnalyst.event_id == event_id, AdverseEventAnalyst.user_id == user_id)
        .first()
        is not None
    )


@router.get("/{event_id}", response_model=AdverseEventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    event = db.query(AdverseEvent).filter(AdverseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable")

    return AdverseEventOut(
        id=event.id,
        numero_suivi=event.numero_suivi,
        date_evenement=event.date_evenement,
        lieu=event.lieu,
        service_nom=event.service.nom,
        description=event.description,
        personnes_impliquees=event.personnes_impliquees,
        gravite=event.gravite,
        actions_immediates=event.actions_immediates,
        declarant_email=event.declarant.email,
        statut=event.statut,
        date_declaration=event.date_declaration,
        pieces_jointes=event.pieces_jointes,
    )


@router.patch("/{event_id}/assign-analysts", response_model=list[AnalystOut])
def assign_analysts(
    event_id: int,
    payload: AssignAnalystsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission("evenements", "manage_analysis")),
):
    event = db.query(AdverseEvent).filter(AdverseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable")

    if event.statut != "declare":
        raise HTTPException(status_code=400, detail="Cet événement n'est pas au statut 'déclaré'")

    analysts = []
    for email in payload.analyst_emails:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"Utilisateur introuvable : {email}")

        existing = (
            db.query(AdverseEventAnalyst)
            .filter(AdverseEventAnalyst.event_id == event_id, AdverseEventAnalyst.user_id == user.id)
            .first()
        )
        if not existing:
            entry = AdverseEventAnalyst(event_id=event_id, user_id=user.id)
            db.add(entry)
            analysts.append(entry)

            notify(
                db,
                user_id=user.id,
                template_name="a_verifier",
                context={"objet": f"Analyse requise : {event.numero_suivi}"},
                lien=f"/evenements/{event_id}/analyse",
            )

    ancien_statut = event.statut
    event.statut = "en_analyse"
    db.commit()

    change_status(
        db,
        object_type=ObjectType.event,
        object_id=event.id,
        ancien_statut=ancien_statut,
        nouveau_statut="en_analyse",
        user_id=current_user.id,
    )

    all_analysts = db.query(AdverseEventAnalyst).filter(AdverseEventAnalyst.event_id == event_id).all()
    return [
        AnalystOut(user_email=a_user.email, date_assignation=a.date_assignation)
        for a in all_analysts
        for a_user in [db.query(User).filter(User.id == a.user_id).first()]
        if a_user
    ]


@router.get("/{event_id}/analysts", response_model=list[AnalystOut])
def list_analysts(
    event_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    analysts = db.query(AdverseEventAnalyst).filter(AdverseEventAnalyst.event_id == event_id).all()
    return [
        AnalystOut(user_email=a.user.email if hasattr(a, "user") else db.query(User).filter(User.id == a.user_id).first().email, date_assignation=a.date_assignation)
        for a in analysts
    ]


def _check_can_analyze(db: Session, event_id: int, current_user: User):
    if _is_qualite(db, current_user):
        return
    if _is_assigned_analyst(db, event_id, current_user.id):
        return
    raise HTTPException(
        status_code=403,
        detail="Seul le service Qualité ou un analyste désigné peut accéder à cette analyse",
    )


@router.get("/{event_id}/analysis", response_model=list[AnalysisEntryOut])
def get_analysis(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.query(AdverseEvent).filter(AdverseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable")

    _check_can_analyze(db, event_id, current_user)

    entries = (
        db.query(AdverseEventAnalysisEntry)
        .filter(AdverseEventAnalysisEntry.event_id == event_id)
        .order_by(AdverseEventAnalysisEntry.date)
        .all()
    )
    return [
        AnalysisEntryOut(id=e.id, user_email=e.user.email, contenu=e.contenu, date=e.date)
        for e in entries
    ]


@router.post("/{event_id}/analysis", response_model=AnalysisEntryOut, status_code=201)
def add_analysis_entry(
    event_id: int,
    payload: AnalysisEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.query(AdverseEvent).filter(AdverseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable")

    _check_can_analyze(db, event_id, current_user)

    if event.statut != "en_analyse":
        raise HTTPException(status_code=400, detail="Cet événement n'est pas en cours d'analyse")

    entry = AdverseEventAnalysisEntry(event_id=event_id, user_id=current_user.id, contenu=payload.contenu)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return AnalysisEntryOut(id=entry.id, user_email=current_user.email, contenu=entry.contenu, date=entry.date)