from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.deps import _sessionmaker
from api.routes import mapping, models, occupancy, train

app = FastAPI(title="DataWhisk API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(occupancy.router)
app.include_router(models.router)
app.include_router(train.router)
app.include_router(mapping.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready", tags=["meta"])
def ready() -> dict:
    try:
        with _sessionmaker()() as session:
            session.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"db unreachable: {e}") from e
    return {"status": "ready"}
