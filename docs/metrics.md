# Placement Week Scheduler — Metrics & Evaluation Framework

## 1. Overview
The Placement Week Scheduler evaluates schedule quality and replanning performance using quantitative operational metrics. These metrics serve as the primary objective function for both initial schedule generation and disruption repair.

---

## 2. Core Metrics Specifications

### 2.1 Placement Rate (%)
- **Definition**: The percentage of requested candidate interviews successfully scheduled into valid time slots, rooms, and panels.
- **Formula**:
  $$\text{Placement Rate} = \left( \frac{N_{\text{scheduled}}}{N_{\text{total\_requested}}} \right) \times 100\%$$
- **Target**: 
  - `DREAM` Tier (Priority 4): $100\%$
  - `NICHE` Tier (Priority 3): $100\%$
  - `MID` Tier (Priority 2): $> 85\%$
  - `MASS_RECRUITER` Tier (Priority 1): Capacity-bounded ($20-30\%$ in high-contention datasets)

### 2.2 Student Clash Count (Raw Contention)
- **Definition**: The total number of scheduling search attempts where a candidate was already booked in an otherwise valid company panel slot.
- **Significance**: Measures candidate schedule contention caused by power-law shortlist overlap.

### 2.3 Resource Utilization Rates (%)
- **Room Utilization**:
  $$\text{Room Utilization} = \left( \frac{\text{Total Occupied Room Slots}}{\text{Total Available Rooms} \times \text{Total Grid Time Slots}} \right) \times 100\%$$
- **Panel Utilization**:
  $$\text{Panel Utilization} = \left( \frac{\text{Total Occupied Panel Slots}}{\sum (\text{Company Panels} \times \text{Available Slots})} \right) \times 100\%$$
- **Empirical Baseline**: Room utilization reaches $\approx 93.5\%$ on the benchmark 20-room dataset.

### 2.4 Student Idle Waiting Time (Minutes)
- **Definition**: The gap between consecutive interview time slots for a candidate on the same day.
- **Metrics**:
  - `avg_student_wait_time_mins`: Average gap in minutes.
  - `max_student_wait_time_mins`: Maximum gap experienced by any single candidate.
- **Target**: Average wait time $< 120$ minutes.

### 2.5 Replan Churn (%)
- **Definition**: The percentage of previously scheduled interviews whose assigned time slot, room, or panel changed as a result of a disruption repair.
- **Formula**:
  $$\text{Replan Churn \%} = \left( \frac{N_{\text{moved}} + N_{\text{cancelled}}}{N_{\text{previously\_scheduled}}} \right) \times 100\%$$
- **Targets**:
  - `COMPANY_DELAY` (2 hours): $< 10\%$ of company's own interviews, $0\%$ of other companies' interviews.
  - `PANEL_DROPOUT`: $< 25\%$ of company's interviews, $0\%$ of other companies' interviews.
  - `ROOM_UNAVAILABLE`: $< 5\%$ total schedule disturbance.
  - `STUDENT_WITHDRAWAL`: $0\%$ moved, $0\%$ ripple churn (only cancels withdrawn student's slots and backfills unplaced candidates).
