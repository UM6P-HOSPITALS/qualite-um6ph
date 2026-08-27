# QUALITE-UM6PH — Plateforme Qualité UM6P Hospitals

Plateforme de management de la qualité pour UM6P Hospitals : gestion documentaire, gestion des événements indésirables, audits & inspections.

**Architecture** : monolithe (backend FastAPI unique, base PostgreSQL unique, frontend Next.js unique), authentification via comptes Microsoft (Entra ID).

## Structure

```
qualite-um6ph/
├── backend/          → API FastAPI
│   └── app/
│       ├── core/         → config, moteur statut/historique/notifications (à venir)
│       ├── documentaire/
│       ├── evenements/
│       └── audits/
├── web/              → application Next.js
├── docker-compose.yml
└── .env.example
```

## Lancer le projet en local

### 1. Cloner et configurer

```bash
git clone <url-du-repo> qualite-um6ph
cd qualite-um6ph
cp .env.example .env
```

### 2. Lancer PostgreSQL et Redis

```bash
docker compose up -d
```

### 3. Lancer le backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # sous Windows : .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Vérifier : http://localhost:8000/health doit répondre `{"status": "ok"}`.

### 4. Lancer le frontend

```bash
cd web
npm install
npm run dev
```

Vérifier : http://localhost:3000 doit afficher la page d'accueil QUALITE-UM6PH.

## Avancement

Suivi via les tickets GitHub au format `[FEATURE-XX-##]`. Prochaine étape : `FEATURE-SETUP-02` (schéma de base de données transverse).
