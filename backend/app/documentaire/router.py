from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Role, Service, User, UserRole
from app.core.security import get_current_user
from app.core.status_engine import ObjectType, change_status, notify
from app.documentaire.models import Document, DocumentRequest
from app.documentaire.schemas import DocumentRequestCreate, DocumentRequestOut, ServiceOut

router = APIRouter()


@router.get("/services", response_model=list[ServiceOut])
def list_services(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """Liste de référence pour peupler le sélecteur de service côté
    frontend. Simple lecture, aucune permission spécifique requise au-delà
    d'être connecté."""
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

    # 1. Créer le document lui-même, statut initial
    document = Document(
        intitule=payload.intitule,
        type_document=payload.type_document,
        service_id=payload.service_id,
        statut="en_attente_examen",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # 2. Créer la demande associée
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

    # 3. Tracer le statut initial dans l'historique générique
    change_status(
        db,
        object_type=ObjectType.document,
        object_id=document.id,
        ancien_statut=None,
        nouveau_statut="en_attente_examen",
        user_id=current_user.id,
    )

    # 4. Notifier le responsable de service désigné
    notify(
        db,
        user_id=responsable.id,
        template_name="nouvelle_demande",
        context={"objet": payload.intitule},
        lien=f"/documents/requests/{doc_request.id}",
    )

    # 5. Notifier tous les profils Qualité
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
