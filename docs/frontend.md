# DataWhisk Frontend

This document covers the frontend React application that lives in `ui/`. Read it when onboarding to the UI, adding a new tab/feature, or debugging data-fetching behavior.

---

## What it does

DataWhisk's UI is a single-page application with three tabs:

| Tab | Purpose |
|---|---|
| **Occupancy** | Select a building space, pick a date range, and view historical + forecasted occupancy counts alongside popular-times heatmaps. |
| **Thermal** | Select a VAV zone, configure thermal parameters, and view energy predictions across three models (em, etotal, ec). |
| **Optimizer** | Select a VAV zone, configure optimization parameters, and view an HVAC schedule optimized for cost savings vs. a naive baseline. |

---

## Tech stack

| Concern | Library | Version |
|---|---|---|
| UI framework | React | 18.3.1 |
| Language | TypeScript | 5.6.3 |
| Build tool | Vite | 5.4.10 |
| Styling | Tailwind CSS | 3.4.14 |
| Data fetching / caching | TanStack React Query | 5.59.0 |
| Charts | Recharts | 2.13.0 |
| Date utilities | date-fns | 4.1.0 |

---

## Folder structure

```
ui/
├── index.html                  # Root HTML; mounts React to #root
├── vite.config.ts              # Dev proxy (/api → localhost:8000) + build config
├── tailwind.config.ts          # Tailwind content paths
├── package.json
└── src/
    ├── main.tsx                # Entry point — initializes QueryClient, renders App
    ├── App.tsx                 # Tab routing + global state
    ├── index.css               # Tailwind base imports
    ├── api/                    # API client functions (one file per domain)
    │   ├── models.ts           # Model version management
    │   ├── occupancy.ts        # Occupancy & popular-times endpoints
    │   ├── optimizer.ts        # Thermal optimizer endpoints
    │   ├── spaces.ts           # Space hierarchy & name lookups
    │   └── thermal.ts          # Thermal energy prediction endpoints
    ├── hooks/                  # Custom React Query hooks
    │   ├── useModels.ts
    │   ├── useOccupancy.ts
    │   ├── useOptimizer.ts
    │   └── useThermal.ts
    ├── types/
    │   └── api.ts              # TypeScript interfaces for all API response shapes
    └── components/             # React components (see breakdown below)
```

---

## Components

### Shared

| Component | What it renders |
|---|---|
| `FieldLabel.tsx` | A labeled form field wrapper with an optional hover tooltip explaining the parameter. Used throughout all three tabs. |
| `ErrorModal.tsx` | Full-screen modal shown when occupancy forecast data is missing. Exposes a data ingestion trigger and polls ingestion status. |

### Occupancy tab

| Component | What it renders |
|---|---|
| `SpaceTree.tsx` | Hierarchical space browser. Children load lazily on expand. Includes a search filter that highlights matching nodes. |
| `OccupancyForm.tsx` | Start/end datetime pickers. Submits by calling the parent callback, which sets the global query params. |
| `OccupancyChart.tsx` | Recharts line chart. Two series: historical occupancy (solid) and ML forecast (dashed). |
| `PopularTimesChart.tsx` | Bar chart aggregated by day of week and hour, showing average historical occupancy — a "heat map" rendered as grouped bars. |
| `MetadataStrip.tsx` | Displays space metadata: space ID, active model version, last observed timestamp, and point counts. |
| `ModelVersionSelector.tsx` | Slide-in sidebar panel listing model versions for the selected space. Allows activating a version as production. |
| `FetchDataForm.tsx` | Sidebar form to export raw occupancy data for the selected space/date range to CSV. |

### Thermal tab

| Component | What it renders |
|---|---|
| `VavList.tsx` | Scrollable list of VAV zones with a search filter. Shared between Thermal and Optimizer tabs. |
| `ThermalForm.tsx` | Multi-field form: granularity, zone temp, ambient temp, setpoints, time window. |
| `ThermalChart.tsx` | Triple-line Recharts chart, one series per energy model: em (Energy to Maintain), etotal (Total Energy), ec (Cooling Energy). |

### Optimizer tab

| Component | What it renders |
|---|---|
| `OptimizerForm.tsx` | Parameters: granularity, initial temp, cooling setpoint, ambient temp, date range. |
| `OptimizerChart.tsx` | Multi-panel visualization (details below). |

`OptimizerChart.tsx` is the most complex component. Its panels (all synced on the x-axis):

1. **Summary cards** — optimized cost, naive baseline cost, savings %, and solver status.
2. **Cost bar chart** — optimized vs. naive cost per day (multi-day view only).
3. **Temperature line chart** — predicted zone temperature with reference lines for cooling and comfort bounds.
4. **HVAC state bar chart** — discrete states per interval: cooling / maintaining / off.
5. **TOU price area chart** — time-of-use electricity price over the optimization window.

Background shading highlights occupied hours and peak pricing windows across all panels.

---

## API integration

### Base URL

The base URL is set via the Vite env variable `VITE_API_BASE_URL`, defaulting to `/api`. During development, Vite proxies `/api` to `http://localhost:8000`, so no CORS configuration is needed.

### Endpoints called

| Domain | Endpoint | Purpose |
|---|---|---|
| Spaces | `GET /services/spaces/space-names` | ID → human name mapping |
| Spaces | `GET /services/spaces/{id}/children` | Lazy-load child spaces in the tree |
| Occupancy | `GET /services/occupancy/spaces` | List all space IDs |
| Occupancy | `GET /services/occupancy/{id}` | Historical + forecast occupancy |
| Occupancy | `GET /services/occupancy/{id}/popular-times` | Aggregated hourly averages by day |
| Occupancy | `GET /services/occupancy/{id}/has-data` | Check data availability |
| Thermal | `GET /services/thermal/zones` | Available VAV zones |
| Thermal | `GET /services/thermal/{zoneId}/predict/range` | Energy predictions (em, etotal, ec) |
| Optimizer | `GET /services/thermal/{zoneId}/optimize/range` | Cost-optimized HVAC schedule |
| Data export | `POST /export/occupancy/{id}` | Export raw data to CSV |
| Ingestion | `POST /ingest/occupancy/{id}` | Trigger data ingestion job |
| Ingestion | `GET /ingest/occupancy/{id}/status` | Poll ingestion job status |
| Admin | `GET /admin/models/{id}/versions` | List model versions for a space |
| Admin | `POST /admin/models/{id}/set-production` | Activate a model version |

### Error handling

A custom `ApiError` class (extends `Error`) carries the HTTP status code. API functions catch non-2xx responses, attempt to parse the JSON error body, and throw an `ApiError`. React Query surfaces these as `error` objects on the query; components render them inline or inside `ErrorModal`.

### Cache / stale-time strategy

| Data | Stale time |
|---|---|
| Space names, zone names | 5–10 minutes |
| Occupancy data | 1 minute |
| Thermal predictions, optimizer results | 1 minute |
| Model versions | 30 seconds |
| Popular-times aggregates | 30 minutes |

---

## State management

There is no global state library. `App.tsx` owns the state that must be shared across tabs:

| State | Type | Purpose |
|---|---|---|
| `tab` | `"occupancy" \| "thermal" \| "optimizer"` | Active tab |
| `spaceId` | `string \| null` | Selected space (occupancy tab) |
| `zoneId` | `string \| null` | Selected VAV zone (thermal / optimizer tabs) |
| `params` | occupancy query params | Submitted form state for the occupancy query |
| `thermalParams` | thermal query params | Submitted form state for the thermal query |
| `optimizerParams` | optimizer query params | Submitted form state for the optimizer query |

Each form component holds its own local `useState` values while the user edits. On submit, it calls a parent callback that copies the values into `App`'s state. That state is passed as arguments to the React Query hooks, which only fire a request when all required params are non-null.

---

## Data-fetching hooks

Each domain has a dedicated custom hook in `src/hooks/`:

```
useOccupancy(spaceId, params)       → { data, isLoading, error }
useAllThermalRanges(zoneId, params) → { em, etotal, ec, isLoading, error }
useOptimizer(zoneId, params)        → { data, isLoading, error }
useModels(spaceId)                  → { versions, setProduction, ... }
```

Hooks return `undefined` data until all required arguments are provided, preventing spurious requests when the user hasn't selected a space/zone yet.

---

## Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Tab bar: [Occupancy] [Thermal] [Optimizer]                     │
├──────────────────────┬──────────────────────────────────────────┤
│  Sidebar (18 rem)    │  Main content area                       │
│                      │                                          │
│  Occupancy tab:      │  Form → Load → Charts                    │
│    SpaceTree         │                                          │
│    + optional        │  Thermal tab:                            │
│      FetchDataForm   │    ThermalForm → Load → ThermalChart     │
│      ModelVersion    │                                          │
│      Selector        │  Optimizer tab:                          │
│                      │    OptimizerForm → Optimize →            │
│  Thermal/Optimizer:  │    OptimizerChart (multi-panel)          │
│    VavList           │                                          │
└──────────────────────┴──────────────────────────────────────────┘
```

The sidebar is conditional: occupancy uses `SpaceTree`; thermal and optimizer share `VavList`. Both sidebars have a search input for filtering.

---

## Running locally

```bash
cd ui
npm install
npm run dev     # starts Vite dev server at http://localhost:5173
```

The dev server proxies `/api/*` to `http://localhost:8000`, so the FastAPI backend must be running for data to load. See the root `README.md` for how to start the full stack.

---

## Adding a new tab

1. Add a value to the `tab` union type in `App.tsx`.
2. Add a button to the tab bar in `App.tsx`.
3. Create a folder under `src/components/` for the new tab's components.
4. If the tab needs new API calls, add a file under `src/api/` and a hook under `src/hooks/`.
5. Add any new API response shapes to `src/types/api.ts`.
6. Wire up the new tab's root component in the main content area of `App.tsx`.

---

## Cross-references

- **Backend API reference**: [`api-reference.md`](api-reference.md)
- **Backend architecture**: [`architecture.md`](architecture.md)
- **Adding a new endpoint**: [`adding-an-endpoint.md`](adding-an-endpoint.md)
