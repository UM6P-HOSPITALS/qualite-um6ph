from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Role, Service, User, UserRole
from app.core.security import get_current_user
from app.core.status_engine import ObjectType, change_status, notify
from app.documentaire.models import Document, DocumentAssignment, DocumentRequest
from app.documentaire.schemas import (
    DocumentAcceptRequest,
    DocumentRejectRequest,
    DocumentRequestCreate,
    DocumentRequestOut,
    DocumentRequestPendingOut,
    ServiceOut,
)

router = APIRouter()


@router.get("/services", response_model=list[ServiceOut])
def list_services(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return db.query(Service).all()


@router.post("/requests", response_model=DocumentRequestOut, status_code=201)
def create_request(
    payload: DocumentRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = db.query(Service).filter(Service.id == payload.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service introuvable")

    responsable = db.query(User).filter(User.email == payload.responsable_email).first()
    if not responsable:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun utilisateur avec l'email {payload.responsable_email}",
        )

    document = Document(
        intitule=payload.intitule,
        type_document=payload.type_document,
        service_id=payload.service_id,
        statut="en_attente_examen",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    doc_request = DocumentRequest(
        document_id=document.id,
        nature=payload.nature,
        justification=payload.justification,
        demandeur_id=current_user.id,
        responsable_id=responsable.id,
        statut="en_attente_examen",
        pieces_jointes=payload.pieces_jointes,
    )
    db.add(doc_request)
    db.commit()
    db.refresh(doc_request)

    change_status(
        db,
        object_type=ObjectType.document,
        object_id=document.id,
        ancien_statut=None,
        nouveau_statut="en_attente_examen",
        user_id=current_user.id,
    )

    notify(
        db,
        user_id=responsable.id,
        template_name="nouvelle_demande",
        context={"objet": payload.intitule},
        lien=f"/documents/requests/{doc_request.id}",
    )

    qualite_role = db.query(Role).filter(Role.nom == "qualite").first()
    if qualite_role:
        qualite_user_ids = [
            ur.user_id
            for ur in db.query(UserRole).filter(UserRole.role_id == qualite_role.id).all()
        ]
        for uid in qualite_user_ids:
            notify(
                db,
                user_id=uid,
                template_name="nouvelle_demande",
                context={"objet": payload.intitule},
                lien=f"/documents/requests/{doc_request.id}",
            )

    return doc_request


@router.get("/requests/pending", response_model=list[DocumentRequestPendingOut])
def list_pending_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Demandes en attente d'examen, assignées à l'utilisateur connecté en
    tant que responsable de service."""
    requests = (
        db.query(DocumentRequest)
        .filter(
            DocumentRequest.responsable_id == current_user.id,
            DocumentRequest.statut == "en_attente_examen",
        )
        .all()
    )
    return [
        DocumentRequestPendingOut(
            id=r.id,
            document_id=r.document_id,
            intitule=r.document.intitule,
            nature=r.nature,
            type_document=r.document.type_document,
            justification=r.justification,
            demandeur_email=r.demandeur.email,
            date=r.date,
        )
        for r in requests
    ]


def _get_request_or_404(db: Session, request_id: int) -> DocumentRequest:
    doc_request = db.query(DocumentRequest).filter(DocumentRequest.id == request_id).first()
    if not doc_request:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    return doc_request


def _check_is_responsable(doc_request: DocumentRequest, current_user: User):
    if doc_request.responsable_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Seul le responsable désigné peut examiner cette demande",
        )


@router.patch("/requests/{request_id}/accept", response_model=DocumentRequestOut)
def accept_request(
    request_id: int,
    payload: DocumentAcceptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc_request = _get_request_or_404(db, request_id)
    _check_is_responsable(doc_request, current_user)

    if doc_request.statut != "en_attente_examen":
        raise HTTPException(status_code=400, detail="Cette demande a déjà été traitée")

    def _resolve_users(emails: list[str]) -> list[User]:
        users = []
        for email in emails:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"Utilisateur introuvable : {email}")
            users.append(user)
        return users

    redacteurs = _resolve_users(payload.redacteur_emails)
    verificateurs = _resolve_users(payload.verificateur_emails)
    approbateurs = _resolve_users(payload.approbateur_emails)

    for user in redacteurs:
        db.add(DocumentAssignment(document_id=doc_request.document_id, user_id=user.id, role_document="redacteur"))
    for user in verificateurs:
        db.add(DocumentAssignment(document_id=doc_request.document_id, user_id=user.id, role_document="verificateur"))
    for user in approbateurs:
        db.add(DocumentAssignment(document_id=doc_request.document_id, user_id=user.id, role_document="approbateur"))

    document = doc_request.document
    document.perimetre = payload.perimetre
    document.confidentialite = payload.confidentialite

    ancien_statut = doc_request.statut
    doc_request.statut = "en_cours_redaction"
    document.statut = "en_cours_redaction"
    db.commit()

    change_status(
        db,
        object_type=ObjectType.document,
        object_id=document.id,
        ancien_statut=ancien_statut,
        nouveau_statut="en_cours_redaction",
        user_id=current_user.id,
    )

    for user in redacteurs + verificateurs:
        notify(
            db,
            user_id=user.id,
            template_name="nouvelle_demande",
            context={"objet": document.intitule},
            lien=f"/documents/{document.id}",
        )

    db.refresh(doc_request)
    return doc_request


@router.patch("/requests/{request_id}/reject", response_model=DocumentRequestOut)
def reject_request(
    request_id: int,
    payload: DocumentRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc_request = _get_request_or_404(db, request_id)
    _check_is_responsable(doc_request, current_user)

    if doc_request.statut != "en_attente_examen":
        raise HTTPException(status_code=400, detail="Cette demande a déjà été traitée")

    document = doc_request.document
    ancien_statut = doc_request.statut

    doc_request.statut = "rejetee"
    doc_request.motif_rejet = payload.motif
    document.statut = "rejetee"
    db.commit()

    change_status(
        db,
        object_type=ObjectType.document,
        object_id=document.id,
        ancien_statut=ancien_statut,
        nouveau_statut="rejetee",
        user_id=current_user.id,
        commentaire=payload.motif,
    )

    notify(
        db,
        user_id=doc_request.demandeur_id,
        template_name="nouvelle_demande",
        context={"objet": f"Rejetée : {document.intitule} ({payload.motif})"},
        lien=f"/documents/requests/{doc_request.id}",
    )

    db.refresh(doc_request)
    return doc_request