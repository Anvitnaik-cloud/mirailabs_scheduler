"""
Placement Week Scheduler - Priority-Ordered CSP Scheduler Engine
Enforces hard constraints, explicit unscheduled diagnostics, and full quality metrics.
"""
import argparse
import json
from dataclasses import asdict
from typing import List, Dict, Set, Tuple, Optional, Any

from engine.models import (
    Company, Student, Room, TimeSlot, Panel, Interview,
    Schedule, PriorityTier, InterviewStatus
)


def generate_time_slots() -> List[TimeSlot]:
    """
    Generates discrete 30-minute time slots across Days 1, 2, and 3 (09:00 - 18:00).
    Total 18 slots per day = 54 slots total.
    """
    slots = []
    global_index = 0
    for day in range(1, 4):
        slot_in_day = 0
        for hour in range(9, 18):
            for minute in (0, 30):
                start_h, start_m = hour, minute
                end_h = hour if minute == 0 else hour + 1
                end_m = 30 if minute == 0 else 0
                
                start_str = f"{start_h:02d}:{start_m:02d}"
                end_str = f"{end_h:02d}:{end_m:02d}"
                slot_id = f"SLOT_D{day}_{start_h:02d}{start_m:02d}_{end_h:02d}{end_m:02d}"
                
                slots.append(TimeSlot(
                    id=slot_id,
                    day=day,
                    start_time=start_str,
                    end_time=end_str,
                    duration_mins=30,
                    slot_index=global_index
                ))
                global_index += 1
                slot_in_day += 1
    return slots


class PlacementScheduler:
    def __init__(self, companies: List[Company], students: List[Student], rooms: List[Room]):
        self.companies = {c.id: c for c in companies}
        self.students = {s.id: s for s in students}
        self.rooms = {r.id: r for r in rooms}
        self.time_slots = generate_time_slots()
        
        # Organize slots by day
        self.slots_by_day: Dict[int, List[TimeSlot]] = {}
        for slot in self.time_slots:
            self.slots_by_day.setdefault(slot.day, []).append(slot)
            
        # Build panels for each company
        self.panels: Dict[str, List[Panel]] = {}
        for comp in companies:
            comp_panels = []
            for p_num in range(1, comp.panel_count + 1):
                p_id = f"PANEL_{comp.id}_{p_num}"
                comp_panels.append(Panel(id=p_id, company_id=comp.id, panel_number=p_num))
            self.panels[comp.id] = comp_panels

        # Occupancy Tracking sets for O(1) constraint verification
        self.student_occupied: Set[Tuple[str, str]] = set()  # (student_id, slot_id)
        self.panel_occupied: Set[Tuple[str, str]] = set()    # (panel_id, slot_id)
        self.room_occupied: Set[Tuple[str, str]] = set()     # (room_id, slot_id)
        
        # Clash counter during search
        self.student_clash_attempts = 0

    def get_required_slots_count(self, duration_mins: int) -> int:
        """30 mins -> 1 slot, 45 mins / 60 mins -> 2 slots."""
        return 1 if duration_mins <= 30 else 2

    def solve(self) -> Schedule:
        # Build raw interview requests from student shortlists
        interview_requests: List[Tuple[Student, Company]] = []
        for student in self.students.values():
            for comp_id in student.shortlisted_company_ids:
                if comp_id in self.companies:
                    interview_requests.append((student, self.companies[comp_id]))

        # Sort requests using Most-Constrained-First (MCF) heuristics:
        # 1. Company Priority Tier (DREAM=4 > NICHE=3 > MID=2 > MASS=1)
        # 2. Student Shortlist Count (most constrained candidate first)
        # 3. Company CGPA Cutoff
        interview_requests.sort(key=lambda req: (
            -req[1].priority_tier.value,
            -len(req[0].shortlisted_company_ids),
            -req[1].cgpa_cutoff,
            req[1].id,
            req[0].id
        ))

        scheduled_interviews: List[Interview] = []
        unscheduled_interviews: List[Interview] = []

        interview_counter = 1
        for student, company in interview_requests:
            int_id = f"INT_{company.id}_{student.id}"
            interview = Interview(
                id=int_id,
                student_id=student.id,
                company_id=company.id,
                status=InterviewStatus.UNSCHEDULED
            )
            
            placed, reason = self._try_place_interview(interview, student, company)
            if placed:
                interview.status = InterviewStatus.SCHEDULED
                scheduled_interviews.append(interview)
            else:
                interview.status = InterviewStatus.UNSCHEDULED
                interview.unplacement_reason = reason
                unscheduled_interviews.append(interview)
            
            interview_counter += 1

        # Calculate Quality Metrics
        metrics = self._calculate_metrics(scheduled_interviews, unscheduled_interviews, len(interview_requests))
        
        return Schedule(
            id="SCHED_INITIAL",
            scheduled_interviews=scheduled_interviews,
            unscheduled_interviews=unscheduled_interviews,
            metrics=metrics
        )

    def _try_place_interview(
        self, interview: Interview, student: Student, company: Company
    ) -> Tuple[bool, Optional[str]]:
        req_slots = self.get_required_slots_count(company.interview_duration_mins)
        comp_panels = self.panels[company.id]
        available_rooms = list(self.rooms.values())
        
        student_conflict_encountered = False
        room_conflict_encountered = False
        panel_conflict_encountered = False

        # Iterate over company's allowed interview days
        for day in company.interview_day_mask:
            day_slots = self.slots_by_day.get(day, [])
            
            # Slide window over slots
            for idx in range(len(day_slots) - req_slots + 1):
                target_slots = day_slots[idx : idx + req_slots]
                target_slot_ids = [s.id for s in target_slots]
                
                # Check 1: Is student free across target_slots?
                student_free = all((student.id, sid) not in self.student_occupied for sid in target_slot_ids)
                if not student_free:
                    student_conflict_encountered = True
                    self.student_clash_attempts += 1
                    continue

                # Check 2: Is any panel free across target_slots?
                for panel in comp_panels:
                    panel_free = all((panel.id, sid) not in self.panel_occupied for sid in target_slot_ids)
                    if not panel_free:
                        panel_conflict_encountered = True
                        continue

                    # Check 3: Is any room free across target_slots?
                    for room in available_rooms:
                        room_free = all((room.id, sid) not in self.room_occupied for sid in target_slot_ids)
                        if not room_free:
                            room_conflict_encountered = True
                            continue

                        # Placed successfully! Commit occupancy
                        for sid in target_slot_ids:
                            self.student_occupied.add((student.id, sid))
                            self.panel_occupied.add((panel.id, sid))
                            self.room_occupied.add((room.id, sid))
                            
                        interview.panel_id = panel.id
                        interview.room_id = room.id
                        interview.slot_id = target_slot_ids[0]  # Start slot
                        return True, None

        # Diagnostics ranking when placement fails
        if student_conflict_encountered and not panel_conflict_encountered and not room_conflict_encountered:
            return False, "STUDENT_CLASH"
        elif panel_conflict_encountered and not room_conflict_encountered:
            return False, "PANEL_CONTENTION"
        elif room_conflict_encountered:
            return False, "ROOM_CONTENTION"
        else:
            return False, "CAPACITY_EXCEEDED"

    def _calculate_metrics(
        self, scheduled: List[Interview], unscheduled: List[Interview], total_requested: int
    ) -> Dict[str, Any]:
        scheduled_count = len(scheduled)
        unscheduled_count = len(unscheduled)
        placement_rate_pct = round((scheduled_count / total_requested * 100), 2) if total_requested > 0 else 0.0

        # Room Utilization Rate
        total_possible_room_slots = len(self.rooms) * len(self.time_slots)
        total_used_room_slots = len(self.room_occupied)
        room_utilization_pct = round((total_used_room_slots / total_possible_room_slots * 100), 2) if total_possible_room_slots > 0 else 0.0

        # Panel Utilization Rate
        total_possible_panel_slots = 0
        for comp in self.companies.values():
            allowed_days = len(comp.interview_day_mask)
            total_possible_panel_slots += comp.panel_count * (allowed_days * 18)
        total_used_panel_slots = len(self.panel_occupied)
        panel_utilization_pct = round((total_used_panel_slots / total_possible_panel_slots * 100), 2) if total_possible_panel_slots > 0 else 0.0

        # Student Waiting Times
        student_schedules: Dict[str, List[int]] = {}
        slot_map = {s.id: s.slot_index for s in self.time_slots}
        for intv in scheduled:
            if intv.slot_id in slot_map:
                student_schedules.setdefault(intv.student_id, []).append(slot_map[intv.slot_id])

        wait_times_mins = []
        for s_id, s_indices in student_schedules.items():
            if len(s_indices) > 1:
                s_indices.sort()
                for i in range(len(s_indices) - 1):
                    # Gap in slot index * 30 mins
                    gap_slots = s_indices[i+1] - s_indices[i] - 1
                    if gap_slots > 0:
                        wait_times_mins.append(gap_slots * 30)

        avg_wait_mins = round(sum(wait_times_mins) / len(wait_times_mins), 1) if wait_times_mins else 0.0
        max_wait_mins = max(wait_times_mins) if wait_times_mins else 0

        # Diagnostics breakdown for unscheduled
        diagnostic_counts: Dict[str, int] = {}
        for u in unscheduled:
            reason = u.unplacement_reason or "UNKNOWN"
            diagnostic_counts[reason] = diagnostic_counts.get(reason, 0) + 1

        return {
            "total_interviews_requested": total_requested,
            "scheduled_count": scheduled_count,
            "unscheduled_count": unscheduled_count,
            "placement_rate_pct": placement_rate_pct,
            "student_clash_attempts": self.student_clash_attempts,
            "room_utilization_pct": room_utilization_pct,
            "panel_utilization_pct": panel_utilization_pct,
            "avg_student_wait_time_mins": avg_wait_mins,
            "max_student_wait_time_mins": max_wait_mins,
            "replan_churn_count": 0,
            "replan_churn_pct": 0.0,
            "unscheduled_diagnostics_breakdown": diagnostic_counts
        }


def run_scheduler_from_dataset(dataset_path: str, output_path: Optional[str] = None) -> Schedule:
    with open(dataset_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    companies = []
    for c in raw_data["companies"]:
        companies.append(Company(
            id=c["id"],
            name=c["name"],
            priority_tier=PriorityTier[c["priority_tier"]],
            interview_day_mask=c["interview_day_mask"],
            interview_duration_mins=c["interview_duration_mins"],
            panel_count=c["panel_count"],
            cgpa_cutoff=c["cgpa_cutoff"]
        ))

    students = []
    for s in raw_data["students"]:
        students.append(Student(
            id=s["id"],
            name=s["name"],
            cgpa=s["cgpa"],
            branch=s["branch"],
            shortlisted_company_ids=s["shortlisted_company_ids"]
        ))

    rooms = []
    for r in raw_data["rooms"]:
        rooms.append(Room(
            id=r["id"],
            name=r["name"],
            capacity=r["capacity"],
            has_whiteboard=r["has_whiteboard"],
            has_projector=r["has_projector"]
        ))

    scheduler = PlacementScheduler(companies, students, rooms)
    schedule = scheduler.solve()

    if output_path:
        def serialize_interview(intv: Interview) -> Dict[str, Any]:
            d = asdict(intv)
            if isinstance(d.get("status"), InterviewStatus):
                d["status"] = d["status"].value
            return d

        out_dict = {
            "id": schedule.id,
            "metrics": schedule.metrics,
            "scheduled_interviews": [serialize_interview(i) for i in schedule.scheduled_interviews],
            "unscheduled_interviews": [serialize_interview(i) for i in schedule.unscheduled_interviews]
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out_dict, f, indent=2)

    return schedule


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Placement Week Feasible Schedule Generator")
    parser.add_argument("--dataset", type=str, default="data/dataset.json", help="Path to input dataset JSON")
    parser.add_argument("--output", type=str, default="data/schedule.json", help="Path to output schedule JSON")
    args = parser.parse_args()

    sched = run_scheduler_from_dataset(args.dataset, args.output)
    
    print("\n" + "=" * 65)
    print("           INITIAL SCHEDULE RUN RESULTS & METRICS")
    print("=" * 65)
    print(f"Total Interviews Requested : {sched.metrics['total_interviews_requested']}")
    print(f"Successfully Scheduled     : {sched.metrics['scheduled_count']} ({sched.metrics['placement_rate_pct']}%)")
    print(f"Unscheduled (Infeasible)   : {sched.metrics['unscheduled_count']}")
    print(f"Student Clash Attempts     : {sched.metrics['student_clash_attempts']}")
    print("-" * 65)
    print(f"Room Utilization Rate      : {sched.metrics['room_utilization_pct']}%")
    print(f"Panel Utilization Rate     : {sched.metrics['panel_utilization_pct']}%")
    print(f"Avg Student Waiting Time   : {sched.metrics['avg_student_wait_time_mins']} mins")
    print(f"Max Student Waiting Time   : {sched.metrics['max_student_wait_time_mins']} mins")
    print("-" * 65)
    print("Unscheduled Diagnostics Breakdown (Ranked by Priority):")
    for reason, count in sched.metrics["unscheduled_diagnostics_breakdown"].items():
        print(f"  - {reason:<22}: {count:4d} interviews")
    print("=" * 65 + "\n")
