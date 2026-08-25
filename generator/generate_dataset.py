"""
Placement Week Scheduler - Realistic Dataset Generator
Generates reproducible company, student, shortlist, and room datasets.
"""
import argparse
import csv
import json
import os
import random
from typing import List, Dict, Any

from engine.models import PriorityTier


COMPANY_NAMES_BY_TIER = {
    PriorityTier.MASS_RECRUITER: [
        "TCS Digital", "Accenture Tech", "Infosys Systems", "Cognizant Technology"
    ],
    PriorityTier.MID_TIER: [
        "Capgemini Engineering", "Wipro Turbo", "LTI Mindtree", "HCL Tech",
        "Dell Technologies", "Bosch India", "Schneider Electric", "Oracle Financial",
        "Samsung R&D", "Siemens Healthineers"
    ],
    PriorityTier.NICHE: [
        "Zscaler Cyber", "Nvidia Embedded", "Qualcomm Wireless", "Texas Instruments",
        "AMD VLSI", "Palo Alto Networks", "Thoughtworks", "Synopsys Systems",
        "Cadence Design", "Cisco Systems", "Akamai Networks", "Juniper Cloud"
    ],
    PriorityTier.DREAM: [
        "Google India", "Microsoft IDC", "Atlassian Tech", "Uber Engineering",
        "Amazon AWS", "Directi Media", "Goldman Sachs", "DE Shaw & Co", "Arcesium"
    ]
}

BRANCHES = ["CS", "ISE", "ECE", "MECH", "CIVIL"]
BRANCH_WEIGHTS = [0.35, 0.25, 0.20, 0.10, 0.10]
BRANCH_SHORTLIST_MULTIPLIER = {
    "CS": 1.5,
    "ISE": 1.5,
    "ECE": 1.0,
    "MECH": 0.5,
    "CIVIL": 0.5,
}

FIRST_NAMES = [
    "Aarav", "Ananya", "Rohan", "Priya", "Aditya", "Sneha", "Vikram", "Kavya",
    "Rahul", "Neha", "Siddharth", "Pooja", "Arjun", "Divya", "Varun", "Ishita",
    "Karan", "Riya", "Yash", "Meera", "Abhinav", "Shreya", "Nikhil", "Tanvi"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Rao", "Nair", "Iyer", "Gupta", "Deshmukh",
    "Kulkarni", "Reddy", "Joshi", "Kumar", "Singh", "Chowdhury", "Mehta", "Bhat"
]


def generate_companies() -> List[Dict[str, Any]]:
    companies = []
    comp_counter = 1

    # Tier 1: Mass Recruiters (4) - Day 1
    for name in COMPANY_NAMES_BY_TIER[PriorityTier.MASS_RECRUITER]:
        companies.append({
            "id": f"COMP_{comp_counter:03d}",
            "name": name,
            "priority_tier": PriorityTier.MASS_RECRUITER.name,
            "priority_tier_val": PriorityTier.MASS_RECRUITER.value,
            "interview_day_mask": [1],
            "interview_duration_mins": 30,
            "panel_count": random.randint(10, 14),
            "cgpa_cutoff": 6.0,
            "shortlist_target": random.randint(220, 320)
        })
        comp_counter += 1

    # Tier 2: Mid Tier (10) - Days 1 & 2
    for name in COMPANY_NAMES_BY_TIER[PriorityTier.MID_TIER]:
        days = [1] if random.random() < 0.4 else ([2] if random.random() < 0.7 else [1, 2])
        companies.append({
            "id": f"COMP_{comp_counter:03d}",
            "name": name,
            "priority_tier": PriorityTier.MID_TIER.name,
            "priority_tier_val": PriorityTier.MID_TIER.value,
            "interview_day_mask": days,
            "interview_duration_mins": 45,
            "panel_count": random.randint(4, 6),
            "cgpa_cutoff": 7.0,
            "shortlist_target": random.randint(40, 75)
        })
        comp_counter += 1

    # Tier 3: Niche (12) - Days 1, 2 & 3
    for name in COMPANY_NAMES_BY_TIER[PriorityTier.NICHE]:
        day_choice = random.choice([[1], [2], [3], [1, 2], [2, 3]])
        companies.append({
            "id": f"COMP_{comp_counter:03d}",
            "name": name,
            "priority_tier": PriorityTier.NICHE.name,
            "priority_tier_val": PriorityTier.NICHE.value,
            "interview_day_mask": day_choice,
            "interview_duration_mins": 45,
            "panel_count": random.randint(2, 4),
            "cgpa_cutoff": 7.5,
            "shortlist_target": random.randint(25, 45)
        })
        comp_counter += 1

    # Tier 4: Dream (9) - Days 2 & 3
    for name in COMPANY_NAMES_BY_TIER[PriorityTier.DREAM]:
        day_choice = random.choice([[2], [3], [2, 3]])
        companies.append({
            "id": f"COMP_{comp_counter:03d}",
            "name": name,
            "priority_tier": PriorityTier.DREAM.name,
            "priority_tier_val": PriorityTier.DREAM.value,
            "interview_day_mask": day_choice,
            "interview_duration_mins": 60,
            "panel_count": random.randint(2, 3),
            "cgpa_cutoff": 8.5,
            "shortlist_target": random.randint(15, 30)
        })
        comp_counter += 1

    return companies


def generate_students(num_students: int = 800) -> List[Dict[str, Any]]:
    students = []
    for i in range(1, num_students + 1):
        branch = random.choices(BRANCHES, weights=BRANCH_WEIGHTS, k=1)[0]
        # CGPA truncated normal distribution between 5.5 and 10.0
        raw_cgpa = random.gauss(7.6, 1.1)
        cgpa = round(max(5.5, min(10.0, raw_cgpa)), 2)
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        
        students.append({
            "id": f"STU_{i:04d}",
            "name": name,
            "cgpa": cgpa,
            "branch": branch,
            "shortlisted_company_ids": []
        })
    return students


def generate_rooms(num_rooms: int = 20) -> List[Dict[str, Any]]:
    rooms = []
    for i in range(1, num_rooms + 1):
        rooms.append({
            "id": f"ROOM_{i:03d}",
            "name": f"Placement Block Hall {i:02d}",
            "capacity": random.choice([4, 6, 8]),
            "has_whiteboard": True,
            "has_projector": random.choice([True, False])
        })
    return rooms


def assign_power_law_shortlists(students: List[Dict[str, Any]], companies: List[Dict[str, Any]]):
    """
    Applies power-law shortlist probability based on CGPA and Branch preference.
    Ensures high-performing CS/ISE candidates appear on multiple company shortlists.
    """
    for comp in companies:
        cutoff = comp["cgpa_cutoff"]
        target_count = comp["shortlist_target"]
        
        eligible_students = [s for s in students if s["cgpa"] >= cutoff]
        if not eligible_students:
            continue
        
        # Calculate power-law selection weights
        weights = []
        for s in eligible_students:
            cgpa_delta = s["cgpa"] - cutoff + 0.5
            branch_mult = BRANCH_SHORTLIST_MULTIPLIER.get(s["branch"], 1.0)
            weight = (cgpa_delta ** 2.2) * branch_mult
            weights.append(weight)
        
        # Sample without replacement weighted by candidate score
        sample_size = min(target_count, len(eligible_students))
        selected_students = []
        
        # Weighted random sampling without replacement
        pool = list(zip(eligible_students, weights))
        for _ in range(sample_size):
            if not pool:
                break
            total_w = sum(w for _, w in pool)
            r = random.uniform(0, total_w)
            cum = 0.0
            chosen_idx = 0
            for idx, (stu, w) in enumerate(pool):
                cum += w
                if r <= cum:
                    chosen_idx = idx
                    break
            chosen_stu, _ = pool.pop(chosen_idx)
            selected_students.append(chosen_stu)
        
        # Record shortlisted company on student object
        for s in selected_students:
            s["shortlisted_company_ids"].append(comp["id"])


def export_dataset(dataset: Dict[str, Any], output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Export JSON
    json_path = os.path.join(output_dir, "dataset.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    
    # 2. Export Companies CSV
    comp_path = os.path.join(output_dir, "companies.csv")
    with open(comp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "priority_tier", "interview_day_mask", "interview_duration_mins", "panel_count", "cgpa_cutoff", "shortlist_target"])
        for c in dataset["companies"]:
            writer.writerow([c["id"], c["name"], c["priority_tier"], ";".join(map(str, c["interview_day_mask"])), c["interview_duration_mins"], c["panel_count"], c["cgpa_cutoff"], c["shortlist_target"]])

    # 3. Export Students CSV
    stu_path = os.path.join(output_dir, "students.csv")
    with open(stu_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "cgpa", "branch", "shortlist_count", "shortlisted_company_ids"])
        for s in dataset["students"]:
            writer.writerow([s["id"], s["name"], s["cgpa"], s["branch"], len(s["shortlisted_company_ids"]), ";".join(s["shortlisted_company_ids"])])

    # 4. Export Rooms CSV
    room_path = os.path.join(output_dir, "rooms.csv")
    with open(room_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "capacity", "has_whiteboard", "has_projector"])
        for r in dataset["rooms"]:
            writer.writerow([r["id"], r["name"], r["capacity"], r["has_whiteboard"], r["has_projector"]])

    # 5. Export Shortlists Junction CSV
    sl_path = os.path.join(output_dir, "shortlists.csv")
    with open(sl_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id", "company_id"])
        for s in dataset["students"]:
            for cid in s["shortlisted_company_ids"]:
                writer.writerow([s["id"], cid])


def print_summary_statistics(dataset: Dict[str, Any]):
    students = dataset["students"]
    companies = dataset["companies"]
    rooms = dataset["rooms"]
    
    total_shortlists = sum(len(s["shortlisted_company_ids"]) for s in students)
    
    # Overlap density counts
    counts = {0: 0, 1: 0, "2-3": 0, "4-6": 0, "7+": 0}
    busiest_student = max(students, key=lambda s: len(s["shortlisted_company_ids"]))
    
    for s in students:
        sc = len(s["shortlisted_company_ids"])
        if sc == 0:
            counts[0] += 1
        elif sc == 1:
            counts[1] += 1
        elif 2 <= sc <= 3:
            counts["2-3"] += 1
        elif 4 <= sc <= 6:
            counts["4-6"] += 1
        else:
            counts["7+"] += 1
            
    print("\n" + "=" * 65)
    print("         DATASET SUMMARY STATISTICS (SANITY CHECK)")
    print("=" * 65)
    print(f"Total Companies   : {len(companies)} (Mass: 4, Mid: 10, Niche: 12, Dream: 9)")
    print(f"Total Students    : {len(students)}")
    print(f"Total Rooms       : {len(rooms)}")
    print(f"Total Shortlists  : {total_shortlists} (Avg {total_shortlists / len(students):.2f} per student)")
    print("-" * 65)
    print("Student Shortlist Overlap Distribution:")
    print(f"  - 0 Shortlists  : {counts[0]:3d} ({counts[0]/len(students)*100:.1f}%)")
    print(f"  - 1 Shortlist   : {counts[1]:3d} ({counts[1]/len(students)*100:.1f}%)")
    print(f"  - 2-3 Shortlists: {counts['2-3']:3d} ({counts['2-3']/len(students)*100:.1f}%)")
    print(f"  - 4-6 Shortlists: {counts['4-6']:3d} ({counts['4-6']/len(students)*100:.1f}%)")
    print(f"  - 7+ Shortlists : {counts['7+']:3d} ({counts['7+']/len(students)*100:.1f}%)")
    print("-" * 65)
    print(f"Busiest Candidate : {busiest_student['name']} ({busiest_student['id']})")
    print(f"  - Branch: {busiest_student['branch']} | CGPA: {busiest_student['cgpa']} | Shortlists: {len(busiest_student['shortlisted_company_ids'])}")
    print("-" * 65)
    
    # Tier breakdown
    tier_summary = {}
    for c in companies:
        tier = c["priority_tier"]
        if tier not in tier_summary:
            tier_summary[tier] = {"count": 0, "shortlists": 0, "panels": 0}
        tier_summary[tier]["count"] += 1
        tier_summary[tier]["shortlists"] += c["shortlist_target"]
        tier_summary[tier]["panels"] += c["panel_count"]
        
    print("Company Tier Breakdown:")
    for tier, data in tier_summary.items():
        print(f"  - {tier:<15}: {data['count']:2d} companies | {data['panels']:2d} total panels | {data['shortlists']:4d} shortlisted candidates")
    print("=" * 65 + "\n")


def generate(seed: int = 42, output_dir: str = "data") -> Dict[str, Any]:
    random.seed(seed)
    
    companies = generate_companies()
    students = generate_students(800)
    rooms = generate_rooms(20)
    
    assign_power_law_shortlists(students, companies)
    
    dataset = {
        "seed": seed,
        "companies": companies,
        "students": students,
        "rooms": rooms
    }
    
    export_dataset(dataset, output_dir)
    print_summary_statistics(dataset)
    return dataset


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Placement Week Realistic Dataset Generator")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory for JSON and CSV files")
    args = parser.parse_args()
    
    generate(seed=args.seed, output_dir=args.output_dir)
