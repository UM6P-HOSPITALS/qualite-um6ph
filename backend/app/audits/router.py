from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Role, Service, User, UserRole
from app.core.permissions import require_permission
from app.core.security import get_current_user
from app.audits.models import AuditProgram
from app.audits.schemas import (
    AssignResponsableRequest,
    AuditProgramCreate,
    AuditProgramOut,
    AuditProgramUpdate,
)

STATUTS_PROGRAMME_VALIDES = ("planifie", "en_cours", "realise")

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