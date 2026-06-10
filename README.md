# DataWhisk

**Occupancy forecasting and thermal energy modeling for university building spaces.**

DataWhisk ingests historical sensor data from a PostgreSQL database, trains per-space machine learning models via Dagster, and shows predictions through a FastAPI backend. This is then displayed by a React dashboard. Building operators and researchers can use it to forecast how many people will be in a room at a given time and to model the energy cost of reaching a heating or cooling setpoint.

> **Deployment status:** Local / on-premises only. There is no publicly hosted version.

---

## Team Members and Roles

| Name | Role |
| :--- | :--- |
| **Gabriel Gomes** | Occupancy model science — per-space time-series models, occupancy data injestion and pipelines, Dagster assets, MLflow registry, React UI |
| **Atharva** | Thermal model science — physics-informed $E_c$ (cooling) and $E_h$ (heating) regression models |
| **Vivek** | Systems architecture — FastAPI gateway, Dagster orchestration, Docker Compose infrastructure, Dagster assets, MLflow registry, React UI, Thermal model science — physics-informed $E_c$ (cooling) and $E_h$ (heating) regression models |

---

## Features Implemented

- **Occupancy tab** — select a building space from a searchable tree, choose a date range, and view a chart of historical occupancy alongside a model forecast for future intervals. Displays model version, MAPE, and training metadata.
- **Popular times chart** — aggregated hour-of-week map for a selected space.
- **Thermal tab** — input zone ID, temperatures, setpoints, and time range to retrieve mechanical energy estimates ($E_m$, $E_{total}$, $E_c$) across intervals.
- **Optimizer tab** — find the optimal cooling setpoint for a given zone over a date range to minimise energy cost.
- **Model management sidebar** — view available MLflow model versions for a space and promote one to `@production`.
- **Export data** — trigger on-demand data ingestion for a space ID into the occupancy table.
- **Error reporting** — modal alerts when no production model exists for a space or when forecast generation fails.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Browser  (React + Vite, port 5173)             │
│  • OccupancyChart  • ThermalChart               │
│  • OptimizerChart  • SpaceTree sidebar          │
└─────────────────┬───────────────────────────────┘
                  │ HTTP / JSON
┌─────────────────▼───────────────────────────────┐
│  FastAPI  (port 8000)                           │
│  routes: occupancy · thermal · optimizer        │
│           spaces · train · export · mapping     │
└──────┬─────────────────────┬────────────────────┘
       │                     │
┌──────▼──────┐    ┌─────────▼──────────┐
│  PostgreSQL  │    │  Dagster           │
│  (port 5432) │    │  webserver :3000   │
│  occupancy   │    │  daemon            │
│  occuspace   │    │  GraphQL client    │
└──────────────┘    └─────────┬──────────┘
                              │ trains & materialises
                    ┌─────────▼──────────┐
                    │  MLflow  (port 5001)│
                    │  experiment tracker │
                    │  model registry    │
                    └────────────────────┘
```

**Request flow for occupancy forecast:**
1. UI calls `GET /occupancy/{space_id}?start=…&end=…`
2. FastAPI queries PostgreSQL for historical readings, computes future intervals
3. FastAPI loads the `@production` MLflow model for that space via `ModelResolver`
4. Predictions are returned alongside historical data and model metadata

**Training flow:**
1. UI (or operator) calls `POST /train/{space_id}`
2. FastAPI fires a GraphQL mutation to the Dagster daemon
3. Dagster runs the training job, logs metrics to MLflow, and registers a new model version
4. Operator promotes the version to `@production` in the MLflow UI or via the Model sidebar

---

## Tech Stack

| Layer | Technology |
| :--- | :--- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts |
| Backend | Python 3.11, FastAPI, SQLAlchemy, psycopg2 |
| ML / orchestration | Dagster, MLflow (experiment tracking + model registry) |
| Database | PostgreSQL 15 |
| Containerisation | Docker, Docker Compose |

---

## Setup Instructions

### Prerequisites

- Python **3.11+**
- Docker + Docker Compose
- Node.js **18+** and npm (for the UI)
- `git`

### 1. Clone and configure environment variables

```bash
git clone <repo-url> tippers-services
cd tippers-services
cp .env.example .env
```

Edit `.env` and set the credentials for your sensor database:

```
DATABASE_URL=postgresql://user:pass@postgres:5432/datawhisk
```

See [Environment Variables](#environment-variables) below for all options.

### 2. Create a Python virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows PowerShell

pip install --upgrade pip
pip install -r api/requirements.txt
pip install -r orchestration/requirements.txt
pip install -e .                    # dev/test tooling from pyproject.toml
```

### 3. Start the backend stack (Docker Compose)
Run this in the root directory:
```bash
docker compose up -d --build
```

This starts: PostgreSQL, MLflow, FastAPI, Dagster webserver, Dagster daemon.

```bash
docker compose logs -f             # all services
docker compose logs -f api         # single service
```

| Service | URL | Notes |
| :--- | :--- | :--- |
| FastAPI | http://localhost:8000/docs | Swagger UI |
| Dagster | http://localhost:3000 | Jobs, assets, run history |
| MLflow | http://localhost:5001 | Model registry |
| PostgreSQL | localhost:5432 | Credentials from `.env` |

To stop:
```bash
docker compose down          # stop, keep data volumes
docker compose down -v       # stop and wipe all volumes
```

### 4. Start the frontend

```bash
cd ui
npm install
npm run dev
```

UI is available at **http://localhost:5173**.

---

## How to Run Locally

Once the backend is up and the UI dev server is running:

1. Open http://localhost:5173 in a browser.
2. Use the **Space** tree in the left sidebar to find and select a building space.
3. **Occupancy tab** — pick a date range and click **Load** to see historical data and a forecast.
4. **Thermal tab** — enter zone parameters and click **Load** to retrieve energy estimates.
5. **Optimizer tab** — enter zone parameters and click **Optimize** to find the best setpoint.

To train a model for a new space, call the API directly or use the Dagster UI:
```bash
curl -X POST http://localhost:8000/train/473
```
After training completes, open the **Model** button in the Occupancy form, select the new version, and promote it to `@production`.

To run the API on the host (outside Docker) while keeping Postgres/MLflow containerised:
```bash
# Change DATABASE_URL in .env: postgres → localhost
uvicorn api.main:app --reload --port 8000
```

---

## Environment Variables

All variables live in `.env` (copy from `.env.example`):

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://user:pass@postgres:5432/datawhisk` | Sensor data Postgres. Use `localhost` instead of `postgres` when running the API outside Docker. |
| `MLFLOW_TRACKING_URI` | `http://mlflow:5000` | MLflow server. Internal Docker DNS — do not change unless you rename the service. |
| `DAGSTER_HOME` | `/opt/dagster/dagster_home` | Dagster metadata directory (inside container). |
| `DAGSTER_WEBSERVER_HOST` | `dagster_webserver` | Dagster GraphQL target. Use `localhost` when running the API on the host. |
| `DAGSTER_WEBSERVER_PORT` | `3000` | |
| `POSTGRES_USER` | `dw` | Local Postgres user (Dagster + MLflow metadata). |
| `POSTGRES_PASSWORD` | `dw` | Local Postgres password. |

---

## Testing and Verification

Run the test suite with the virtual environment activated:

```bash
pytest
```

`pyproject.toml` sets `pythonpath = ["shared", "api", "orchestration"]` so all service imports resolve without extra configuration.

To manually verify the occupancy endpoint:
```bash
curl "http://localhost:8000/occupancy/473?start=2024-04-01T00:00:00&end=2024-09-30T00:00:00"
```

A successful response includes `historical`, `forecast`, `model_version`, and `mape` fields. If no `@production` model exists for the space, the response includes a `forecast_error` message (which the UI also surfaces as a modal).

---

## Known Issues and Future Work

**Known limitations:**
- No deployed / hosted version — the system must be run locally against an institutional Postgres instance that holds the sensor data.
- Thermal and optimizer models currently require the user to know the zone ID string (e.g. `VAV-101`) — there is no lookup or autocomplete for zone IDs in the UI.
- Model training is triggered manually; there is no scheduled retraining pipeline yet.
- The `@production` alias must be set manually in MLflow or via the Model sidebar after each training run.
- No hosted MLFlow server yet. However that will be worked on in subsequent iterations.

**Potential future work:**
- Scheduled Dagster jobs for automatic nightly model retraining.
- Zone ID autocomplete sourced from the database.
- Multi-space aggregate forecasting (floor-level or building-level rollup).
- Authentication layer for the API and UI.
- Hosted deployment (UCI server or cloud).
- Alert system to flag spaces where occupancy significantly deviates from forecast.

---

## Demo

Demo video: _coming soon_
