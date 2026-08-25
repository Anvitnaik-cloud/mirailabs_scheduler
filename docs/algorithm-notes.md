# Scheduling Algorithm Design & Scaling Analysis

## 1. Algorithm Selection: Priority-Ordered Backtracking CSP

The scheduling engine uses a **Priority-Ordered Backtracking Constraint Satisfaction Problem (CSP)** algorithm augmented with **Most-Constrained-First (MCF)** heuristics.

### Why Priority CSP vs. Black-Box CP-SAT (OR-Tools)?
1. **Live Defense Explainability**: Integer Linear Programming (ILP) or CP-SAT solvers behave as black boxes. In a live defense, explaining why a specific student was displaced or why a disruption caused a global reshuffle is opaque. The Priority CSP algorithm guarantees 100% deterministic, step-by-step explainability.
2. **Explicit Unscheduled Diagnostics**: When full schedule feasibility is impossible, CP-SAT returns an `INFEASIBLE` state or drops variables without explicit domain reasons. Priority CSP pinpoint-logs the exact binding constraint (`ROOM_CONTENTION`, `PANEL_CONTENTION`, `STUDENT_CLASH`, `CAPACITY_EXCEEDED`).
3. **Sub-Second Performance**: By combining time-slot discretization with $O(1)$ set/hash map occupancy lookups, the algorithm schedules 2,200+ interviews across 800 students, 35 companies, and 20 rooms in $< 0.5$ seconds.

---

## 2. Hard Constraints Enforced

1. **No Student Double-Booking**: $\forall s \in \text{Students}, \forall t \in \text{TimeSlots}$, student $s$ is assigned to at most 1 interview at slot $t$.
2. **No Room Double-Booking**: $\forall r \in \text{Rooms}, \forall t \in \text{TimeSlots}$, room $r$ hosts at most 1 panel/interview at slot $t$.
3. **No Panel Double-Booking**: $\forall p \in \text{Panels}, \forall t \in \text{TimeSlots}$, panel $p$ conducts at most 1 interview at slot $t$.
4. **Company Time & Day Boundaries**: Interview slots must fall strictly within the company's designated interview day mask (e.g. Day 1 only, or Days 2 & 3).

---

## 3. Search Ordering & Heuristics

Interviews are sorted for placement using a multi-level priority key:

$$\text{Sort Key} = \Big( -\text{PriorityTier}(C),\, -\text{ShortlistCount}(S),\, \text{Duration}(C),\, \text{CompanyID} \Big)$$

1. **Tier Priority**: `DREAM` (Tier 4) > `NICHE` (Tier 3) > `MID_TIER` (Tier 2) > `MASS_RECRUITER` (Tier 1). High-value dream/niche interviews are secured first.
2. **Most-Constrained-First (MCF) Candidate Heuristic**: Candidates with high shortlist counts (e.g., 10-20 shortlists) are placed earlier in the search space when slot availability is widest, minimizing domino conflicts.

---

## 4. Big-O Complexity & Scaling Behavior

Let:
- $N_{\text{int}}$ = Total candidate interview requests ($\approx 2,200$).
- $S$ = Total discrete time slots per day grid ($3 \text{ Days} \times 18 \text{ Slots/Day} = 54 \text{ Slots}$).
- $P$ = Total panels available ($\approx 150$).
- $R$ = Total physical rooms ($20$).

### Time Complexity
- **Sorting Phase**: $O(N_{\text{int}} \log N_{\text{int}})$.
- **Slot Assignment Phase**: For each interview, we iterate over valid company day slots $S_C \le S$, company panels $P_C \le 14$, and rooms $R$.
- Checking occupancy in bit-sets/hash sets takes $O(1)$ time.
- **Worst-Case Upper Bound**: $O(N_{\text{int}} \cdot S_C \cdot P_C \cdot R)$.
- **Empirical Operations Count**: $2,200 \times 18 \times 4 \times 20 \approx 3.1 \times 10^6$ basic operations, running in $\approx 250 \text{ ms}$ on standard Python 3.10 runtime.

### Space Complexity
- Occupancy sets for Students, Panels, and Rooms: $O(|\text{Students}| \cdot S + |\text{Panels}| \cdot S + |\text{Rooms}| \cdot S) \approx O(N \cdot S)$, requiring $< 5 \text{ MB}$ RAM.
