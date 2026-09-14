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
    DashboardEIOut,
    EfficacyEvaluationRequest,
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
    include_cloture: bool = False,
    _current_user: User = Depends(get_current_user),
):
    query = db.query(AdverseEvent)
    if not include_cloture:
        query = query.filter(AdverseEvent.statut != "cloture")
    events = query.order_by(AdverseEvent.date_declaration.desc()).all()
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


@router.get("/dashboard", response_model=DashboardEIOut)
def get_dashboard(
    db: Session = Depends(get_db),
    _=Depends(require_permission("evenements", "view_stats")),
):
    all_events = db.query(AdverseEvent).all()
    total = len(all_events)

    cloture_events = [e for e in all_events if e.statut == "cloture"]
    taux_cloture = (len(cloture_events) / total) if total > 0 else 0.0

    delais = [
        (e.date_cloture - e.date_declaration).days
        for e in cloture_events
        if e.date_cloture is not None
    ]
    delai_moyen = (sum(delais) / len(delais)) if delais else 0.0

    repartition_gravite: dict[str, int] = {}
    for e in all_events:
        repartition_gravite[e.gravite] = repartition_gravite.get(e.gravite, 0) + 1

    repartition_par_service: dict[str, int] = {}
    for e in all_events:
        nom = e.service.nom
        repartition_par_service[nom] = repartition_par_service.get(nom, 0) + 1

    tendance: dict[str, int] = {}
    for e in all_events:
        key = e.date_declaration.strftime("%Y-%m")
        tendance[key] = tendance.get(key, 0) + 1
    tendance_mensuelle = [{"mois": k, "count": v} for k, v in sorted(tendance.items())]

    return DashboardEIOut(
        total_evenements=total,
        taux_cloture=round(taux_cloture, 2),
        delai_moyen_jours=round(delai_moyen, 1),
        repartition_gravite=repartition_gravite,
        repartition_par_service=repartition_par_service,
        tendance_mensuelle=tendance_mensuelle,
    )


@router.get("/export/excel")
def export_excel(
    db: Session = Depends(get_db),
    _=Depends(require_permission("evenements", "view_stats")),
):
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook

    events = db.query(AdverseEvent).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Événements indésirables"
    ws.append(["Numéro", "Date événement", "Service", "Gravité", "Statut", "Date déclaration", "Date clôture"])

    for e in events:
        ws.append([
            e.numero_suivi,
            e.date_evenement.strftime("%Y-%m-%d %H:%M"),
            e.service.nom,
            e.gravite,
            e.statut,
            e.date_declaration.strftime("%Y-%m-%d"),
            e.date_cloture.strftime("%Y-%m-%d") if e.date_cloture else "",
        ])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=evenements_indesirables.xlsx"},
    )


@router.get("/export/pdf")
def export_pdf(
    db: Session = Depends(get_db),
    _=Depends(require_permission("evenements", "view_stats")),
):
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    events = db.query(AdverseEvent).all()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = [Paragraph("Rapport des événements indésirables", styles["Title"]), Spacer(1, 12)]

    data = [["Numéro", "Date événement", "Service", "Gravité", "Statut", "Déclaration", "Clôture"]]
    for e in events:
        data.append([
            e.numero_suivi,
            e.date_evenement.strftime("%Y-%m-%d %H:%M"),
            e.service.nom,
            e.gravite,
            e.statut,
            e.date_declaration.strftime("%Y-%m-%d"),
            e.date_cloture.strftime("%Y-%m-%d") if e.date_cloture else "-",
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00543f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=evenements_indesirables.pdf"},
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


@router.patch("/{event_id}/evaluate-efficacite", response_model=AdverseEventOut)
def evaluate_efficacite(
    event_id: int,
    payload: EfficacyEvaluationRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permission("evenements", "manage_analysis")),
):
    event = db.query(AdverseEvent).filter(AdverseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable")

    if event.statut != "actions_definies":
        raise HTTPException(status_code=400, detail="L'événement doit être au statut 'actions_definies'")

    event.evaluation_efficacite = payload.contenu
    event.efficacite_evaluee = True
    db.commit()
    db.refresh(event)

    return _event_to_out(event)


@router.patch("/{event_id}/close", response_model=AdverseEventOut)
def close_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission("evenements", "manage_analysis")),
):
    event = db.query(AdverseEvent).filter(AdverseEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Événement introuvable")

    if not event.efficacite_evaluee:
        raise HTTPException(
            status_code=400,
            detail="L'évaluation d'efficacité doit être faite avant la clôture",
        )

    if event.statut != "actions_definies":
        raise HTTPException(status_code=400, detail="L'événement doit être au statut 'actions_definies'")

    ancien_statut = event.statut
    event.statut = "cloture"
    event.date_cloture = datetime.utcnow()
    db.commit()

    change_status(
        db,
        object_type=ObjectType.event,
        object_id=event.id,
        ancien_statut=ancien_statut,
        nouveau_statut="cloture",
        user_id=current_user.id,
    )

    db.refresh(event)
    return _event_to_out(event)