import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.security import get_current_user

router = APIRouter()

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".xlsx", ".xls"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 Mo


@router.post("/uploads")
async def upload_file(
    file: UploadFile = File(...),
    _current_user=Depends(get_current_user),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non autorisé ({ext}). Autorisés : {', '.join(ALLOWED_EXTENSIONS)}",
        )

    contents = await file.read()
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 10 Mo)")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, stored_name)
    with open(path, "wb") as f:
        f.write(contents)

    return {"filename": file.filename, "stored_name": stored_name, "url": f"/uploaded_files/{stored_name}"}