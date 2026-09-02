from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth_router import router as auth_router
from app.core.config import settings
from app.core.roles_router import router as roles_router
from app.core.scheduler import start_scheduler
from app.core.status_engine import router as history_router

from app.documentaire.router import router as documentaire_router

app = FastAPI(title="QUALITE-UM6PH — Plateforme Qualité UM6P Hospitals")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(roles_router, prefix="/admin", tags=["admin"])
app.include_router(history_router, prefix="/history", tags=["history"])
app.include_router(documentaire_router, prefix="/documents", tags=["documentaire"])


@app.on_event("startup")
def on_startup():
    start_scheduler()


@app.get("/health")
def health():
    return {"status": "ok"}
