from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Role, Service, User, UserRole
from app.core.permissions import require_permission
from app.core.security import get_current_user
from app.core.status_engine import ObjectType, change_status, notify
import hashlib

from app.documentaire.models import (
    Document,
    DocumentAssignment,
    DocumentComment,
    DocumentRequest,
    DocumentSignature,
    DocumentTemplate,
)
from app.documentaire.schemas import (
    CommentCreate,
    CommentOut,
    DocumentAcceptRequest,
    DocumentDetailOut,
    DocumentRejectRequest,
    DocumentRequestCreate,
    DocumentRequestOut,
    DocumentRequestPendingOut,
    DocumentTemplateCreate,
    DocumentTemplateOut,
    DocumentTemplateUpdate,
    DraftSave,
    ServiceOut,
    SignatureOut,
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


# ---------- Templates (réservé Qualité) ----------

@router.get("/templates", response_model=list[DocumentTemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Lecture ouverte à tout utilisateur connecté (les rédacteurs en ont
    besoin), seule la modification est réservée Qualité."""
    return db.query(DocumentTemplate).all()


@router.post("/templates", response_model=DocumentTemplateOut, status_code=201)
def create_template(
    payload: DocumentTemplateCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_templates")),
):
    template = DocumentTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.patch("/templates/{template_id}", response_model=DocumentTemplateOut)
def update_template(
    template_id: int,
    payload: DocumentTemplateUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_templates")),
):
    template = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_templates")),
):
    template = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template introuvable")
    db.delete(template)
    db.commit()


# ---------- Rédaction ----------

def _check_is_redacteur(db: Session, document_id: int, current_user: User):
    assignment = (
        db.query(DocumentAssignment)
        .filter(
            DocumentAssignment.document_id == document_id,
            DocumentAssignment.user_id == current_user.id,
            DocumentAssignment.role_document == "redacteur",
        )
        .first()
    )
    if not assignment:
        raise HTTPException(
            status_code=403,
            detail="Seul un rédacteur assigné à ce document peut le modifier",
        )


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return document


@router.patch("/{document_id}/draft", response_model=DocumentDetailOut)
def save_draft(
    document_id: int,
    payload: DraftSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    _check_is_redacteur(db, document_id, current_user)

    document.contenu = payload.contenu
    db.commit()
    db.refresh(document)
    return document

def _get_assignment(db: Session, document_id: int, user_id: int, role_document: str):
    return (
        db.query(DocumentAssignment)
        .filter(
            DocumentAssignment.document_id == document_id,
            DocumentAssignment.user_id == user_id,
            DocumentAssignment.role_document == role_document,
        )
        .first()
    )


@router.patch("/{document_id}/submit-review", response_model=DocumentDetailOut)
def submit_review(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    if not _get_assignment(db, document_id, current_user.id, "redacteur"):
        raise HTTPException(status_code=403, detail="Seul un rédacteur assigné peut soumettre à vérification")

    if document.statut != "en_cours_redaction":
        raise HTTPException(status_code=400, detail="Le document n'est pas en cours de rédaction")

    ancien_statut = document.statut
    document.statut = "en_cours_verification"
    db.commit()

    change_status(
        db,
        object_type=ObjectType.document,
        object_id=document.id,
        ancien_statut=ancien_statut,
        nouveau_statut="en_cours_verification",
        user_id=current_user.id,
    )

    verificateurs = (
        db.query(DocumentAssignment)
        .filter(
            DocumentAssignment.document_id == document_id,
            DocumentAssignment.role_document == "verificateur",
        )
        .all()
    )
    for v in verificateurs:
        notify(
            db,
            user_id=v.user_id,
            template_name="a_verifier",
            context={"objet": document.intitule},
            lien=f"/documents/{document.id}/verification",
        )

    db.refresh(document)
    return document


@router.get("/{document_id}/comments", response_model=list[CommentOut])
def list_comments(
    document_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    comments = (
        db.query(DocumentComment)
        .filter(DocumentComment.document_id == document_id)
        .order_by(DocumentComment.date)
        .all()
    )
    return [
        CommentOut(id=c.id, user_email=c.user.email, contenu=c.contenu, date=c.date)
        for c in comments
    ]


@router.post("/{document_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    document_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    is_redacteur = _get_assignment(db, document_id, current_user.id, "redacteur")
    is_verificateur = _get_assignment(db, document_id, current_user.id, "verificateur")
    if not is_redacteur and not is_verificateur:
        raise HTTPException(status_code=403, detail="Vous n'êtes pas assigné à ce document")

    comment = DocumentComment(document_id=document_id, user_id=current_user.id, contenu=payload.contenu)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return CommentOut(id=comment.id, user_email=current_user.email, contenu=comment.contenu, date=comment.date)


@router.patch("/{document_id}/return-to-author", response_model=DocumentDetailOut)
def return_to_author(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    if not _get_assignment(db, document_id, current_user.id, "verificateur"):
        raise HTTPException(status_code=403, detail="Seul un vérificateur assigné peut retourner le document")

    if document.statut != "en_cours_verification":
        raise HTTPException(status_code=400, detail="Le document n'est pas en cours de vérification")

    ancien_statut = document.statut
    document.statut = "en_cours_redaction"
    db.commit()

    change_status(
        db,
        object_type=ObjectType.document,
        object_id=document.id,
        ancien_statut=ancien_statut,
        nouveau_statut="en_cours_redaction",
        user_id=current_user.id,
        commentaire="Retourné au rédacteur avec commentaires",
    )

    redacteurs = (
        db.query(DocumentAssignment)
        .filter(
            DocumentAssignment.document_id == document_id,
            DocumentAssignment.role_document == "redacteur",
        )
        .all()
    )
    for r in redacteurs:
        notify(
            db,
            user_id=r.user_id,
            template_name="a_verifier",
            context={"objet": f"Retourné avec commentaires : {document.intitule}"},
            lien=f"/documents/{document.id}/redaction",
        )

    db.refresh(document)
    return document

def _assigned_roles(db: Session, document_id: int, user_id: int) -> list[str]:
    assignments = (
        db.query(DocumentAssignment)
        .filter(
            DocumentAssignment.document_id == document_id,
            DocumentAssignment.user_id == user_id,
        )
        .all()
    )
    return [a.role_document for a in assignments]


def _check_all_signed(db: Session, document: Document) -> bool:
    """Vérifie que tous les rédacteurs ET tous les vérificateurs assignés
    ont signé. Si oui, fait passer le document au statut 'verifie'."""
    assignments = (
        db.query(DocumentAssignment)
        .filter(
            DocumentAssignment.document_id == document.id,
            DocumentAssignment.role_document.in_(["redacteur", "verificateur"]),
        )
        .all()
    )
    required = {(a.user_id, a.role_document) for a in assignments}

    signatures = (
        db.query(DocumentSignature)
        .filter(DocumentSignature.document_id == document.id)
        .all()
    )
    signed = {(s.user_id, s.role_signataire) for s in signatures}

    return required.issubset(signed) and len(required) > 0


@router.post("/{document_id}/sign", response_model=SignatureOut, status_code=201)
def sign_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    if document.statut != "en_cours_verification":
        raise HTTPException(
            status_code=400,
            detail="Le document doit être en cours de vérification pour être signé",
        )

    roles = _assigned_roles(db, document_id, current_user.id)
    role_signataire = None
    if "redacteur" in roles:
        role_signataire = "redacteur"
    elif "verificateur" in roles:
        role_signataire = "verificateur"

    if not role_signataire:
        raise HTTPException(
            status_code=403,
            detail="Seul un rédacteur ou vérificateur assigné peut signer",
        )

    already = (
        db.query(DocumentSignature)
        .filter(
            DocumentSignature.document_id == document_id,
            DocumentSignature.user_id == current_user.id,
            DocumentSignature.role_signataire == role_signataire,
        )
        .first()
    )
    if already:
        raise HTTPException(status_code=400, detail="Vous avez déjà signé ce document")

    hash_contenu = hashlib.sha256((document.contenu or "").encode("utf-8")).hexdigest()

    signature = DocumentSignature(
        document_id=document_id,
        user_id=current_user.id,
        role_signataire=role_signataire,
        hash_contenu=hash_contenu,
    )
    db.add(signature)
    db.commit()
    db.refresh(signature)

    if _check_all_signed(db, document):
        ancien_statut = document.statut
        document.statut = "verifie"
        db.commit()
        change_status(
            db,
            object_type=ObjectType.document,
            object_id=document.id,
            ancien_statut=ancien_statut,
            nouveau_statut="verifie",
            user_id=current_user.id,
        )

    return SignatureOut(
        id=signature.id,
        user_email=current_user.email,
        role_signataire=signature.role_signataire,
        date=signature.date,
    )


@router.get("/{document_id}/signatures", response_model=list[SignatureOut])
def list_signatures(
    document_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    signatures = (
        db.query(DocumentSignature)
        .filter(DocumentSignature.document_id == document_id)
        .all()
    )
    return [
        SignatureOut(id=s.id, user_email=s.user.email, role_signataire=s.role_signataire, date=s.date)
        for s in signatures
    ]


@router.post("/{document_id}/assignments", status_code=201)
def add_assignment(
    document_id: int,
    email: str,
    role_document: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_assignments")),
):
    """Ajouter un vérificateur en cours de route (réservé Qualité)."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    existing = (
        db.query(DocumentAssignment)
        .filter(
            DocumentAssignment.document_id == document_id,
            DocumentAssignment.user_id == user.id,
            DocumentAssignment.role_document == role_document,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Déjà assigné avec ce rôle")

    assignment = DocumentAssignment(document_id=document_id, user_id=user.id, role_document=role_document)
    db.add(assignment)
    db.commit()

    notify(
        db,
        user_id=user.id,
        template_name="a_verifier",
        context={"objet": document.intitule},
        lien=f"/documents/{document.id}/verification",
    )

    return {"message": f"{email} assigné comme {role_document}"}


@router.delete("/{document_id}/assignments/{assignment_id}", status_code=204)
def remove_assignment(
    document_id: int,
    assignment_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_assignments")),
):
    """Retirer un vérificateur en cours de route (réservé Qualité)."""
    assignment = (
        db.query(DocumentAssignment)
        .filter(DocumentAssignment.id == assignment_id, DocumentAssignment.document_id == document_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignation introuvable")

    db.delete(assignment)
    db.commit()