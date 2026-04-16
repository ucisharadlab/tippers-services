# Requirements Specification: DataWhisk Services (v2.0)

## 1. Project Overview
DataWhisk is a multi-service platform designed to provide occupancy forecasting and thermal energy modeling for building spaces. The system utilizes a decoupled architecture where a FastAPI gateway interacts with a Dagster orchestration engine to handle long-running analytical tasks.

## 2. Team Roles & Responsibilities

### Task 1: Occupancy Prediction Models (Gabriel)
**Role:** Model Scientist (Occupancy)
* **Objective:** Develop time-series models for every `space_id` to predict human density.
* **Data Source:** Historical data from `public.occupancy` and `public.occuspace` (PostgreSQL).
* **Modeling Strategy:** * Individual per-space models for high granularity.
    * Bottom-up aggregation for floor-level occupancy insights.
* **Output:** Software-Defined Assets (SDA) in Dagster representing predicted occupancy sequences.

### Task 2: Thermal Transfer Models — $E_c$ & $E_h$ (Atharva)
**Role:** Model Scientist (Thermal)
* **Objective:** Build physics-informed regression models for $E_c$ (Cooling) and $E_h$ (Heating).
* **Data Source:** Thermal sensors mapped to `space_id` and ambient weather data.
* **Key Metrics:** * **Lead Time:** Minutes required to reach a target setpoint.
    * **Energy Cost:** Estimated kWh for the transition.
* **Output:** Software-Defined Assets (SDA) in Dagster linked to specific `space_id`s.

### Task 3: API Infrastructure & Orchestration (Vivek)
**Role:** Systems Architect
* **Objective:** Build the FastAPI gateway and the Dagster orchestration backend.
* **Integration:** * Implement `DagsterGraphQLClient` within FastAPI to trigger model training/inference jobs.
    * Manage the **Model-to-Space Mapping Table** in SQL.
* **Infrastructure:** Containerize the ecosystem using Docker (FastAPI, Dagster Webserver, Dagster Daemon, Redis, and PostgreSQL).

---

## 3. Technical Architecture

### Communication Flow
1.  **Request:** FastAPI receives a `POST` request to update a model for a specific `space_id`.
2.  **Trigger:** FastAPI sends a GraphQL mutation to the **Dagster Daemon**.
3.  **Execution:** Dagster executes the long-running SQL queries and Python model training as a "Run."
4.  **Tracking:** Dagster provides real-time logs and status via its UI.
5.  **Materialization:** Once complete, Dagster updates the "Asset" status and records metadata (e.g., model accuracy).

### The Mapping Table Schema
A dedicated table managed by Vivek to track the state of all models:
| Column | Type | Description |
| :--- | :--- | :--- |
| `space_id` | String | Unique identifier for the room/space. |
| `occupancy_model_uri` | String | MLflow URI or Dagster Asset Key for Gabriel's model. |
| `thermal_model_uri` | String | MLflow URI or Dagster Asset Key for Atharva's model. |
| `last_trained` | Timestamp | The last time the Dagster job completed successfully. |
| `last_run_id` | String | The Dagster Run ID for traceability. |

---

## 4. Accelerated 3-Week Timeline

| Week | Gabriel (Occupancy) | Atharva (Thermal) | Vivek (Infrastructure) |
| :--- | :--- | :--- | :--- |
| **Week 1** | Data profiling and cleaning of occupancy tables. | Isolate cooling/heating events from sensor data. | Dockerize Dagster + FastAPI; Setup GraphQL client logic. |
| **Week 2** | Define Occupancy Assets in Dagster; Train initial models. | Define Thermal Assets ($E_c$/$E_h$); Train regression models. | Build the Model Mapping Table; Create FastAPI trigger endpoints. |
| **Week 3** | Validate predictions; Fine-tune ensemble logic. | Finalize energy/time calculation logic. | End-to-end integration: API $ightarrow$ Dagster $ightarrow$ Asset update. |

---

## 5. Definition of Done
* **Functional API:** `POST /train/{space_id}` triggers a Dagster run; `GET /occupancy/{space_id}` returns data from the materialized asset.
* **Observability:** All long-running SQL queries are tracked in the Dagster UI with logs and success/fail states.
* **Decoupling:** The FastAPI process remains responsive and does not time out during 2-hour model runs.
* **Persistence:** Model metadata and lineage are stored in the Mapping Table and Dagster's internal DB.
