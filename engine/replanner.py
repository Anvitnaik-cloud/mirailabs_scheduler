"""
Placement Week Scheduler - Incremental Replanning Engine
Handles disruptions with minimal churn, localized micro-repairs, and structured diff generation.
"""
import argparse
import json
from dataclasses import asdict
from typing import List, Dict, Set, Tuple, Optional, Any

from engine.models import (
    Company, Student, Room, TimeSlot, Panel, Interview,
    Schedule, PriorityTier, InterviewStatus, DisruptionType, DisruptionEvent
)
from engine.scheduler import generate_time_slots, PlacementScheduler


class IncrementalReplanner:
    def __init__(self, dataset_path: str, schedule_data: Dict[str, Any]):
        # Load dataset entities
        with open(dataset_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        self.companies = {
            c["id"]: Company(
                id=c["id"],
                name=c["name"],
                priority_tier=PriorityTier[c["priority_tier"]],
                interview_day_mask=c["interview_day_mask"],
                interview_duration_mins=c["interview_duration_mins"],
                panel_count=c["panel_count"],
                cgpa_cutoff=c["cgpa_cutoff"]
            ) for c in raw_data["companies"]
        }

        self.students = {
            s["id"]: Student(
                id=s["id"],
                name=s["name"],
                cgpa=s["cgpa"],
                branch=s["branch"],
                shortlisted_company_ids=s["shortlisted_company_ids"]
            ) for s in raw_data["students"]
        }

        self.rooms = {
            r["id"]: Room(
                id=r["id"],
                name=r["name"],
                capacity=r["capacity"],
                has_whiteboard=r["has_whiteboard"],
                has_projector=r["has_projector"]
            ) for r in raw_data["rooms"]
        }

        self.time_slots = generate_time_slots()
        self.slot_map = {s.id: s for s in self.time_slots}
        self.slots_by_day: Dict[int, List[TimeSlot]] = {}
        for slot in self.time_slots:
            self.slots_by_day.setdefault(slot.day, []).append(slot)

        # Active Panels dictionary
        self.panels: Dict[str, List[Panel]] = {}
        for comp in self.companies.values():
            comp_panels = []
            for p_num in range(1, comp.panel_count + 1):
                p_id = f"PANEL_{comp.id}_{p_num}"
                comp_panels.append(Panel(id=p_id, company_id=comp.id, panel_number=p_num))
            self.panels[comp.id] = comp_panels

        # Reconstruct active schedule state
        self.scheduled_interviews: Dict[str, Interview] = {}
        self.unscheduled_interviews: Dict[str, Interview] = {}
        
        for i_data in schedule_data.get("scheduled_interviews", []):
            intv = Interview(
                id=i_data["id"],
                student_id=i_data["student_id"],
                company_id=i_data["company_id"],
                panel_id=i_data.get("panel_id"),
                room_id=i_data.get("room_id"),
                slot_id=i_data.get("slot_id"),
                status=InterviewStatus(i_data["status"])
            )
            self.scheduled_interviews[intv.id] = intv

        for i_data in schedule_data.get("unscheduled_interviews", []):
            intv = Interview(
                id=i_data["id"],
                student_id=i_data["student_id"],
                company_id=i_data["company_id"],
                status=InterviewStatus(i_data["status"]),
                unplacement_reason=i_data.get("unplacement_reason")
            )
            self.unscheduled_interviews[intv.id] = intv

        # Occupancy tracking sets
        self.student_occupied: Set[Tuple[str, str]] = set()
        self.panel_occupied: Set[Tuple[str, str]] = set()
        self.room_occupied: Set[Tuple[str, str]] = set()
        self.disabled_rooms: Set[str] = set()

        self._rebuild_occupancy()

    def _rebuild_occupancy(self):
        self.student_occupied.clear()
        self.panel_occupied.clear()
        self.room_occupied.clear()

        for intv in self.scheduled_interviews.values():
            if intv.is_placed():
                comp = self.companies[intv.company_id]
                req_slots = 1 if comp.interview_duration_mins <= 30 else 2
                start_slot = self.slot_map[intv.slot_id]
                day_slots = self.slots_by_day[start_slot.day]
                
                start_idx = next(i for i, s in enumerate(day_slots) if s.id == start_slot.id)
                target_slot_ids = [day_slots[start_idx + k].id for k in range(req_slots)]
                
                for sid in target_slot_ids:
                    self.student_occupied.add((intv.student_id, sid))
                    self.panel_occupied.add((intv.panel_id, sid))
                    self.room_occupied.add((intv.room_id, sid))

    def get_required_slots_count(self, duration_mins: int) -> int:
        return 1 if duration_mins <= 30 else 2

    def apply_disruptions(self, events: List[DisruptionEvent]) -> Dict[str, Any]:
        """
        Executes chained disruptions incrementally without full schedule recalculation.
        """
        initial_scheduled_count = len(self.scheduled_interviews)
        invalidated_interviews: Dict[str, Interview] = {}
        cancelled_interviews: List[Dict[str, Any]] = []
        who_to_notify: List[Dict[str, Any]] = []
        
        # Step 1: Process Disruption Events and identify invalidated scope
        for event in events:
            if event.type == DisruptionType.COMPANY_DELAY:
                comp_id = event.payload["company_id"]
                delay_hours = event.payload.get("delay_hours", 2)
                comp = self.companies.get(comp_id)
                
                if comp:
                    # Invalidate company interviews scheduled before delay_hours on company days
                    for intv_id, intv in list(self.scheduled_interviews.items()):
                        if intv.company_id == comp_id and intv.slot_id:
                            slot = self.slot_map[intv.slot_id]
                            start_hour = int(slot.start_time.split(":")[0])
                            # If scheduled during delayed morning block (e.g. before 9 + delay_hours)
                            if start_hour < (9 + delay_hours):
                                invalidated_interviews[intv_id] = intv
                                
                    who_to_notify.append({
                        "recipient_type": "COMPANY",
                        "recipient_id": comp_id,
                        "name": comp.name,
                        "message": f"Arrival delayed by {delay_hours} hours. Morning interviews rescheduled."
                    })

            elif event.type == DisruptionType.PANEL_DROPOUT:
                panel_id = event.payload["panel_id"]
                comp_id = event.payload.get("company_id")
                
                # Remove panel from active panels
                if comp_id and comp_id in self.panels:
                    self.panels[comp_id] = [p for p in self.panels[comp_id] if p.id != panel_id]

                for intv_id, intv in list(self.scheduled_interviews.items()):
                    if intv.panel_id == panel_id:
                        invalidated_interviews[intv_id] = intv
                        
                who_to_notify.append({
                    "recipient_type": "PANEL",
                    "recipient_id": panel_id,
                    "name": panel_id,
                    "message": "Panel dropped out. Assigned interviews re-routed."
                })

            elif event.type == DisruptionType.STUDENT_WITHDRAWAL:
                student_id = event.payload["student_id"]
                student = self.students.get(student_id)
                
                # Cancel all scheduled interviews of withdrawn student
                for intv_id, intv in list(self.scheduled_interviews.items()):
                    if intv.student_id == student_id:
                        del self.scheduled_interviews[intv_id]
                        intv.status = InterviewStatus.CANCELLED
                        intv.unplacement_reason = "STUDENT_WITHDREW"
                        cancelled_interviews.append({
                            "interview_id": intv.id,
                            "student_id": student_id,
                            "student_name": student.name if student else student_id,
                            "company_id": intv.company_id,
                            "company_name": self.companies[intv.company_id].name,
                            "reason": "Candidate withdrew placement registration"
                        })

                who_to_notify.append({
                    "recipient_type": "STUDENT",
                    "recipient_id": student_id,
                    "name": student.name if student else student_id,
                    "message": "Student placement registration withdrawn. Freeing reserved room/panel slots."
                })

            elif event.type == DisruptionType.ROOM_UNAVAILABLE:
                room_id = event.payload["room_id"]
                self.disabled_rooms.add(room_id)
                room = self.rooms.get(room_id)
                
                for intv_id, intv in list(self.scheduled_interviews.items()):
                    if intv.room_id == room_id:
                        invalidated_interviews[intv_id] = intv

                who_to_notify.append({
                    "recipient_type": "ROOM",
                    "recipient_id": room_id,
                    "name": room.name if room else room_id,
                    "message": "Room marked unavailable. In-room interviews relocated."
                })

        # Un-commit occupancies of all invalidated interviews
        for intv in invalidated_interviews.values():
            if intv.id in self.scheduled_interviews:
                del self.scheduled_interviews[intv.id]
        
        self._rebuild_occupancy()

        # Step 2: Micro-Repair (Local Relocation of Displaced Interviews)
        moved_interviews: List[Dict[str, Any]] = []
        still_unscheduled: List[Dict[str, Any]] = []
        newly_scheduled: List[Dict[str, Any]] = []

        # Sort invalidated interviews by Priority Tier (Dream > Niche > Mid > Mass)
        sorted_invalidated = sorted(
            invalidated_interviews.values(),
            key=lambda i: (-self.companies[i.company_id].priority_tier.value, i.id)
        )

        for intv in sorted_invalidated:
            old_slot = intv.slot_id
            old_room = intv.room_id
            old_panel = intv.panel_id
            
            student = self.students[intv.student_id]
            comp = self.companies[intv.company_id]
            
            placed, reason = self._try_place_single_interview(intv, student, comp)
            if placed:
                self.scheduled_interviews[intv.id] = intv
                moved_interviews.append({
                    "interview_id": intv.id,
                    "student_id": intv.student_id,
                    "student_name": student.name,
                    "company_id": comp.id,
                    "company_name": comp.name,
                    "old_slot": old_slot,
                    "new_slot": intv.slot_id,
                    "old_room": old_room,
                    "new_room": intv.room_id,
                    "old_panel": old_panel,
                    "new_panel": intv.panel_id
                })
                who_to_notify.append({
                    "recipient_type": "STUDENT",
                    "recipient_id": student.id,
                    "name": student.name,
                    "message": f"Interview with {comp.name} rescheduled to room {intv.room_id} at slot {intv.slot_id}."
                })
            else:
                intv.status = InterviewStatus.UNSCHEDULED
                intv.unplacement_reason = reason
                self.unscheduled_interviews[intv.id] = intv
                still_unscheduled.append({
                    "interview_id": intv.id,
                    "student_id": intv.student_id,
                    "student_name": student.name,
                    "company_id": comp.id,
                    "company_name": comp.name,
                    "reason": reason
                })

        # Step 3: Backfill Opportunistic Placement for previously unscheduled interviews
        sorted_unscheduled = sorted(
            list(self.unscheduled_interviews.values()),
            key=lambda i: (-self.companies[i.company_id].priority_tier.value, i.id)
        )

        for intv in sorted_unscheduled:
            if intv.id in self.scheduled_interviews:
                continue
            student = self.students[intv.student_id]
            comp = self.companies[intv.company_id]
            
            placed, _ = self._try_place_single_interview(intv, student, comp)
            if placed:
                self.scheduled_interviews[intv.id] = intv
                if intv.id in self.unscheduled_interviews:
                    del self.unscheduled_interviews[intv.id]
                newly_scheduled.append({
                    "interview_id": intv.id,
                    "student_id": intv.student_id,
                    "student_name": student.name,
                    "company_id": comp.id,
                    "company_name": comp.name,
                    "slot_id": intv.slot_id,
                    "room_id": intv.room_id
                })

        # Step 4: Calculate Churn Metrics & Construct Diff
        moved_count = len(moved_interviews)
        cancelled_count = len(cancelled_interviews)
        total_churn = moved_count + cancelled_count
        churn_pct = round((total_churn / initial_scheduled_count * 100), 2) if initial_scheduled_count > 0 else 0.0

        # Remove duplicate notification entries
        unique_notifications = []
        seen_notes = set()
        for note in who_to_notify:
            key = (note["recipient_type"], note["recipient_id"], note["message"])
            if key not in seen_notes:
                seen_notes.add(key)
                unique_notifications.append(note)

        return {
            "moved": moved_interviews,
            "cancelled": cancelled_interviews,
            "newly_scheduled": newly_scheduled,
            "still_unscheduled": still_unscheduled,
            "who_to_notify": unique_notifications,
            "churn_metrics": {
                "previously_scheduled_count": initial_scheduled_count,
                "moved_count": moved_count,
                "cancelled_count": cancelled_count,
                "total_churn_count": total_churn,
                "replan_churn_pct": churn_pct,
                "currently_scheduled_count": len(self.scheduled_interviews),
                "currently_unscheduled_count": len(self.unscheduled_interviews)
            }
        }

    def _try_place_single_interview(
        self, interview: Interview, student: Student, company: Company
    ) -> Tuple[bool, Optional[str]]:
        req_slots = self.get_required_slots_count(company.interview_duration_mins)
        comp_panels = self.panels.get(company.id, [])
        available_rooms = [r for r in self.rooms.values() if r.id not in self.disabled_rooms]

        student_conflict = False
        room_conflict = False
        panel_conflict = False

        for day in company.interview_day_mask:
            day_slots = self.slots_by_day.get(day, [])
            
            for idx in range(len(day_slots) - req_slots + 1):
                target_slots = day_slots[idx : idx + req_slots]
                target_slot_ids = [s.id for s in target_slots]
                
                # Check student
                if any((student.id, sid) in self.student_occupied for sid in target_slot_ids):
                    student_conflict = True
                    continue

                # Check panel
                for panel in comp_panels:
                    if any((panel.id, sid) in self.panel_occupied for sid in target_slot_ids):
                        panel_conflict = True
                        continue

                    # Check room
                    for room in available_rooms:
                        if any((room.id, sid) in self.room_occupied for sid in target_slot_ids):
                            room_conflict = True
                            continue

                        # Place interview!
                        for sid in target_slot_ids:
                            self.student_occupied.add((student.id, sid))
                            self.panel_occupied.add((panel.id, sid))
                            self.room_occupied.add((room.id, sid))

                        interview.panel_id = panel.id
                        interview.room_id = room.id
                        interview.slot_id = target_slot_ids[0]
                        interview.status = InterviewStatus.SCHEDULED
                        interview.unplacement_reason = None
                        return True, None

        if student_conflict and not panel_conflict and not room_conflict:
            return False, "STUDENT_CLASH"
        elif panel_conflict and not room_conflict:
            return False, "PANEL_CONTENTION"
        elif room_conflict:
            return False, "ROOM_CONTENTION"
        else:
            return False, "CAPACITY_EXCEEDED"


def print_structured_diff(diff: Dict[str, Any]):
    churn = diff["churn_metrics"]
    print("\n" + "=" * 70)
    print("           REPLAN STRUCTURED DIFF REPORT")
    print("=" * 70)
    print(f"Previously Scheduled  : {churn['previously_scheduled_count']}")
    print(f"Currently Scheduled   : {churn['currently_scheduled_count']}")
    print(f"Interviews Moved      : {churn['moved_count']}")
    print(f"Interviews Cancelled  : {churn['cancelled_count']}")
    print(f"Newly Scheduled       : {len(diff['newly_scheduled'])}")
    print(f"Still Unscheduled     : {len(diff['still_unscheduled'])}")
    print(f"REPLAN CHURN RATE     : {churn['replan_churn_pct']}% ({churn['total_churn_count']} disturbed)")
    print("-" * 70)

    if diff["moved"]:
        print("\n[MOVED INTERVIEWS]")
        for m in diff["moved"][:5]:  # Show top 5
            print(f"  - {m['interview_id']} ({m['student_name']} w/ {m['company_name']}):")
            print(f"    Slot: {m['old_slot']} -> {m['new_slot']} | Room: {m['old_room']} -> {m['new_room']}")
        if len(diff["moved"]) > 5:
            print(f"    ... and {len(diff['moved']) - 5} more moved interviews.")

    if diff["cancelled"]:
        print("\n[CANCELLED INTERVIEWS]")
        for c in diff["cancelled"][:5]:
            print(f"  - {c['interview_id']} ({c['student_name']} w/ {c['company_name']}): {c['reason']}")

    if diff["newly_scheduled"]:
        print("\n[NEWLY SCHEDULED INTERVIEWS]")
        for n in diff["newly_scheduled"][:5]:
            print(f"  - {n['interview_id']} ({n['student_name']} w/ {n['company_name']}): Slot {n['slot_id']} in Room {n['room_id']}")

    print("\n[NOTIFICATION ROSTER]")
    print(f"Total Recipients to Notify: {len(diff['who_to_notify'])}")
    for note in diff["who_to_notify"][:5]:
        print(f"  - [{note['recipient_type']}] {note['name']} ({note['recipient_id']}): {note['message']}")
    if len(diff["who_to_notify"]) > 5:
        print(f"    ... and {len(diff['who_to_notify']) - 5} more notifications.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Incremental Replanning Engine CLI")
    parser.add_argument("--dataset", type=str, default="data/dataset.json", help="Path to input dataset JSON")
    parser.add_argument("--schedule", type=str, default="data/schedule.json", help="Path to input active schedule JSON")
    parser.add_argument("--disruption-type", type=str, choices=["COMPANY_DELAY", "PANEL_DROPOUT", "STUDENT_WITHDRAWAL", "ROOM_UNAVAILABLE"], help="Disruption type")
    parser.add_argument("--target-id", type=str, help="Target ID (company_id, panel_id, student_id, or room_id)")
    parser.add_argument("--delay-hours", type=int, default=2, help="Delay hours for COMPANY_DELAY")
    args = parser.parse_args()

    with open(args.schedule, "r", encoding="utf-8") as f:
        schedule_data = json.load(f)

    replanner = IncrementalReplanner(args.dataset, schedule_data)
    
    events = []
    if args.disruption_type and args.target_id:
        dtype = DisruptionType[args.disruption_type]
        payload = {}
        if dtype == DisruptionType.COMPANY_DELAY:
            payload = {"company_id": args.target_id, "delay_hours": args.delay_hours}
        elif dtype == DisruptionType.PANEL_DROPOUT:
            payload = {"panel_id": args.target_id, "company_id": args.target_id.split("_")[1]}
        elif dtype == DisruptionType.STUDENT_WITHDRAWAL:
            payload = {"student_id": args.target_id}
        elif dtype == DisruptionType.ROOM_UNAVAILABLE:
            payload = {"room_id": args.target_id}

        events.append(DisruptionEvent(
            id="EVENT_CLI_01",
            type=dtype,
            timestamp="10:00",
            payload=payload
        ))

    if not events:
        # Default demo compound disruption if no arguments passed
        print("No specific event provided. Running sample compound disruption...")
        events = [
            DisruptionEvent(
                id="EVENT_01",
                type=DisruptionType.COMPANY_DELAY,
                timestamp="09:00",
                payload={"company_id": "COMP_001", "delay_hours": 2}
            ),
            DisruptionEvent(
                id="EVENT_02",
                type=DisruptionType.PANEL_DROPOUT,
                timestamp="09:30",
                payload={"panel_id": "PANEL_COMP002_1", "company_id": "COMP_002"}
            ),
            DisruptionEvent(
                id="EVENT_03",
                type=DisruptionType.STUDENT_WITHDRAWAL,
                timestamp="10:00",
                payload={"student_id": "STU_0035"}
            )
        ]

    diff = replanner.apply_disruptions(events)
    print_structured_diff(diff)
