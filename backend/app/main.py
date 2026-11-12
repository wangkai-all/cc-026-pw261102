"""FastAPI application: experiment metadata + pointwise analysis."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analysis import analyze_experiment
from .data import (
    DATA_DIR,
    DatasetError,
    experiment_summaries,
    get_scenario,
)

app = FastAPI(
    title="实验分析 API",
    description="先检查分流，再分析转化与每用户收入。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "dataDir": str(DATA_DIR)}


@app.get("/api/experiments")
def experiments() -> dict[str, object]:
    try:
        items = experiment_summaries()
    except DatasetError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"experiments": items}


@app.get("/api/analysis")
def analysis(
    experiment_id: str = Query(..., description="实验 ID"),
    start: date | None = Query(None, description="首次曝光起始日期（含）"),
    end: date | None = Query(None, description="首次曝光结束日期（含）"),
    expected_control_pct: float | None = Query(None, description="预期对照组比例，%"),
    expected_treatment_pct: float | None = Query(None, description="预期实验组比例，%"),
) -> dict[str, object]:
    try:
        scenario = get_scenario(experiment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"找不到实验: {experiment_id}") from exc
    except DatasetError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    summary = next(
        item
        for item in experiment_summaries()
        if item["experimentId"] == experiment_id
    )

    default_control = float(scenario.meta.get("expected_control_pct", 50))
    default_treatment = float(scenario.meta.get("expected_treatment_pct", 100 - default_control))
    control_pct = default_control if expected_control_pct is None else expected_control_pct
    if expected_treatment_pct is None:
        treatment_pct = 100.0 - control_pct
    else:
        treatment_pct = expected_treatment_pct

    if not (0 < control_pct < 100):
        raise HTTPException(status_code=400, detail="预期对照组比例必须在 0 到 100 之间。")
    if not (0 < treatment_pct < 100):
        raise HTTPException(status_code=400, detail="预期实验组比例必须在 0 到 100 之间。")
    if abs(control_pct + treatment_pct - 100.0) > 1e-6:
        raise HTTPException(status_code=400, detail="预期分流比例之和必须为 100%。")

    default_start = date.fromisoformat(summary["firstExposureMinDate"])
    default_end = date.fromisoformat(summary["firstExposureMaxDate"])
    start_date = default_start if start is None else start
    end_date = default_end if end is None else end
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="起始日期不能晚于结束日期。")

    try:
        return analyze_experiment(
            scenario,
            start_date,
            end_date,
            control_pct,
            treatment_pct,
        )
    except DatasetError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")
