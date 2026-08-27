from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(title="QUALITE-UM6PH — Plateforme Qualité UM6P Hospitals")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# Les routers des modules métier seront branchés ici au fur et à mesure :
# from app.documentaire.router import router as documentaire_router
# from app.evenements.router import router as evenements_router
# from app.audits.router import router as audits_router
# app.include_router(documentaire_router, prefix="/documents", tags=["documentaire"])
# app.include_router(evenements_router, prefix="/events", tags=["evenements"])
# app.include_router(audits_router, prefix="/audits", tags=["audits"])
