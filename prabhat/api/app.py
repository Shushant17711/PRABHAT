"""S7: the REST API behind the dashboard.

    uvicorn prabhat.api.app:app --reload      # http://127.0.0.1:8000/docs

Every case is computed on first request and cached for the life of the
process. If ``dashboard/dist`` has been built, it is served at ``/``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..alerts import USER_CLASSES, USER_CLASSES_BY_NAME
from ..cap import to_cap
from ..ledger import Ledger, seed_hindcasts, summary
from ..pipeline import CaseResult, case_ids, case_spec, run_case

DIST = Path(__file__).resolve().parents[2] / "dashboard" / "dist"
ledger = Ledger()


def _result(case_id: str) -> CaseResult:
    if case_id not in case_ids():
        raise HTTPException(404, f"unknown case {case_id!r}")
    res = run_case(case_id)
    for a in res.alerts:
        ledger.record_alert(a)
    return res


def _by_tube(tube_id: str) -> CaseResult:
    for cid in case_ids():
        if tube_id.startswith(cid + "-"):
            res = _result(cid)
            if any(t.tube_id == tube_id for t in res.tubes):
                return res
    raise HTTPException(404, f"unknown tube {tube_id!r}")


def _warm() -> None:
    with ThreadPoolExecutor() as pool:
        list(pool.map(_result, case_ids()))


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not any(e.get("kind") == "hindcast" for e in ledger.entries()):
        seed_hindcasts(ledger)
    yield


app = FastAPI(
    title="PRABHAT",
    version=__version__,
    description="Tracked-object extreme-weather anomaly detection with runtime "
                "hallucination gates. All forecast data is synthetic; see /v1/status.",
    lifespan=lifespan,
)


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/v1/cases")
def cases() -> list[dict]:
    out = []
    for cid in case_ids():
        spec = case_spec(cid)
        out.append({
            "id": cid,
            "hazard": spec.hazard,
            "title": spec.title + (" (interpolation control)" if cid != spec.id else ""),
            "init_time": spec.init_time,
            "variable": spec.variable,
            "units": spec.units,
            "threshold": spec.threshold,
            "domain_bbox": list(spec.domain_bbox),
        })
    return out


@app.get("/v1/user-classes")
def user_classes() -> list[dict]:
    return [u.to_dict() for u in USER_CLASSES]


@app.get("/v1/status")
def status() -> list[dict]:
    _warm()
    return [_result(cid).status for cid in case_ids()]


@app.get("/v1/tubes")
def tubes(case: str) -> list[dict]:
    return [t.to_dict() for t in _result(case).tubes]


@app.get("/v1/tubes/{tube_id}/gate")
def gate(tube_id: str) -> dict:
    return _by_tube(tube_id).gate


@app.get("/v1/tubes/{tube_id}/analogues")
def analogues(tube_id: str) -> list[dict]:
    return _by_tube(tube_id).analogues


@app.get("/v1/tubes/{tube_id}/exceedance")
def exceedance(tube_id: str) -> dict:
    return _by_tube(tube_id).raster


@app.get("/v1/tubes/{tube_id}/efi")
def efi(tube_id: str) -> dict:
    return _by_tube(tube_id).efi


@app.get("/v1/alerts")
def alerts(case: str, user_class: str | None = Query(None)) -> list[dict]:
    if user_class is not None and user_class not in USER_CLASSES_BY_NAME:
        raise HTTPException(404, f"unknown user class {user_class!r}")
    return [a for a in _result(case).alerts
            if user_class is None or a["user_class"] == user_class]


@app.get("/v1/churn")
def churn(case: str) -> list[dict]:
    return _result(case).churn


@app.get("/v1/ledger/summary")
def ledger_summary() -> dict:
    return summary(ledger)


@app.get("/v1/cap/{alert_id}.xml")
def cap(alert_id: str) -> Response:
    for cid in case_ids():
        if alert_id.startswith(cid + "-"):
            for a in _result(cid).alerts:
                if a["alert_id"] == alert_id:
                    return Response(to_cap(a), media_type="application/xml")
    raise HTTPException(404, f"unknown alert {alert_id!r}")


if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(DIST / "index.html")
