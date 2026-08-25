# Dataset Generator Assumptions & Distribution Specifications

## 1. Overview
The placement dataset generator simulates a realistic university campus placement environment. Rather than uniform random sampling, the generator uses empirical distributions and power-law shortlisting mechanics to produce realistic resource contention and schedule clashes.

---

## 2. Company Profiles & Tier Breakdown (Total: 35 Companies)

Companies are partitioned into 4 distinct priority tiers:

| Priority Tier | Count | Interview Day(s) | Panel Count | Duration | Min CGPA | Shortlist Target / Co. |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Mass Recruiter** | 4 | Day 1 | 8 - 14 | 30 mins | 6.0 | 250 - 400 candidates |
| **Mid-Tier** | 10 | Day 1, Day 2 | 4 - 6 | 45 mins | 7.0 | 40 - 80 candidates |
| **Niche** | 12 | Day 1, Day 2, Day 3 | 2 - 4 | 45 mins | 7.5 | 20 - 50 candidates |
| **Dream Tier** | 9 | Day 2, Day 3 | 2 - 3 | 60 mins | 8.5 | 15 - 35 candidates |

---

## 3. Student Pool Demographics (Total: 800 Students)

### 3.1 Academic Branch Distribution
- **Computer Science (CS)**: 35% (280 students)
- **Information Science (ISE)**: 25% (200 students)
- **Electronics & Comm (ECE)**: 20% (160 students)
- **Mechanical (MECH)**: 10% (80 students)
- **Civil Engineering (CIVIL)**: 10% (80 students)

### 3.2 CGPA Distribution
- Modeled as a truncated Gaussian distribution with mean $\mu = 7.6$, standard deviation $\sigma = 1.1$, clamped between $[5.5, 10.0]$.

---

## 4. Power-Law Shortlisting & Skewed Overlap Mechanics

Shortlist allocation is **not** uniform random. It models real placement dynamics where high-performing candidates receive multiple job offers/interviews:

1. **Eligibility Gate**: A candidate must meet `Company.cgpa_cutoff`.
2. **Branch Weight Multiplier ($W_{branch}$)**:
   - CS / ISE: $1.5\times$
   - ECE: $1.0\times$
   - MECH / CIVIL: $0.5\times$
3. **Power-Law Weight Calculation**:
   $$\text{Weight} = (\text{CGPA} - \text{CGPA}_{\text{cutoff}} + 0.5)^{2.2} \times W_{branch}$$
4. **Sampling**: Candidates are sampled weighted by this score until the company's shortlist target count is reached.

### Resulting Contention Impact
Top 10% candidates (CGPA > 9.0 in CS/ISE) appear on 8-15 company shortlists simultaneously. This creates realistic student double-booking pressure during schedule generation.

---

## 5. Physical Infrastructure (Total: 20 Rooms)

- Rooms: `ROOM_101` through `ROOM_120`.
- Capacity: 4 - 8 seats per room.
- Equipment: 100% whiteboards, 50% projector-equipped.

---

## 6. Output Artifacts

- **JSON**: `data/dataset.json` (Structured single-file dump of entities and relations).
- **CSV**: `data/companies.csv`, `data/students.csv`, `data/rooms.csv`, `data/shortlists.csv`.
