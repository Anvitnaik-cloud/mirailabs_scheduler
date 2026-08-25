# Defense Decisions & Tradeoff Architecture

## 1. What "Good" Means for This Placement Schedule

A "good" placement week schedule is not defined by raw interview count alone, but by a multi-objective balance across candidate value, physical constraint safety, and operational stability.

### Mathematical Objective Function
A schedule $S$ is considered **Optimal / Good** if it maximizes:

$$\text{Score}(S) = w_1 \cdot \text{Placement}_{\text{Dream/Niche}} + w_2 \cdot \text{RoomUtil} - w_3 \cdot \text{WaitTime}_{\text{Avg}} - w_4 \cdot \text{ReplanChurn}$$

where $w_1 \gg w_2 \gg w_3 \gg w_4$.

### Operational Definition Criteria:
1. **Tier Honor Guarantee**: $100\%$ placement rate for Dream (Tier 4) and Niche (Tier 3) companies. High-salary, specialized roles must never be sacrificed for high-volume recruiters.
2. **High Infrastructure Efficiency**: Room utilization rate $> 90\%$ without physical double-booking.
3. **Candidate Well-Being**: Average candidate idle wait time $< 120$ minutes between interviews.
4. **Disruption Stability**: Replan churn remains $< 5\%$ for single disruptions and $< 10\%$ for compound disruptions.

---

## 2. Constraint Bending Hierarchy & System vs. Escalation Boundaries

When physical infrastructure (20 rooms over 3 days = 1,080 room-slots max) is insufficient to satisfy total demand (2,207 requested interviews), constraints must bend deterministically.

### Tiered Bending Order (First to Bend $\to$ Last to Bend)

```text
[BEND FIRST] Mass Recruiter Parallel Candidate Capacity
     │
     ▼
[BEND SECOND] Mid-Tier Candidate Over-Allocation
     │
     ▼
[ESCALATE TO COORDINATOR] Dream/Niche Day Shift or Room Expansion
     │
     ▼
[HARD INVARIANT — NEVER BEND] Student, Panel, or Room Double-Booking
```

1. **Level 1: Automatic System Bending (Mass Recruiter Capacity Trimming)**:
   - *Behavior*: When room capacity is exhausted, the scheduler automatically drops excess candidate slots from Mass Recruiters (Tier 1).
   - *Reasoning*: Mass recruiters shortlist hundreds of candidates for generic roles. Dropping 50 mass recruiter interviews frees 50 room-slots, preserving 100% of Dream tier interviews.
   - *Automation*: $100\%$ automatic by system.

2. **Level 2: Automatic System Bending (Mid-Tier Slot Compression)**:
   - *Behavior*: If room pressure persists, lower-CGPA candidates in Mid-Tier companies are unplaced.
   - *Automation*: $100\%$ automatic by system with explicit `ROOM_CONTENTION` diagnostics.

3. **Level 3: Coordinator Escalation Boundary**:
   - *Behavior*: If a `PANEL_DROPOUT` or `ROOM_UNAVAILABLE` event threatens to drop a **Dream Tier or Niche Tier** interview, the system does **NOT** auto-cancel it. Instead, it triggers a **Coordinator Escalation Alert**.
   - *Reasoning*: Dropping a Dream company interview damages institutional reputation and student career prospects. A human coordinator must decide whether to:
     - Extend day schedule hours (e.g., add 18:00 - 20:00 evening slots).
     - Authorize an auxiliary room block (e.g., convert Auditorium to Room 21).
   - *Automation*: System surfaces escalation alert in Dashboard; human coordinator clicks to authorize parameter expansion.

---

## 3. Acceptable Churn Threshold Rationale per Disruption Type

Rescheduling an entire campus drive because one company arrived late creates chaos, lost interviews, and candidate panics. Replan churn must be tightly bounded.

| Disruption Event Type | Target Churn Threshold | Justification & Bound Logic |
| :--- | :---: | :--- |
| **Company Delay** (e.g. 2 hrs late) | **$< 10\%$ of company's interviews**<br>($0\%$ of other companies) | Shifting a company's morning block delays only their own morning interviews. By restricting repair to that company's assigned panels/rooms, other companies experience **$0\%$ churn**. |
| **Panel Dropout** (1 panel lost) | **$< 25\%$ of company's interviews** | A single panel loss reduces company throughput by $1/\text{PanelCount}$. Affected interviews are rerouted to remaining panels of the *same* company. Other companies remain untouched. |
| **Room Unavailable** (1 room down) | **$< 3\%$ of total schedule** | Relocates only the $\approx 10-15$ interviews assigned to that specific room into unused room slots. |
| **Student Withdrawal** | **$0\%$ ripple churn** | Freeing a withdrawn candidate's slots never invalidates anyone else. The engine uses freed slots to backfill previously unscheduled candidates (**negative net disruption**). |

### Mathematical Defense of Churn Bound
If a schedule has $N_{\text{sched}} = 500$ interviews, a 2-hour delay of Company A (having 30 interviews, 10 scheduled in morning) invalidates 10 interviews. 
- *Naive Reschedule Churn*: Rescheduling all 500 interviews causes $\sim 300$ moves ($\mathbf{60\% \text{ churn}}$).
- *Our Incremental Replanner Churn*: Touches only 10 interviews ($\mathbf{2\% \text{ churn}}$).
