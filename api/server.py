"""
Placement Week Scheduler - REST API & Dashboard Server
Serves coordinator dashboard UI and real-time replanning backend endpoints.
"""
import json
import os
import tempfile
import threading
from enum import Enum
from dataclasses import asdict
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.models import DisruptionEvent, DisruptionType, PriorityTier, InterviewStatus
from engine.scheduler import run_scheduler_from_dataset
from engine.replanner import IncrementalReplanner


API_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(API_DIR)
DATASET_PATH = os.path.join(PROJECT_ROOT, "data", "dataset.json")
SCHEDULE_PATH = os.path.join(PROJECT_ROOT, "data", "schedule.json")

# Mutex to prevent concurrent read/write races on schedule.json
_schedule_lock = threading.Lock()

app = FastAPI(title="Placement Week Scheduler API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EnumSafeEncoder(json.JSONEncoder):
    """Handles all Enum subclasses in dataclass-derived dicts."""
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


class DisruptionPayload(BaseModel):
    id: Optional[str] = "EVENT_USER"
    type: str
    target_id: str
    delay_hours: Optional[int] = 2


class CompoundDisruptionPayload(BaseModel):
    events: List[DisruptionPayload]


def _write_json_atomic(path: str, data: Any):
    """Write JSON to a temp file then atomically rename to prevent corruption."""
    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, cls=EnumSafeEncoder)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _read_schedule_safe() -> Dict[str, Any]:
    """Read schedule.json; if corrupted, regenerate from scratch."""
    try:
        with open(SCHEDULE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        run_scheduler_from_dataset(DATASET_PATH, SCHEDULE_PATH)
        with open(SCHEDULE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)


def ensure_data_exists():
    if not os.path.exists(DATASET_PATH):
        from generator.generate_dataset import generate
        generate(seed=42, output_dir="data")
    if not os.path.exists(SCHEDULE_PATH):
        run_scheduler_from_dataset(DATASET_PATH, SCHEDULE_PATH)


@app.on_event("startup")
def startup_event():
    ensure_data_exists()


def serialize_interview(intv) -> Dict[str, Any]:
    """Convert Interview dataclass to a JSON-safe dict, handling enums."""
    d = asdict(intv)
    status = d.get("status")
    if isinstance(status, Enum):
        d["status"] = status.value
    return d


@app.get("/api/schedule")
def get_schedule():
    ensure_data_exists()
    with _schedule_lock:
        data = _read_schedule_safe()
    return JSONResponse(content=data)


@app.get("/api/dataset")
def get_dataset():
    ensure_data_exists()
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(content=data)


@app.post("/api/replan")
def replan(payload: CompoundDisruptionPayload):
    ensure_data_exists()

    with _schedule_lock:
        current_schedule_data = _read_schedule_safe()
        replanner = IncrementalReplanner(DATASET_PATH, current_schedule_data)

        disruption_events = []
        for idx, item in enumerate(payload.events):
            dtype = DisruptionType[item.type]
            p_dict = {}
            if dtype == DisruptionType.COMPANY_DELAY:
                p_dict = {"company_id": item.target_id, "delay_hours": item.delay_hours or 2}
            elif dtype == DisruptionType.PANEL_DROPOUT:
                parts = item.target_id.split("_")
                comp_id = "_".join(parts[1:-1]) if len(parts) >= 3 else item.target_id
                p_dict = {"panel_id": item.target_id, "company_id": comp_id}
            elif dtype == DisruptionType.STUDENT_WITHDRAWAL:
                p_dict = {"student_id": item.target_id}
            elif dtype == DisruptionType.ROOM_UNAVAILABLE:
                p_dict = {"room_id": item.target_id}

            disruption_events.append(DisruptionEvent(
                id=item.id or f"EVENT_{idx+1}",
                type=dtype,
                timestamp="10:00",
                payload=p_dict
            ))

        diff = replanner.apply_disruptions(disruption_events)

        total_requested = current_schedule_data.get("metrics", {}).get("total_interviews_requested", 2207)
        updated_schedule_dict = {
            "id": "SCHED_REPLANNED",
            "metrics": {
                "total_interviews_requested": total_requested,
                "scheduled_count": len(replanner.scheduled_interviews),
                "unscheduled_count": len(replanner.unscheduled_interviews),
                "placement_rate_pct": round(len(replanner.scheduled_interviews) / max(total_requested, 1) * 100, 2),
                "replan_churn_pct": diff["churn_metrics"]["replan_churn_pct"],
                "replan_churn_count": diff["churn_metrics"]["total_churn_count"],
                "room_utilization_pct": round(len(replanner.room_occupied) / max(len(replanner.rooms) * 54, 1) * 100, 2)
            },
            "scheduled_interviews": [serialize_interview(i) for i in replanner.scheduled_interviews.values()],
            "unscheduled_interviews": [serialize_interview(i) for i in replanner.unscheduled_interviews.values()]
        }

        _write_json_atomic(SCHEDULE_PATH, updated_schedule_dict)

    return JSONResponse(content={
        "diff": diff,
        "schedule": updated_schedule_dict
    })


@app.post("/api/reset")
def reset_schedule():
    ensure_data_exists()
    with _schedule_lock:
        run_scheduler_from_dataset(DATASET_PATH, SCHEDULE_PATH)
        data = _read_schedule_safe()
    return JSONResponse(content={"message": "Schedule reset to baseline state", "schedule": data})


# Mount React Dashboard frontend
DASHBOARD_DIR = os.path.join(PROJECT_ROOT, "dashboard")
if os.path.exists(DASHBOARD_DIR):
    app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index_page():
    index_file = os.path.join(DASHBOARD_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Placement Week Scheduler API</h1><p>Dashboard UI loading...</p>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="127.0.0.1", port=8000, reload=True)
