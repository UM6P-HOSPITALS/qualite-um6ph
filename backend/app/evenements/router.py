from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Role, Service, User, UserRole
from app.core.permissions import require_permission
from app.core.security import get_current_user
from app.core.status_engine import ObjectType, change_status, notify
from app.evenements.models import AdverseEvent, AdverseEventAction, AdverseEventAnalysisEntry, AdverseEventAnalyst
from app.evenements.schemas import (
    ActionCreate,
    ActionOut,
    ActionStatusUpdate,
    AdverseEventCreate,
    AdverseEventOut,
    AnalysisEntryCreate,
    AnalysisEntryOut,
    AnalystOut,
    AssignAnalystsRequest,
    MajorCompletionRequest,
)

PRIORITES_VALIDES = ("basse", "moyenne", "haute")
CRITICITES_VALIDES = ("mineure", "majeure", "critique")
STATUTS_ACTION_VALIDES = ("a_faire", "en_cours", "realisee")
GRAVITES_VALIDES = ("mineur", "majeur", "grave")
SIGNALEMENT_DESTINATAIRES = (
    "Médecin Spécialiste Concerné",
    "Surveillant",
    "Service Qualité et Gestion des Risques",
    "Direction Médicale",
    "Autre",
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


def _event_to_out(event: AdverseEvent) -> AdverseEventOut:
    return AdverseEventOut(
        id=event.id,
        numero_suivi=event.numero_suivi,
        date_evenement=event.date_evenement,
        lieu=event.lieu,
        service_nom=event.service.nom,
        professionnel_identifiant=event.professionnel_identifiant,
        contact_professionnel=event.contact_professionnel,
        categorie=event.categorie,
        description=event.description,
        personnes_impliquees=event.personnes_impliquees,
        gravite=event.gravite,
        actions_immediates=event.actions_immediates,
        signalement_effectue_a=event.signalement_effectue_a,
        visa_major=event.visa_major,
        declarant_email=event.declarant.email,
        statut=event.statut,
        date_declaration=event.date_declaration,
        pieces_jointes=event.pieces_jointes,
    )


@router.get("/", response_model=list[AdverseEventOut])
def list_events(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    events = db.query(AdverseEvent).order_by(AdverseEvent.date_declaration.desc()).all()
    return [_event_to_out(e) for e in events]


@router.post("/", response_model=AdverseEventOut, status_code=201)
def declare_event(
    payload: AdverseEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = db.query(Service).filter(Service.id == payload.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service introuvable")

    if payload.gravite not in GRAVITES_VALIDES:
        raise HTTPException(status_code=400, detail=f"Gravité invalide ({', '.join(GRAVITES_VALIDES)})")

    numero_suivi = _generate_numero_suivi(db)

    event = AdverseEvent(
        numero_suivi=numero_suivi,
        date_evenement=payload.date_evenement,
        lieu=payload.lieu,
        service_id=payload.service_id,
        professionnel_identifiant=payload.professionnel_identifiant,
        contact_professionnel=payload.contact_professionnel,
        categorie=payload.categorie,
        description=payload.description,
        gravite=payload.gravite,
        actions_immediates=payload.actions_immediates,
        personnes_impliquees=payload.personnes_impliquees,
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
        recipients = db.query(UserRole).filter(UserRole.role_id.in_(notified_role_ids)).all()
        for r in recipients:
            notify(
                db,
                user_id=r.user_id,
                template_name="nouvelle_demande",
                context={"objet": f"Événement indésirable déclaré : {numero_suivi} ({service.nom})"},
                lien=f"/evenements/{event.id}",
            )

    return _event_to_out(event)


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


def _check_can_analyze(db: Session, event_id: int, current_user: User):
    if _is_qualite(db, current_user):
        return
    if _is_assigned_analyst(db, event_id, current_user.id):
        return
    raise HTTPException(
        status_code=403,
        detail="Seul le service Qualité ou un analyste désigné peut accéder à cette analyse",
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

    return _event_to_out(event)


@router.patch("/{event_id}/major-completion", response_model=AdverseEventOut)
def complete_by_major(
    event_id: int,
    payload: MajorCompletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Section 'À renseigner par le major du service' — réservé à Qualité
    ou au responsable de service concerné, faute d'un rôle 'major' dédié
    dans le système actuel."""
    event = db.query(AdverseEvent).filter(AdverseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable")

    is_qualite = _is_qualite(db, current_user)
    is_responsable_service = any(
        ur.service_id == event.service_id for ur in current_user.roles
    )
    if not is_qualite and not is_responsable_service:
        raise HTTPException(
            status_code=403,
            detail="Seul le service Qualité ou le responsable du service concerné peut compléter cette section",
        )

    if not payload.visa.strip():
        raise HTTPException(status_code=400, detail="Le visa est requis")

    event.signalement_effectue_a = payload.signalement_effectue_a
    event.visa_major = payload.visa.strip()
    event.date_completion_major = datetime.utcnow()
    db.commit()
    db.refresh(event)

    return _event_to_out(event)


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
        AnalystOut(
            user_email=db.query(User).filter(User.id == a.user_id).first().email,
            date_assignation=a.date_assignation,
        )
        for a in all_analysts
    ]


@router.get("/{event_id}/analysts", response_model=list[AnalystOut])
def list_analysts(
    event_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    analysts = db.query(AdverseEventAnalyst).filter(AdverseEventAnalyst.event_id == event_id).all()
    return [
        AnalystOut(
            user_email=db.query(User).filter(User.id == a.user_id).first().email,
            date_assignation=a.date_assignation,
        )
        for a in analysts
    ]


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


@router.post("/{event_id}/actions", response_model=ActionOut, status_code=201)
def create_action(
    event_id: int,
    payload: ActionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.query(AdverseEvent).filter(AdverseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable")

    _check_can_analyze(db, event_id, current_user)

    if payload.priorite not in PRIORITES_VALIDES:
        raise HTTPException(status_code=400, detail=f"Priorité invalide ({', '.join(PRIORITES_VALIDES)})")
    if payload.criticite not in CRITICITES_VALIDES:
        raise HTTPException(status_code=400, detail=f"Criticité invalide ({', '.join(CRITICITES_VALIDES)})")

    responsable = db.query(User).filter(User.email == payload.responsable_email).first()
    if not responsable:
        raise HTTPException(status_code=404, detail=f"Utilisateur introuvable : {payload.responsable_email}")

    if event.statut == "en_analyse":
        ancien_statut = event.statut
        event.statut = "actions_definies"
        db.commit()
        change_status(
            db,
            object_type=ObjectType.event,
            object_id=event.id,
            ancien_statut=ancien_statut,
            nouveau_statut="actions_definies",
            user_id=current_user.id,
        )

    action = AdverseEventAction(
        event_id=event_id,
        description=payload.description,
        responsable_id=responsable.id,
        echeance=payload.echeance,
        priorite=payload.priorite,
        criticite=payload.criticite,
        statut="a_faire",
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    notify(
        db,
        user_id=responsable.id,
        template_name="action_assignee",
        context={"objet": f"{event.numero_suivi} — {payload.description[:50]}"},
        lien=f"/evenements/{event_id}/actions",
    )

    return ActionOut(
        id=action.id,
        event_id=action.event_id,
        description=action.description,
        responsable_email=responsable.email,
        echeance=action.echeance,
        priorite=action.priorite,
        criticite=action.criticite,
        statut=action.statut,
        date_creation=action.date_creation,
    )


@router.get("/{event_id}/actions", response_model=list[ActionOut])
def list_actions(
    event_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    actions = db.query(AdverseEventAction).filter(AdverseEventAction.event_id == event_id).all()
    return [
        ActionOut(
            id=a.id,
            event_id=a.event_id,
            description=a.description,
            responsable_email=a.responsable.email,
            echeance=a.echeance,
            priorite=a.priorite,
            criticite=a.criticite,
            statut=a.statut,
            date_creation=a.date_creation,
        )
        for a in actions
    ]


@router.get("/actions/mine", response_model=list[ActionOut])
def list_my_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actions = db.query(AdverseEventAction).filter(AdverseEventAction.responsable_id == current_user.id).all()
    return [
        ActionOut(
            id=a.id,
            event_id=a.event_id,
            description=a.description,
            responsable_email=current_user.email,
            echeance=a.echeance,
            priorite=a.priorite,
            criticite=a.criticite,
            statut=a.statut,
            date_creation=a.date_creation,
        )
        for a in actions
    ]


@router.patch("/actions/{action_id}/status", response_model=ActionOut)
def update_action_status(
    action_id: int,
    payload: ActionStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = db.query(AdverseEventAction).filter(AdverseEventAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action introuvable")

    if action.responsable_id != current_user.id and not _is_qualite(db, current_user):
        raise HTTPException(
            status_code=403,
            detail="Seul le responsable de l'action ou le service Qualité peut modifier son statut",
        )

    if payload.statut not in STATUTS_ACTION_VALIDES:
        raise HTTPException(status_code=400, detail=f"Statut invalide ({', '.join(STATUTS_ACTION_VALIDES)})")

    action.statut = payload.statut
    db.commit()
    db.refresh(action)

    return ActionOut(
        id=action.id,
        event_id=action.event_id,
        description=action.description,
        responsable_email=action.responsable.email,
        echeance=action.echeance,
        priorite=action.priorite,
        criticite=action.criticite,
        statut=action.statut,
        date_creation=action.date_creation,
    )