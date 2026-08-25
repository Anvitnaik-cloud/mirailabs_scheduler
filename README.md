# Placement Week Scheduler

A constraint-based scheduling and real-time replanning system for high-concurrency campus placement drives. Built for the **Mirai Labs Software Developer Intern** take-home assignment.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Approach & Algorithm Design](#approach--algorithm-design)
- [Architecture Overview](#architecture-overview)
- [Directory Structure](#directory-structure)
- [Setup & Installation](#setup--installation)
- [Usage Guide](#usage-guide)
- [API Reference](#api-reference)
- [Quality Metrics & Evaluation](#quality-metrics--evaluation)
- [Design Decisions & Tradeoffs](#design-decisions--tradeoffs)
- [Documentation Index](#documentation-index)

---

## Problem Statement

A university placement week spans **3 days** with **35 companies**, **800 students**, and **20 physical rooms**. Companies shortlist candidates and require dedicated interview panels, rooms, and time slots. The scheduler must:

1. **Generate a feasible initial schedule** — assign every shortlisted interview to a panel, room, and time slot without conflicts.
2. **Handle real-time disruptions** — company delays, panel dropouts, student withdrawals, and room outages — with **minimum churn** (< 5% schedule disturbance per event).
3. **Expose a REST API and coordinator dashboard** for live injection of disruptions and visual inspection of the schedule grid.

---

## Approach & Algorithm Design

### Core Algorithm: Priority-Ordered CSP (Constraint Satisfaction Problem)

The engine uses a **greedy CSP solver** augmented with **Most-Constrained-First (MCF)** heuristics rather than a black-box ILP/CP-SAT solver. This was a deliberate choice for three reasons:

1. **Explainability** — every scheduling decision can be traced step-by-step; when an interview cannot be placed, the exact binding constraint (`STUDENT_CLASH`, `PANEL_CONTENTION`, `ROOM_CONTENTION`, `CAPACITY_EXCEEDED`) is logged.
2. **Performance** — O(1) hash-set occupancy lookups schedule ~2,200 interviews in < 500ms on standard hardware.
3. **Incremental replanning** — the occupancy-set architecture enables localized micro-repairs without full schedule recalculation.

### How the Scheduler Works

```
┌─────────────────────────────────────────────────────────────┐
│  1. Build interview request list from student shortlists    │
│  2. Sort by: Tier (DREAM > NICHE > MID > MASS)             │
│            → Shortlist overlap count (most constrained)     │
│            → CGPA cutoff                                    │
│  3. For each request, try to assign (slot, panel, room):    │
│       • Check student availability in slot   ── O(1) set    │
│       • Check panel availability in slot     ── O(1) set    │
│       • Check room availability in slot      ── O(1) set    │
│       • On success: commit occupancy to all 3 sets          │
│       • On failure: record diagnostic reason                │
│  4. Emit Schedule with metrics + unscheduled diagnostics    │
└─────────────────────────────────────────────────────────────┘
```

### How the Replanner Works

When a disruption occurs (e.g., a company is delayed 2 hours), the replanner performs **incremental micro-repairs**:

```
┌──────────────────────────────────────────────────────────────┐
│  1. Identify invalidated interviews (scoped to disruption)   │
│  2. Release their occupancy slots                            │
│  3. Re-place invalidated interviews by priority (DREAM first)│
│  4. Backfill: attempt to schedule previously-unscheduled     │
│     interviews into newly freed slots                        │
│  5. Emit structured diff (moved, cancelled, newly_scheduled, │
│     who_to_notify) + churn metrics                           │
└──────────────────────────────────────────────────────────────┘
```

**Churn targets:**
| Disruption Type | Churn Target |
| :--- | :--- |
| Company Delay (2 hrs) | < 10% of that company's interviews |
| Panel Dropout | < 25% of that company's interviews |
| Room Unavailable | < 3% of total schedule |
| Student Withdrawal | 0% ripple churn (only cancels + backfills) |

### Time & Space Complexity

| Phase | Complexity |
| :--- | :--- |
| Sorting | O(N·log N) where N = interview requests (~2,200) |
| Slot assignment | O(N · S · P · R) worst-case, with S=slots, P=panels, R=rooms |
| Occupancy checks | O(1) per check via hash sets |
| Empirical runtime | ~250ms for 2,200 interviews on Python 3.10 |
| Memory | < 5 MB (occupancy sets across students × slots) |

---

## Architecture Overview

```
                    ┌───────────────────────┐
                    │   Coordinator UI      │
                    │  (dashboard/index.html)│
                    └───────────┬───────────┘
                                │ HTTP
                    ┌───────────▼───────────┐
                    │   FastAPI REST API     │
                    │   (api/server.py)      │
                    │                        │
                    │  GET /api/schedule     │
                    │  GET /api/dataset      │
                    │  POST /api/replan      │
                    │  POST /api/reset       │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                  │
   ┌──────────▼──────┐  ┌──────▼───────┐  ┌──────▼───────────┐
   │  Scheduler CSP  │  │  Replanner   │  │ Dataset Generator│
   │ (scheduler.py)  │  │(replanner.py)│  │(generate_dataset)│
   └────────┬────────┘  └──────┬───────┘  └──────────────────┘
            │                  │
   ┌────────▼──────────────────▼────────┐
   │       Domain Models (models.py)    │
   │  Company | Student | Panel | Room  │
   │  TimeSlot | Interview | Schedule  │
   │  DisruptionEvent                   │
   └────────────────────────────────────┘
            │
   ┌────────▼───────────────────────────┐
   │         data/ (JSON + CSV)         │
   │  dataset.json | schedule.json      │
   │  companies.csv | students.csv      │
   │  rooms.csv | shortlists.csv        │
   └────────────────────────────────────┘
```

**Key design principle:** The scheduling engine (`engine/`) is completely decoupled from storage, API, and UI. All domain entities are pure Python dataclasses with zero ORM dependencies.

---

## Directory Structure

```text
MiraiLabs/
├── README.md                      # This file
├── docs/                          # Architecture & decision documentation
│   ├── domain-model.md            # Core entity definitions & design tradeoffs
│   ├── dataset-assumptions.md     # Dataset generation distributions & parameters
│   ├── algorithm-notes.md         # CSP algorithm design & Big-O analysis
│   ├── metrics.md                 # Schedule quality metric specifications
│   └── decisions.md               # Constraint bending hierarchy & churn thresholds
├── engine/                        # Core scheduling & replanning engine (no I/O deps)
│   ├── __init__.py
│   ├── models.py                  # Pure Python dataclasses & enums
│   ├── scheduler.py               # Priority-ordered CSP scheduler
│   └── replanner.py               # Incremental minimum-churn replanning engine
├── generator/                     # Realistic dataset generator
│   ├── __init__.py
│   └── generate_dataset.py        # Power-law shortlisting & CSV/JSON export
├── api/                           # REST API server (FastAPI)
│   ├── __init__.py
│   └── server.py                  # Endpoints for schedule, replan, reset
├── dashboard/                     # Coordinator web dashboard
│   ├── README.md
│   └── index.html                 # Single-page schedule grid & disruption controls
├── data/                          # Generated data artifacts (gitignored or committed)
│   ├── dataset.json               # Full entity dataset (companies, students, rooms)
│   ├── schedule.json              # Current schedule state
│   ├── companies.csv              # Company profiles
│   ├── students.csv               # Student demographics
│   ├── rooms.csv                  # Room inventory
│   └── shortlists.csv             # Student ↔ Company junction table
└── tests/                         # Test suite
    └── __init__.py
```

---

## Setup & Installation

### Prerequisites

- **Python 3.10+** (3.11 / 3.12 also work)
- **pip** (Python package manager)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd MiraiLabs
```

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install fastapi uvicorn pydantic
```

> **Note:** The core scheduling engine (`engine/`) has **zero external dependencies** — it uses only Python's standard library (`dataclasses`, `json`, `csv`, `random`, `argparse`). FastAPI and Uvicorn are only required for the REST API server.

### 4. Generate the Dataset

```bash
python -m generator.generate_dataset --seed 42 --output-dir data
```

This creates:
- `data/dataset.json` — structured entity dump (companies, students, rooms, shortlists)
- `data/companies.csv`, `data/students.csv`, `data/rooms.csv`, `data/shortlists.csv`

### 5. Generate the Initial Schedule

```bash
python -m engine.scheduler --dataset data/dataset.json --output data/schedule.json
```

Output includes placement rate, room/panel utilization, wait times, and unscheduled diagnostics.

### 6. Run the API Server + Dashboard

```bash
python -m api.server
```

This starts the FastAPI server at **http://127.0.0.1:8000**:
- **Dashboard UI:** http://127.0.0.1:8000/
- **API Docs (Swagger):** http://127.0.0.1:8000/docs

> On first startup, if `data/dataset.json` or `data/schedule.json` don't exist, the server auto-generates them.

---

## Usage Guide

### CLI: Run the Replanner with Disruptions

```bash
# Company delayed by 2 hours
python -m engine.replanner \
  --dataset data/dataset.json \
  --schedule data/schedule.json \
  --disruption-type COMPANY_DELAY \
  --target-id COMP_001 \
  --delay-hours 2

# Panel dropout
python -m engine.replanner \
  --dataset data/dataset.json \
  --schedule data/schedule.json \
  --disruption-type PANEL_DROPOUT \
  --target-id PANEL_COMP002_1

# Student withdrawal
python -m engine.replanner \
  --dataset data/dataset.json \
  --schedule data/schedule.json \
  --disruption-type STUDENT_WITHDRAWAL \
  --target-id STU_0035

# Room unavailable
python -m engine.replanner \
  --dataset data/dataset.json \
  --schedule data/schedule.json \
  --disruption-type ROOM_UNAVAILABLE \
  --target-id ROOM_005
```

Running without arguments executes a **sample compound disruption** (company delay + panel dropout + student withdrawal).

### Dashboard: Visual Disruption Injection

1. Start the server: `python -m api.server`
2. Open http://127.0.0.1:8000/ in a browser
3. Use the disruption controls to inject events and observe real-time schedule updates

---

## API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/schedule` | Returns the current schedule (interviews + metrics) |
| `GET` | `/api/dataset` | Returns the full dataset (companies, students, rooms) |
| `POST` | `/api/replan` | Applies disruption events and returns a structured diff |
| `POST` | `/api/reset` | Resets the schedule to the baseline initial state |

### POST `/api/replan` — Request Body

```json
{
  "events": [
    {
      "type": "COMPANY_DELAY",
      "target_id": "COMP_001",
      "delay_hours": 2
    },
    {
      "type": "PANEL_DROPOUT",
      "target_id": "PANEL_COMP002_1"
    },
    {
      "type": "STUDENT_WITHDRAWAL",
      "target_id": "STU_0035"
    },
    {
      "type": "ROOM_UNAVAILABLE",
      "target_id": "ROOM_005"
    }
  ]
}
```

### POST `/api/replan` — Response Structure

```json
{
  "diff": {
    "moved": [...],
    "cancelled": [...],
    "newly_scheduled": [...],
    "still_unscheduled": [...],
    "who_to_notify": [...],
    "churn_metrics": {
      "previously_scheduled_count": 500,
      "moved_count": 10,
      "cancelled_count": 3,
      "total_churn_count": 13,
      "replan_churn_pct": 2.6,
      "currently_scheduled_count": 497,
      "currently_unscheduled_count": 1710
    }
  },
  "schedule": { ... }
}
```

---

## Quality Metrics & Evaluation

The scheduler computes and reports these metrics after every run:

| Metric | Description | Target |
| :--- | :--- | :--- |
| **Placement Rate** | % of requested interviews successfully scheduled | DREAM/NICHE: 100%, MID: > 85% |
| **Room Utilization** | % of room-slots occupied | > 90% |
| **Panel Utilization** | % of panel-slots occupied | Tier-dependent |
| **Avg Student Wait Time** | Mean idle gap between a student's consecutive interviews | < 120 mins |
| **Max Student Wait Time** | Worst-case idle gap for any student | Monitored |
| **Replan Churn %** | % of interviews disturbed per disruption event | < 5% single, < 10% compound |
| **Unscheduled Diagnostics** | Breakdown by reason: `STUDENT_CLASH`, `PANEL_CONTENTION`, `ROOM_CONTENTION`, `CAPACITY_EXCEEDED` | For root-cause analysis |

---

## Design Decisions & Tradeoffs

### Why Priority CSP over CP-SAT / OR-Tools?

| Factor | Priority CSP (ours) | CP-SAT / ILP |
| :--- | :--- | :--- |
| Explainability | Step-by-step, per-interview diagnostics | Black-box `INFEASIBLE` |
| Incremental replan | Localized micro-repair on occupancy sets | Full re-solve required |
| Dependencies | Zero (stdlib only) | Requires `ortools` / `google-cp-sat` |
| Performance | ~250ms for 2,200 interviews | Comparable, but heavier setup |
| Defense readiness | Every decision auditable | Hard to explain displacement |

### Why SQLite over MongoDB?

- **Zero external daemons** — embedded via Python's `sqlite3` module
- **ACID transactional integrity** for compound replan operations
- **Instant reset** — delete and recreate the DB file
- **Decoupled via Repository Pattern** — storage can be swapped without touching scheduling logic

### Constraint Bending Hierarchy

When physical capacity is exhausted, constraints bend in this order:
1. **Mass Recruiter capacity trimming** (automatic)
2. **Mid-Tier slot compression** (automatic)
3. **Coordinator escalation** for Dream/Niche threats (requires human approval)
4. **NEVER: Student/Panel/Room double-booking** (hard invariant)

### Dataset Generation: Power-Law Shortlisting

Shortlists are **not** uniformly random. High-CGPA students in CS/ISE appear on 8–15 company shortlists simultaneously, creating realistic contention that stress-tests the scheduler:

```
Weight = (CGPA - cutoff + 0.5)^2.2 × Branch_Multiplier
```

---

## Documentation Index

Detailed design documents are in the `docs/` directory:

| Document | Contents |
| :--- | :--- |
| [domain-model.md](docs/domain-model.md) | Entity definitions, relationships, and design tradeoffs |
| [dataset-assumptions.md](docs/dataset-assumptions.md) | Dataset distributions, tier profiles, and power-law mechanics |
| [algorithm-notes.md](docs/algorithm-notes.md) | CSP algorithm design, heuristics, and Big-O analysis |
| [metrics.md](docs/metrics.md) | Metric specifications, formulas, and target thresholds |
| [decisions.md](docs/decisions.md) | Constraint bending hierarchy and churn threshold rationale |

---

## Technical Stack

| Layer | Technology |
| :--- | :--- |
| Scheduling Engine | Python 3.10+ (pure stdlib dataclasses) |
| REST API | FastAPI + Uvicorn |
| Coordinator Dashboard | Vanilla HTML/CSS/JS (single-page) |
| Data Storage | JSON files (SQLite-ready via Repository Pattern) |
| Dataset Generator | Python (`random`, `csv`, `json`) |
