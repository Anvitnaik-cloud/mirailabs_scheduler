# Placement Week Scheduler — Domain Model & Entity Architecture

## 1. Overview & Core Philosophy
The Placement Week Scheduler coordinates complex, high-concurrency campus placement interviews across multiple companies, students, interview panels, and physical rooms over a multi-day timeline.

To ensure live defense adaptability, the domain model enforces **strict separation between pure domain entities and persistence/DB logic**. The engine operates solely on Python dataclasses without ORM dependencies.

---

## 2. Core Entities & Properties

### 2.1 Company
Represents an recruiting organization participating in placement week.
- `id` (str): Unique company identifier (e.g., `COMP_001`).
- `name` (str): Company name.
- `priority_tier` (PriorityTier): Enum [`MASS_RECRUITER`, `MID_TIER`, `NICHE`, `DREAM`].
- `interview_day_mask` (List[int]): Days on which the company interviews (e.g., `[1]` for Day 1 mass recruiter, `[2, 3]` for dream tier).
- `interview_duration_mins` (int): Duration of a single candidate interview block (e.g., 30, 45, 60 mins).
- `panel_count` (int): Number of parallel panels company operates.
- `cgpa_cutoff` (float): Minimum student CGPA eligibility threshold.

### 2.2 Student
Represents a graduating candidate seeking placement.
- `id` (str): Unique student identifier (e.g., `STU_0001`).
- `name` (str): Student full name.
- `cgpa` (float): Cumulative Grade Point Average (0.00 - 10.00).
- `branch` (str): Academic branch (e.g., `CS`, `ISE`, `ECE`, `MECH`, `CIVIL`).
- `shortlisted_company_ids` (List[str]): List of company IDs that shortlisted this candidate.

### 2.3 Panel
Represents an evaluation panel (team of interviewers) belonging to a company.
- `id` (str): Unique panel ID (e.g., `PANEL_COMP001_1`).
- `company_id` (str): Foreign reference to parent Company.
- `panel_number` (int): Panel sequence index within company (1..panel_count).

### 2.4 Room
Represents a physical room location available for interviews.
- `id` (str): Unique room ID (e.g., `ROOM_101`).
- `name` (str): Human-readable room label / hall name.
- `capacity` (int): Max seat capacity (default 4 for 1:1 / 2:1 interview setups).
- `has_whiteboard` (bool): Equipment flag.
- `has_projector` (bool): Equipment flag.

### 2.5 TimeSlot
Represents a discrete time interval in the placement schedule grid.
- `id` (str): Unique slot ID (e.g., `SLOT_D1_0900_0930`).
- `day` (int): Placement day index (1, 2, 3, etc.).
- `start_time` (str): ISO format time string `HH:MM` (e.g., `"09:00"`).
- `end_time` (str): ISO format time string `HH:MM` (e.g., `"09:30"`).
- `slot_index` (int): Sequential index across the day grid.
- `duration_mins` (int): Duration in minutes.

### 2.6 Interview
Represents an allocated or unallocated interview session between a student and a company panel.
- `id` (str): Unique interview ID (e.g., `INT_COMP001_STU0042`).
- `student_id` (str): Reference to Student.
- `company_id` (str): Reference to Company.
- `panel_id` (Optional[str]): Assigned Panel ID.
- `room_id` (Optional[str]): Assigned Room ID.
- `slot_id` (Optional[str]): Assigned TimeSlot ID.
- `status` (InterviewStatus): Enum [`SCHEDULED`, `UNSCHEDULED`, `CANCELLED`, `COMPLETED`].
- `unplacement_reason` (Optional[str]): Detailed diagnostic text if `UNSCHEDULED` (e.g., `ROOM_CONTENTION`, `PANEL_CONTENTION`, `STUDENT_CLASH`).

### 2.7 Schedule
Represents the complete state of placement schedule allocations across all days.
- `id` (str): Schedule run identifier.
- `scheduled_interviews` (List[Interview]): Successfully assigned interviews.
- `unscheduled_interviews` (List[Interview]): Unplaced interviews with diagnostic reasons.
- `metrics` (Dict[str, Any]): Metrics report snapshot (% scheduled, clash counts, room/panel utilization, waiting times, churn).

### 2.8 DisruptionEvent
Represents an external disruption injected into the active schedule state.
- `id` (str): Unique event ID.
- `type` (DisruptionType): Enum [`COMPANY_DELAY`, `PANEL_DROPOUT`, `STUDENT_WITHDRAWAL`, `ROOM_UNAVAILABLE`].
- `timestamp` (str): Time of event occurrence/report.
- `payload` (Dict[str, Any]): Event parameters (e.g., `company_id`, `delay_hours`, `panel_id`, `student_id`, `room_id`).
- `status` (str): Status [`PENDING`, `APPLIED`, `FAILED`].

---

## 3. Entity Design Tradeoffs (Live Defense Justification)

1. **Explicit `Panel` Entity vs. Pure Numeric Counting**:
   - *Tradeoff*: Creating distinct `Panel` records increases entity count versus tracking numeric panel counts (`panel_1_busy_slots`).
   - *Defense*: Explicit Panel objects allow localized panel dropouts (Disruption Type 2) and individual panel history without invalidating an entire company's state.

2. **Normalized `TimeSlot` Grid vs. Continuous Datetimes**:
   - *Tradeoff*: Discretizing time into fixed slots limits arbitrary sub-minute scheduling flexibility.
   - *Defense*: Eliminates continuous interval overlap computation complexity ($O(N \log N)$ interval trees $\to O(1)$ hash map lookups), enabling instant constraint checks for student, panel, and room double-booking during live replanning.

3. **First-Class `DisruptionEvent` vs. Inline State Mutators**:
   - *Tradeoff*: Requires event serialization, validation, and structured diff generator code overhead.
   - *Defense*: Enables transaction auditing, replay capability, compound disruption chaining (late recruiter + dropped panel + student withdrawal), and structured diff calculation (`moved`, `cancelled`, `newly_scheduled`, `who_to_notify`).

4. **Decoupled Dataclasses vs. Heavy ORM Models**:
   - *Tradeoff*: Manually converting engine domain models to database schema records.
   - *Defense*: Ensures complete isolation of the algorithm engine from storage drivers. Swapping storage engines (SQLite $\leftrightarrow$ MongoDB $\leftrightarrow$ In-Memory) during the defense requires zero changes to the scheduling or replanning logic.
