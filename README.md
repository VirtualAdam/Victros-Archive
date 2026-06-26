# Victros

**Strategic Reasoning Schema (SRS) — B2B Sales Strategy System**

Victros is a deterministic diagnosis engine for B2B sales deals with an LLM coaching interface. The LLM is the voice; the schema is the brain. Strategy selection is fully deterministic and auditable regardless of LLM model.

---

## Quick Start

```bash
# Clone
git clone https://github.com/VirtualAdam/Victros-Archive.git
cd Victros-Archive

# Local dev (Docker — full stack with Cosmos emulator)
cp .env.example .env   # fill in AI credentials
docker compose up --build

# Or backend only (file-based storage, no Docker)
cd victros-poc
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
STORAGE_BACKEND=file uvicorn server.main:create_app --factory --reload --port 8000
```

Frontend: http://localhost:5173 | Backend: http://localhost:8000

---

## Architecture

```
User Input
  → Azure Static Web Apps (React SPA, Entra External ID auth)
    → Azure Container Apps (FastAPI backend)
      ├── Decision Engine (deterministic: signals → patterns → strategy → actions)
      ├── Azure Cosmos DB (sessions, snapshots)
      └── Azure OpenAI GPT-4o (intent routing, extraction, explanation)
```

The Decision Engine is pure Python — no LLM. Only three services call GPT-4o (Intent Router, Extraction, Explanation), and none can alter strategic decisions.

Full architecture docs: [`_documentation/ARCHITECTURE.md`](_documentation/ARCHITECTURE.md)

---

## Project Structure

```
victros-poc/
├── backend/           Python/FastAPI backend
│   ├── server/        Application code
│   │   ├── decision/  Deterministic engine (patterns, signals, strategies)
│   │   ├── llm/       LLM service wrappers (intent, extraction, explanation)
│   │   ├── db/        Cosmos DB persistence
│   │   └── auth.py    Entra authentication
│   ├── schema/        Signal & pattern definitions (JSON)
│   └── tests/         Unit + integration tests
├── frontend/          React/TypeScript SPA
infra/                 Azure Bicep IaC (all resources)
_documentation/        Architecture & design docs
Product specs/         Product specifications
full schemas/          CSV exports of schema data
.github/workflows/     CI/CD pipelines
```

---

## Deploy to Azure

**Automated (recommended):** Use the Claude deployment skill — upload `.claude/skills/deploy.md` to Claude with the message "Use this skill to deploy Victros." It handles tool installation, infrastructure provisioning, and deployment interactively.

**Manual:** See [`deployment-guide.md`](deployment-guide.md) for the full step-by-step.

**Quick manual deploy** (after infra is provisioned):
```bash
./deploy.sh backend    # Build + push image + update Container App
git push origin main   # Frontend deploys via GitHub Actions
```

---

## Testing

```bash
cd victros-poc

# Backend unit tests (decision engine — no LLM needed)
pytest backend/tests -m "not llm and not integration" -q

# Frontend tests
cd frontend && npm test
```

---

## Key Documentation

| Document | Purpose |
|----------|---------|
| [`_documentation/ARCHITECTURE.md`](_documentation/ARCHITECTURE.md) | System architecture, data flow, component contracts |
| [`deployment-guide.md`](deployment-guide.md) | Full Azure deployment walkthrough |
| [`victros-poc-spec.md`](victros-poc-spec.md) | Engineering specification |
| [`infra/DEPLOYMENT.md`](infra/DEPLOYMENT.md) | Infrastructure deployment notes |
| [`.github/CI_SETUP.md`](.github/CI_SETUP.md) | CI/CD configuration reference |
| [`infra/entra/README.md`](infra/entra/README.md) | Entra External ID setup |

---

## License

Proprietary — Wiedemann Labs. All rights reserved.
