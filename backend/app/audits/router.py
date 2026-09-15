from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Role, Service, User, UserRole
from app.core.permissions import require_permission
from app.core.security import get_current_user
from app.core.status_engine import ObjectType, change_status, notify
from app.audits.models import AuditAction, AuditFinding, AuditGrid, AuditGridCriteria, AuditProgram
from app.audits.schemas import (
    AssignResponsableRequest,
    AuditActionCreate,
    AuditActionOut,
    AuditActionStatusUpdate,
    AuditGridCreate,
    AuditGridOut,
    AuditProgramCreate,
    AuditProgramOut,
    AuditProgramUpdate,
    ConformiteOut,
    DashboardAuditOut,
    FindingCreate,
    FindingOut,
)

STATUTS_PROGRAMME_VALIDES = ("planifie", "en_cours", "realise")
CLASSIFICATIONS_VALIDES = ("mineure", "majeure", "critique")
STATUTS_AUDIT_ACTION_VALIDES = ("a_faire", "en_cours", "realisee")

router = APIRouter()


def _program_to_out(program: AuditProgram) -> AuditProgramOut:
    return AuditProgramOut(
        id=program.id,
        annee=program.annee,
        service_nom=program.service.nom if program.service else None,
        processus=program.processus,
        thematique=program.thematique,
        responsable_email=program.responsable.email,
        date_debut_prevue=program.date_debut_prevue,
        date_fin_prevue=program.date_fin_prevue,
        statut=program.statut,
        notes=program.notes,
        rapport_verrouille=program.rapport_verrouille,
        date_creation=program.date_creation,
    )


def _is_qualite(db: Session, current_user: User) -> bool:
    return (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == current_user.id, Role.nom == "qualite")
        .first()
        is not None
    )


def _can_view_program(db: Session, program: AuditProgram, current_user: User) -> bool:
    return _is_qualite(db, current_user) or program.responsable_id == current_user.id


def _can_access_program(db: Session, program: AuditProgram, current_user: User) -> bool:
    return _is_qualite(db, current_user) or program.responsable_id == current_user.id


@router.get("/programs", response_model=list[AuditProgramOut])
def list_programs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accès restreint : Qualité voit tout, un responsable désigné ne voit
    que les programmes dont il est responsable — pas d'accès grand public."""
    query = db.query(AuditProgram)
    if not _is_qualite(db, current_user):
        query = query.filter(AuditProgram.responsable_id == current_user.id)

    programs = query.order_by(AuditProgram.annee.desc(), AuditProgram.date_debut_prevue).all()
    return [_program_to_out(p) for p in programs]


@router.post("/programs", response_model=AuditProgramOut, status_code=201)
def create_program(
    payload: AuditProgramCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("audits", "manage_programs")),
):
    if not payload.service_id and not payload.processus and not payload.thematique:
        raise HTTPException(
            status_code=400,
            detail="Précisez au moins un service, un processus ou une thématique",
        )

    if payload.service_id:
        service = db.query(Service).filter(Service.id == payload.service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service introuvable")

    responsable = db.query(User).filter(User.email == payload.responsable_email).first()
    if not responsable:
        raise HTTPException(status_code=404, detail=f"Utilisateur introuvable : {payload.responsable_email}")

    if payload.date_fin_prevue < payload.date_debut_prevue:
        raise HTTPException(status_code=400, detail="La date de fin doit être après la date de début")

    program = AuditProgram(
        annee=payload.annee,
        service_id=payload.service_id,
        processus=payload.processus,
        thematique=payload.thematique,
        responsable_id=responsable.id,
        date_debut_prevue=payload.date_debut_prevue,
        date_fin_prevue=payload.date_fin_prevue,
        notes=payload.notes,
        statut="planifie",
    )
    db.add(program)
    db.commit()
    db.refresh(program)

    return _program_to_out(program)


@router.get("/dashboard", response_model=DashboardAuditOut)
def get_audit_dashboard(
    db: Session = Depends(get_db),
    _=Depends(require_permission("audits", "view_stats")),
):
    programs = db.query(AuditProgram).all()
    total_programmes = len(programs)

    realises = [p for p in programs if p.statut == "realise"]
    taux_realisation = (len(realises) / total_programmes * 100) if total_programmes > 0 else 0.0

    repartition_statuts: dict[str, int] = {}
    for p in programs:
        repartition_statuts[p.statut] = repartition_statuts.get(p.statut, 0) + 1

    repartition_par_service: dict[str, int] = {}
    for p in programs:
        cible = p.service.nom if p.service else (p.processus or p.thematique or "Non spécifié")
        repartition_par_service[cible] = repartition_par_service.get(cible, 0) + 1

    all_findings = db.query(AuditFinding).all()
    non_conformites = [f for f in all_findings if not f.conforme]
    total_non_conformites = len(non_conformites)

    repartition_non_conformites: dict[str, int] = {}
    for nc in non_conformites:
        cle = nc.classification or "non_classee"
        repartition_non_conformites[cle] = repartition_non_conformites.get(cle, 0) + 1

    all_grids = db.query(AuditGrid).all()
    taux_list = []
    for grid in all_grids:
        criteres = db.query(AuditGridCriteria).filter(AuditGridCriteria.grid_id == grid.id).all()
        findings = db.query(AuditFinding).filter(AuditFinding.grid_id == grid.id).all()
        findings_by_criteria = {f.criteria_id: f for f in findings}
        points_total = sum(c.ponderation for c in criteres)
        points_obtenus = sum(
            c.ponderation
            for c in criteres
            if c.id in findings_by_criteria and findings_by_criteria[c.id].conforme
        )
        if points_total > 0:
            taux_list.append(points_obtenus / points_total * 100)

    taux_conformite_moyen = (sum(taux_list) / len(taux_list)) if taux_list else 0.0

    return DashboardAuditOut(
        total_programmes=total_programmes,
        taux_realisation=round(taux_realisation, 1),
        repartition_statuts=repartition_statuts,
        total_non_conformites=total_non_conformites,
        repartition_non_conformites=repartition_non_conformites,
        taux_conformite_moyen=round(taux_conformite_moyen, 1),
        repartition_par_service=repartition_par_service,
    )


@router.get("/programs/{program_id}", response_model=AuditProgramOut)
def get_program(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    program = db.query(AuditProgram).filter(AuditProgram.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programme introuvable")

    if not _can_view_program(db, program, current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à Qualité ou au responsable désigné")

    return _program_to_out(program)


@router.patch("/programs/{program_id}", response_model=AuditProgramOut)
def update_program(
    program_id: int,
    payload: AuditProgramUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("audits", "manage_programs")),
):
    """Modification possible à tout moment de l'année — dates, statut,
    notes — sans verrouillage particulier."""
    program = db.query(AuditProgram).filter(AuditProgram.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programme introuvable")

    if payload.statut is not None and payload.statut not in STATUTS_PROGRAMME_VALIDES:
        raise HTTPException(status_code=400, detail=f"Statut invalide ({', '.join(STATUTS_PROGRAMME_VALIDES)})")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(program, field, value)

    db.commit()
    db.refresh(program)
    return _program_to_out(program)


@router.patch("/programs/{program_id}/responsable", response_model=AuditProgramOut)
def assign_responsable(
    program_id: int,
    payload: AssignResponsableRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permission("audits", "manage_programs")),
):
    program = db.query(AuditProgram).filter(AuditProgram.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programme introuvable")

    responsable = db.query(User).filter(User.email == payload.responsable_email).first()
    if not responsable:
        raise HTTPException(status_code=404, detail=f"Utilisateur introuvable : {payload.responsable_email}")

    program.responsable_id = responsable.id
    db.commit()
    db.refresh(program)
    return _program_to_out(program)


def _grid_to_out(grid: AuditGrid, db: Session) -> AuditGridOut:
    criteres = db.query(AuditGridCriteria).filter(AuditGridCriteria.grid_id == grid.id).all()
    return AuditGridOut(
        id=grid.id,
        program_id=grid.program_id,
        nom=grid.nom,
        criteres=[{"id": c.id, "libelle": c.libelle, "ponderation": c.ponderation} for c in criteres],
        date_creation=grid.date_creation,
    )


@router.post("/grids", response_model=AuditGridOut, status_code=201)
def create_grid(
    payload: AuditGridCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("audits", "manage_programs")),
):
    program = db.query(AuditProgram).filter(AuditProgram.id == payload.program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programme introuvable")

    if not payload.criteres:
        raise HTTPException(status_code=400, detail="Au moins un critère est requis")

    grid = AuditGrid(program_id=payload.program_id, nom=payload.nom)
    db.add(grid)
    db.commit()
    db.refresh(grid)

    for c in payload.criteres:
        db.add(AuditGridCriteria(grid_id=grid.id, libelle=c.libelle, ponderation=c.ponderation))
    db.commit()

    return _grid_to_out(grid, db)


@router.get("/programs/{program_id}/grids", response_model=list[AuditGridOut])
def list_grids_for_program(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    program = db.query(AuditProgram).filter(AuditProgram.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programme introuvable")

    if not _can_access_program(db, program, current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à Qualité ou au responsable désigné")

    grids = db.query(AuditGrid).filter(AuditGrid.program_id == program_id).all()
    return [_grid_to_out(g, db) for g in grids]


@router.get("/grids/{grid_id}", response_model=AuditGridOut)
def get_grid(
    grid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grid = db.query(AuditGrid).filter(AuditGrid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grille introuvable")

    if not _can_access_program(db, grid.program, current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à Qualité ou au responsable désigné")

    return _grid_to_out(grid, db)


@router.post("/grids/{grid_id}/findings", response_model=FindingOut, status_code=201)
def submit_finding(
    grid_id: int,
    payload: FindingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grid = db.query(AuditGrid).filter(AuditGrid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grille introuvable")

    if not _can_access_program(db, grid.program, current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à Qualité ou au responsable désigné")

    criteria = (
        db.query(AuditGridCriteria)
        .filter(AuditGridCriteria.id == payload.criteria_id, AuditGridCriteria.grid_id == grid_id)
        .first()
    )
    if not criteria:
        raise HTTPException(status_code=404, detail="Critère introuvable sur cette grille")

    if not payload.conforme and payload.classification not in CLASSIFICATIONS_VALIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Classification requise si non conforme ({', '.join(CLASSIFICATIONS_VALIDES)})",
        )

    existing = (
        db.query(AuditFinding)
        .filter(AuditFinding.grid_id == grid_id, AuditFinding.criteria_id == payload.criteria_id)
        .first()
    )
    if existing:
        existing.conforme = payload.conforme
        existing.classification = payload.classification if not payload.conforme else None
        existing.observation = payload.observation
        existing.preuves = payload.preuves
        db.commit()
        db.refresh(existing)
        finding = existing
    else:
        finding = AuditFinding(
            grid_id=grid_id,
            criteria_id=payload.criteria_id,
            conforme=payload.conforme,
            classification=payload.classification if not payload.conforme else None,
            observation=payload.observation,
            preuves=payload.preuves,
            auteur_id=current_user.id,
        )
        db.add(finding)
        db.commit()
        db.refresh(finding)

    return FindingOut(
        id=finding.id,
        criteria_id=finding.criteria_id,
        criteria_libelle=criteria.libelle,
        conforme=finding.conforme,
        classification=finding.classification,
        observation=finding.observation,
        preuves=finding.preuves,
        auteur_email=finding.auteur.email,
        date_creation=finding.date_creation,
    )


@router.get("/grids/{grid_id}/findings", response_model=list[FindingOut])
def list_findings(
    grid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grid = db.query(AuditGrid).filter(AuditGrid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grille introuvable")

    if not _can_access_program(db, grid.program, current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à Qualité ou au responsable désigné")

    findings = db.query(AuditFinding).filter(AuditFinding.grid_id == grid_id).all()
    return [
        FindingOut(
            id=f.id,
            criteria_id=f.criteria_id,
            criteria_libelle=db.query(AuditGridCriteria).filter(AuditGridCriteria.id == f.criteria_id).first().libelle,
            conforme=f.conforme,
            classification=f.classification,
            observation=f.observation,
            preuves=f.preuves,
            auteur_email=f.auteur.email,
            date_creation=f.date_creation,
        )
        for f in findings
    ]


@router.get("/grids/{grid_id}/conformite", response_model=ConformiteOut)
def get_conformite(
    grid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grid = db.query(AuditGrid).filter(AuditGrid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grille introuvable")

    if not _can_access_program(db, grid.program, current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à Qualité ou au responsable désigné")

    criteres = db.query(AuditGridCriteria).filter(AuditGridCriteria.grid_id == grid_id).all()
    findings = db.query(AuditFinding).filter(AuditFinding.grid_id == grid_id).all()
    findings_by_criteria = {f.criteria_id: f for f in findings}

    points_total = sum(c.ponderation for c in criteres)
    points_obtenus = sum(
        c.ponderation
        for c in criteres
        if c.id in findings_by_criteria and findings_by_criteria[c.id].conforme
    )
    taux = (points_obtenus / points_total * 100) if points_total > 0 else 0.0

    return ConformiteOut(
        grid_id=grid_id,
        points_obtenus=points_obtenus,
        points_total=points_total,
        taux_conformite=round(taux, 1),
        nb_criteres_evalues=len(findings),
        nb_criteres_total=len(criteres),
    )


def _finding_to_action_out(action: AuditAction) -> AuditActionOut:
    return AuditActionOut(
        id=action.id,
        finding_id=action.finding_id,
        description=action.description,
        responsable_email=action.responsable.email,
        echeance=action.echeance,
        statut=action.statut,
        date_creation=action.date_creation,
    )


@router.get("/actions/mine", response_model=list[AuditActionOut])
def list_my_audit_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    actions = db.query(AuditAction).filter(AuditAction.responsable_id == current_user.id).all()
    return [_finding_to_action_out(a) for a in actions]


@router.post("/findings/{finding_id}/actions", response_model=AuditActionOut, status_code=201)
def create_audit_action(
    finding_id: int,
    payload: AuditActionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    finding = db.query(AuditFinding).filter(AuditFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Constat introuvable")

    grid = db.query(AuditGrid).filter(AuditGrid.id == finding.grid_id).first()
    if not _can_access_program(db, grid.program, current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à Qualité ou au responsable désigné")

    if finding.conforme:
        raise HTTPException(status_code=400, detail="Ce constat est conforme, aucune action corrective nécessaire")

    responsable = db.query(User).filter(User.email == payload.responsable_email).first()
    if not responsable:
        raise HTTPException(status_code=404, detail=f"Utilisateur introuvable : {payload.responsable_email}")

    action = AuditAction(
        finding_id=finding_id,
        description=payload.description,
        responsable_id=responsable.id,
        echeance=payload.echeance,
        statut="a_faire",
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    notify(
        db,
        user_id=responsable.id,
        template_name="action_assignee",
        context={"objet": f"Non-conformité audit : {payload.description[:50]}"},
        lien=f"/audits/{grid.program_id}/grille",
    )

    return _finding_to_action_out(action)


@router.get("/grids/{grid_id}/non-conformites", response_model=list[FindingOut])
def list_non_conformites(
    grid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    grid = db.query(AuditGrid).filter(AuditGrid.id == grid_id).first()
    if not grid:
        raise HTTPException(status_code=404, detail="Grille introuvable")

    if not _can_access_program(db, grid.program, current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à Qualité ou au responsable désigné")

    findings = (
        db.query(AuditFinding)
        .filter(AuditFinding.grid_id == grid_id, AuditFinding.conforme == False)  # noqa: E712
        .all()
    )
    return [
        FindingOut(
            id=f.id,
            criteria_id=f.criteria_id,
            criteria_libelle=db.query(AuditGridCriteria).filter(AuditGridCriteria.id == f.criteria_id).first().libelle,
            conforme=f.conforme,
            classification=f.classification,
            observation=f.observation,
            preuves=f.preuves,
            auteur_email=f.auteur.email,
            date_creation=f.date_creation,
        )
        for f in findings
    ]


@router.get("/findings/{finding_id}/actions", response_model=list[AuditActionOut])
def list_finding_actions(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    finding = db.query(AuditFinding).filter(AuditFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Constat introuvable")

    grid = db.query(AuditGrid).filter(AuditGrid.id == finding.grid_id).first()
    if not _can_access_program(db, grid.program, current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à Qualité ou au responsable désigné")

    actions = db.query(AuditAction).filter(AuditAction.finding_id == finding_id).all()
    return [_finding_to_action_out(a) for a in actions]


@router.patch("/actions/{action_id}/status", response_model=AuditActionOut)
def update_audit_action_status(
    action_id: int,
    payload: AuditActionStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = db.query(AuditAction).filter(AuditAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action introuvable")

    if action.responsable_id != current_user.id and not _is_qualite(db, current_user):
        raise HTTPException(
            status_code=403,
            detail="Seul le responsable de l'action ou le service Qualité peut modifier son statut",
        )

    if payload.statut not in STATUTS_AUDIT_ACTION_VALIDES:
        raise HTTPException(status_code=400, detail=f"Statut invalide ({', '.join(STATUTS_AUDIT_ACTION_VALIDES)})")

    action.statut = payload.statut
    db.commit()
    db.refresh(action)

    return _finding_to_action_out(action)


@router.patch("/programs/{program_id}/close", response_model=AuditProgramOut)
def close_audit_program(
    program_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("audits", "manage_programs")),
):
    """Clôture l'audit : exige que toutes les non-conformités relevées
    aient au moins une action corrective définie, puis verrouille le
    rapport (plus aucune modification possible sur les grilles/constats)."""
    program = db.query(AuditProgram).filter(AuditProgram.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programme introuvable")

    grids = db.query(AuditGrid).filter(AuditGrid.program_id == program_id).all()
    for grid in grids:
        non_conformites = (
            db.query(AuditFinding)
            .filter(AuditFinding.grid_id == grid.id, AuditFinding.conforme == False)  # noqa: E712
            .all()
        )
        for nc in non_conformites:
            has_action = db.query(AuditAction).filter(AuditAction.finding_id == nc.id).first()
            if not has_action:
                raise HTTPException(
                    status_code=400,
                    detail=f"Une action corrective est requise pour toutes les non-conformités avant clôture (constat #{nc.id} manquant)",
                )

    program.statut = "realise"
    program.rapport_verrouille = True
    program.date_cloture = datetime.utcnow()
    db.commit()
    db.refresh(program)

    return _program_to_out(program)


@router.get("/programs/{program_id}/report/pdf")
def generate_report(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    program = db.query(AuditProgram).filter(AuditProgram.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programme introuvable")

    if not _can_access_program(db, program, current_user):
        raise HTTPException(status_code=403, detail="Accès réservé à Qualité ou au responsable désigné")

    grids = db.query(AuditGrid).filter(AuditGrid.program_id == program_id).all()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    cible = program.service.nom if program.service else (program.processus or program.thematique)
    elements = [
        Paragraph(f"Rapport d'audit — {cible} ({program.annee})", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Statut : {program.statut}", styles["Normal"]),
        Spacer(1, 12),
    ]

    for grid in grids:
        elements.append(Paragraph(grid.nom, styles["Heading2"]))
        criteres = db.query(AuditGridCriteria).filter(AuditGridCriteria.grid_id == grid.id).all()
        findings = {f.criteria_id: f for f in db.query(AuditFinding).filter(AuditFinding.grid_id == grid.id).all()}

        data = [["Critère", "Points", "Résultat", "Classification", "Observation"]]
        for c in criteres:
            f = findings.get(c.id)
            data.append([
                c.libelle,
                str(c.ponderation),
                "Conforme" if f and f.conforme else "Non conforme" if f else "Non évalué",
                f.classification if f and f.classification else "-",
                (f.observation[:60] if f and f.observation else "-"),
            ])

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00543f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 20))

    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=rapport_audit_{program_id}.pdf"},
    )