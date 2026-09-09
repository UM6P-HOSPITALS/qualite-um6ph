import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Role, Service, User, UserRole
from app.core.permissions import require_permission
from app.core.security import get_current_user, verify_password
from app.core.status_engine import ObjectType, change_status, notify
from app.documentaire.models import (
    AttendanceList,
    AttendanceParticipant,
    CapsuleView,
    Document,
    DocumentAssignment,
    DocumentComment,
    DocumentRead,
    DocumentRequest,
    DocumentSignature,
    DocumentTemplate,
    DocumentValidation,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    TrainingCapsule,
    ValidationCircuit,
)
from app.documentaire.schemas import (
    AttendanceListCreate,
    AttendanceListOut,
    CommentCreate,
    CommentOut,
    DocumentAcceptRequest,
    DocumentApplicableOut,
    DocumentDetailOut,
    DocumentRejectRequest,
    DocumentRequestCreate,
    DocumentRequestOut,
    DocumentRequestPendingOut,
    DocumentSearchResultOut,
    DocumentTemplateCreate,
    DocumentTemplateOut,
    DocumentTemplateUpdate,
    DraftSave,
    QuizAnswerSubmit,
    QuizAttemptOut,
    QuizCreate,
    QuizOut,
    QuizQuestionOut,
    QuizResultAnonymeOut,
    ReadStatusOut,
    ServiceOut,
    SignatureConfirm,
    SignatureOut,
    TrainingCapsuleCreate,
    TrainingCapsuleOut,
    ValidationCircuitCreate,
    ValidationCircuitOut,
    ValidationConfirm,
    ValidationOut,
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
        document_parent_id=payload.document_parent_id,
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


@router.get("/applicable", response_model=list[DocumentApplicableOut])
def list_applicable_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Documents diffusés, filtrés par les services de l'utilisateur
    connecté (via ses rôles). Indique aussi s'il l'a déjà lu."""
    service_ids = {ur.service_id for ur in current_user.roles if ur.service_id is not None}

    query = db.query(Document).filter(Document.statut == "diffuse")
    if service_ids:
        query = query.filter(Document.service_id.in_(service_ids))

    documents = query.all()

    read_ids = {
        r.document_id
        for r in db.query(DocumentRead).filter(DocumentRead.user_id == current_user.id).all()
    }

    return [
        DocumentApplicableOut(
            id=d.id,
            intitule=d.intitule,
            type_document=d.type_document,
            service_nom=d.service.nom,
            date_diffusion=d.date_diffusion,
            deja_lu=d.id in read_ids,
        )
        for d in documents
    ]


@router.get("/search", response_model=list[DocumentSearchResultOut])
def search_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    keyword: str | None = None,
    type_document: str | None = None,
    service_id: int | None = None,
    auteur_email: str | None = None,
):
    """Recherche multicritère. Seuls les documents diffusés sont visibles
    par défaut, sauf pour Qualité qui voit aussi les autres statuts.
    La confidentialité restreinte/confidentielle est filtrée : seul un
    utilisateur ayant un rôle sur le service concerné y accède."""
    is_qualite = (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == current_user.id, Role.nom == "qualite")
        .first()
        is not None
    )

    query = db.query(Document)

    if not is_qualite:
        query = query.filter(Document.statut == "diffuse")

    if keyword:
        query = query.filter(Document.intitule.ilike(f"%{keyword}%"))
    if type_document:
        query = query.filter(Document.type_document == type_document)
    if service_id:
        query = query.filter(Document.service_id == service_id)

    documents = query.all()

    user_service_ids = {ur.service_id for ur in current_user.roles if ur.service_id is not None}

    results = []
    for d in documents:
        if d.confidentialite in ("restreint", "confidentiel") and not is_qualite:
            if d.service_id not in user_service_ids:
                continue

        redacteur_assignment = (
            db.query(DocumentAssignment)
            .filter(
                DocumentAssignment.document_id == d.id,
                DocumentAssignment.role_document == "redacteur",
            )
            .first()
        )
        doc_auteur_email = redacteur_assignment.user.email if redacteur_assignment else None

        if auteur_email and doc_auteur_email != auteur_email:
            continue

        results.append(
            DocumentSearchResultOut(
                id=d.id,
                intitule=d.intitule,
                type_document=d.type_document,
                service_nom=d.service.nom,
                statut=d.statut,
                auteur_email=doc_auteur_email,
            )
        )

    return results


def _is_qualite(db: Session, current_user: User) -> bool:
    return (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == current_user.id, Role.nom == "qualite")
        .first()
        is not None
    )


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    if document.statut == "obsolete":
        is_qualite = _is_qualite(db, current_user)
        is_redacteur = _get_assignment(db, document_id, current_user.id, "redacteur") is not None
        if not is_qualite and not is_redacteur:
            raise HTTPException(
                status_code=403,
                detail="Document obsolète : accès restreint au service Qualité et au rédacteur, en lecture seule",
            )

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
    payload: SignatureConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    if not payload.nom_signature.strip():
        raise HTTPException(status_code=400, detail="Le nom de signature est requis")

    if not payload.certification:
        raise HTTPException(
            status_code=400,
            detail="Vous devez certifier avoir vérifié le document avant de signer",
        )

    if not current_user.password_hash or not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect — signature refusée")

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
        nom_signature=payload.nom_signature.strip(),
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
        nom_signature=signature.nom_signature,
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
        SignatureOut(
            id=s.id,
            user_email=s.user.email,
            role_signataire=s.role_signataire,
            nom_signature=s.nom_signature,
            date=s.date,
        )
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
    assignment = (
        db.query(DocumentAssignment)
        .filter(DocumentAssignment.id == assignment_id, DocumentAssignment.document_id == document_id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignation introuvable")

    db.delete(assignment)
    db.commit()


DIRECTION_ROLES = [
    "direction_generale",
    "direction_medicale",
    "direction_financiere",
    "direction_rh",
]


@router.get("/validation-circuits", response_model=list[ValidationCircuitOut])
def list_validation_circuits(
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_validation_circuits")),
):
    return db.query(ValidationCircuit).all()


@router.post("/validation-circuits", response_model=ValidationCircuitOut, status_code=201)
def create_validation_circuit(
    payload: ValidationCircuitCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_validation_circuits")),
):
    if payload.role_direction not in DIRECTION_ROLES:
        raise HTTPException(status_code=400, detail=f"role_direction doit être l'un de {DIRECTION_ROLES}")

    circuit = ValidationCircuit(type_document=payload.type_document, role_direction=payload.role_direction)
    db.add(circuit)
    db.commit()
    db.refresh(circuit)
    return circuit


@router.delete("/validation-circuits/{circuit_id}", status_code=204)
def delete_validation_circuit(
    circuit_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_validation_circuits")),
):
    circuit = db.query(ValidationCircuit).filter(ValidationCircuit.id == circuit_id).first()
    if not circuit:
        raise HTTPException(status_code=404, detail="Circuit introuvable")
    db.delete(circuit)
    db.commit()


def _required_direction_roles(db: Session, type_document: str) -> list[str]:
    circuits = db.query(ValidationCircuit).filter(ValidationCircuit.type_document == type_document).all()
    return [c.role_direction for c in circuits]


@router.patch("/{document_id}/submit-validation", response_model=DocumentDetailOut)
def submit_validation(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission("documentaire", "submit_validation")),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    if document.statut != "verifie":
        raise HTTPException(status_code=400, detail="Le document doit être vérifié avant soumission à validation")

    required_roles = _required_direction_roles(db, document.type_document)
    if not required_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Aucun circuit de validation configuré pour le type '{document.type_document}'",
        )

    ancien_statut = document.statut
    document.statut = "en_attente_validation"
    db.commit()

    change_status(
        db,
        object_type=ObjectType.document,
        object_id=document.id,
        ancien_statut=ancien_statut,
        nouveau_statut="en_attente_validation",
        user_id=current_user.id,
    )

    for role_nom in required_roles:
        role = db.query(Role).filter(Role.nom == role_nom).first()
        if not role:
            continue
        holders = db.query(UserRole).filter(UserRole.role_id == role.id).all()
        for h in holders:
            notify(
                db,
                user_id=h.user_id,
                template_name="a_verifier",
                context={"objet": f"Validation requise : {document.intitule}"},
                lien=f"/documents/{document.id}/validation",
            )

    db.refresh(document)
    return document


def _check_all_validated(db: Session, document: Document) -> bool:
    required_roles = set(_required_direction_roles(db, document.type_document))
    if not required_roles:
        return False

    validations = (
        db.query(DocumentValidation)
        .filter(DocumentValidation.document_id == document.id)
        .all()
    )
    validated_roles = {v.role_direction for v in validations}

    return required_roles.issubset(validated_roles)


@router.post("/{document_id}/validate", response_model=ValidationOut, status_code=201)
def validate_document(
    document_id: int,
    payload: ValidationConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    if not payload.nom_signature.strip():
        raise HTTPException(status_code=400, detail="Le nom de signature est requis")

    if not payload.certification:
        raise HTTPException(status_code=400, detail="Vous devez certifier avant de valider")

    if not current_user.password_hash or not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect — validation refusée")

    if document.statut != "en_attente_validation":
        raise HTTPException(status_code=400, detail="Le document n'est pas en attente de validation")

    user_role_ids = [ur.role_id for ur in current_user.roles]
    user_role_names = {
        r.nom for r in db.query(Role).filter(Role.id.in_(user_role_ids)).all()
    }
    required_roles = set(_required_direction_roles(db, document.type_document))
    matching_roles = user_role_names.intersection(required_roles)

    if not matching_roles:
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas un rôle de direction requis pour valider ce document",
        )

    role_direction = next(iter(matching_roles))

    already = (
        db.query(DocumentValidation)
        .filter(
            DocumentValidation.document_id == document_id,
            DocumentValidation.role_direction == role_direction,
        )
        .first()
    )
    if already:
        raise HTTPException(status_code=400, detail="Ce rôle de direction a déjà validé ce document")

    validation = DocumentValidation(
        document_id=document_id,
        user_id=current_user.id,
        role_direction=role_direction,
        nom_signature=payload.nom_signature.strip(),
    )
    db.add(validation)
    db.commit()
    db.refresh(validation)

    if _check_all_validated(db, document):
        ancien_statut = document.statut
        document.statut = "valide"
        document.verrouille = True
        db.commit()
        change_status(
            db,
            object_type=ObjectType.document,
            object_id=document.id,
            ancien_statut=ancien_statut,
            nouveau_statut="valide",
            user_id=current_user.id,
        )

    return ValidationOut(
        id=validation.id,
        user_email=current_user.email,
        role_direction=validation.role_direction,
        nom_signature=validation.nom_signature,
        date=validation.date,
    )


@router.get("/{document_id}/validations", response_model=list[ValidationOut])
def list_validations(
    document_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    validations = (
        db.query(DocumentValidation)
        .filter(DocumentValidation.document_id == document_id)
        .all()
    )
    return [
        ValidationOut(
            id=v.id,
            user_email=v.user.email,
            role_direction=v.role_direction,
            nom_signature=v.nom_signature,
            date=v.date,
        )
        for v in validations
    ]


# ---------- Diffusion et lecture ----------

@router.patch("/{document_id}/publish", response_model=DocumentDetailOut)
def publish_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission("documentaire", "publish")),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    if document.statut != "valide":
        raise HTTPException(status_code=400, detail="Le document doit être validé avant diffusion")

    ancien_statut = document.statut
    document.statut = "diffuse"
    document.date_diffusion = datetime.utcnow()

    if document.document_parent_id:
        parent = db.query(Document).filter(Document.id == document.document_parent_id).first()
        if parent:
            parent.statut = "obsolete"

    db.commit()

    change_status(
        db,
        object_type=ObjectType.document,
        object_id=document.id,
        ancien_statut=ancien_statut,
        nouveau_statut="diffuse",
        user_id=current_user.id,
    )

    concerned_user_ids = {
        ur.user_id
        for ur in db.query(UserRole).filter(UserRole.service_id == document.service_id).all()
    }
    for uid in concerned_user_ids:
        notify(
            db,
            user_id=uid,
            template_name="nouvelle_demande",
            context={"objet": f"Nouveau document diffusé : {document.intitule}"},
            lien=f"/documents/{document.id}/lire",
        )

    db.refresh(document)
    return document


@router.post("/{document_id}/mark-read", status_code=201)
def mark_document_read(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    existing = (
        db.query(DocumentRead)
        .filter(DocumentRead.document_id == document_id, DocumentRead.user_id == current_user.id)
        .first()
    )
    if existing:
        return {"message": "Déjà marqué comme lu", "date": existing.date}

    read = DocumentRead(document_id=document_id, user_id=current_user.id)
    db.add(read)
    db.commit()
    return {"message": "Marqué comme lu"}


@router.get("/{document_id}/read-status", response_model=ReadStatusOut)
def get_read_status(
    document_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "view_stats")),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    nb_lecteurs = (
        db.query(DocumentRead).filter(DocumentRead.document_id == document_id).count()
    )
    nb_total_service = (
        db.query(UserRole.user_id)
        .filter(UserRole.service_id == document.service_id)
        .distinct()
        .count()
    )
    taux = (nb_lecteurs / nb_total_service) if nb_total_service > 0 else 0.0

    return ReadStatusOut(nb_lecteurs=nb_lecteurs, nb_total_service=nb_total_service, taux_lecture=round(taux, 2))


# ---------- Capsules vidéo ----------

@router.get("/{document_id}/capsules", response_model=list[TrainingCapsuleOut])
def list_capsules(
    document_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    return db.query(TrainingCapsule).filter(TrainingCapsule.document_id == document_id).all()


@router.post("/{document_id}/capsules", response_model=TrainingCapsuleOut, status_code=201)
def create_capsule(
    document_id: int,
    payload: TrainingCapsuleCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_training")),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    capsule = TrainingCapsule(document_id=document_id, titre=payload.titre, url_video=payload.url_video)
    db.add(capsule)
    db.commit()
    db.refresh(capsule)
    return capsule


@router.post("/capsules/{capsule_id}/view", status_code=201)
def mark_capsule_viewed(
    capsule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    capsule = db.query(TrainingCapsule).filter(TrainingCapsule.id == capsule_id).first()
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule introuvable")

    existing = (
        db.query(CapsuleView)
        .filter(CapsuleView.capsule_id == capsule_id, CapsuleView.user_id == current_user.id)
        .first()
    )
    if existing:
        return {"message": "Déjà visionnée"}

    view = CapsuleView(capsule_id=capsule_id, user_id=current_user.id)
    db.add(view)
    db.commit()
    return {"message": "Visionnage enregistré"}


# ---------- Quiz ----------

@router.post("/{document_id}/quiz", response_model=QuizOut, status_code=201)
def create_quiz(
    document_id: int,
    payload: QuizCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_training")),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    quiz = Quiz(document_id=document_id, titre=payload.titre)
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    questions = []
    for q in payload.questions:
        question = QuizQuestion(
            quiz_id=quiz.id,
            question=q.question,
            choix=q.choix,
            bonne_reponse_index=q.bonne_reponse_index,
        )
        db.add(question)
        questions.append(question)
    db.commit()
    for q in questions:
        db.refresh(q)

    return QuizOut(
        id=quiz.id,
        titre=quiz.titre,
        questions=[QuizQuestionOut(id=q.id, question=q.question, choix=q.choix) for q in questions],
    )


@router.get("/{document_id}/quiz", response_model=QuizOut)
def get_quiz(
    document_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    quiz = db.query(Quiz).filter(Quiz.document_id == document_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Aucun quiz configuré pour ce document")

    questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).all()
    return QuizOut(
        id=quiz.id,
        titre=quiz.titre,
        questions=[QuizQuestionOut(id=q.id, question=q.question, choix=q.choix) for q in questions],
    )


@router.post("/quiz/{quiz_id}/attempt", response_model=QuizAttemptOut, status_code=201)
def submit_quiz_attempt(
    quiz_id: int,
    payload: QuizAnswerSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz introuvable")

    already = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.quiz_id == quiz_id, QuizAttempt.user_id == current_user.id)
        .first()
    )
    if already:
        raise HTTPException(status_code=400, detail="Vous avez déjà passé ce quiz")

    questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz_id)
        .order_by(QuizQuestion.id)
        .all()
    )
    if len(payload.reponses) != len(questions):
        raise HTTPException(status_code=400, detail="Nombre de réponses incohérent avec le nombre de questions")

    score = sum(
        1 for q, rep in zip(questions, payload.reponses) if rep == q.bonne_reponse_index
    )

    attempt = QuizAttempt(quiz_id=quiz_id, user_id=current_user.id, score=score, total=len(questions))
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return QuizAttemptOut(
        id=attempt.id,
        score=attempt.score,
        total=attempt.total,
        date=attempt.date,
    )


@router.get("/quiz/{quiz_id}/results", response_model=list[QuizResultAnonymeOut])
def list_quiz_results(
    quiz_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "view_stats")),
):
    """Résultats agrégés, sans identité des répondants — Qualité voit la
    distribution des scores, pas qui a répondu quoi."""
    attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz_id).all()
    return [
        QuizResultAnonymeOut(score=a.score, total=a.total, date=a.date)
        for a in attempts
    ]


# ---------- Listes de présence ----------

@router.post("/{document_id}/attendance-lists", response_model=AttendanceListOut, status_code=201)
def create_attendance_list(
    document_id: int,
    payload: AttendanceListCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("documentaire", "manage_training")),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    quiz = db.query(Quiz).filter(Quiz.document_id == document_id).first()
    if not quiz:
        raise HTTPException(
            status_code=400,
            detail="Aucun quiz configuré pour ce document — crée le quiz avant la liste de présence",
        )

    attendance = AttendanceList(document_id=document_id)
    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    nb = 0
    for email in payload.participant_emails:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            continue
        db.add(AttendanceParticipant(attendance_list_id=attendance.id, user_id=user.id))
        nb += 1

        # Envoi automatique du quiz à chaque participant
        notify(
            db,
            user_id=user.id,
            template_name="a_verifier",
            context={"objet": f"Quiz à compléter : {document.intitule}"},
            lien=f"/documents/{document_id}/quiz",
        )

    db.commit()

    return AttendanceListOut(id=attendance.id, date_creation=attendance.date_creation, nb_participants=nb)