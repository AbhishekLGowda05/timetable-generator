# Timetable Generator: Mathematical Relationship Between Classes, Subjects, and Teachers

## Overview

For a timetable to be **feasible** (solvable), there must be enough teachers to cover all the required periods without conflicts. This document explains the mathematical formulas needed to determine the minimum number of teachers.

---

## Basic Variables

| Symbol | Description | Example Value |
|--------|-------------|---------------|
| $C$ | Number of classes/sections | 10 |
| $S$ | Number of subjects | 12 |
| $D$ | Number of school days per week | 6 |
| $P$ | Number of periods per day | 8 |
| $P_w$ | Total periods per week per class | $D \times P = 48$ |
| $T_{max}$ | Max periods a teacher can teach per week | 40-50 |
| $p_s$ | Periods required per week for subject $s$ | Varies (4-7) |

---

## Formula 1: Minimum Teachers for a Single Subject

For a subject that needs $p_s$ periods/week across $C$ classes:

$$T_{min}(s) = \left\lceil \frac{C \times p_s}{T_{max}} \right\rceil$$

**Example (Mathematics):**
- 10 classes × 6 periods/week = 60 periods total
- If teacher max = 50 periods/week
- $T_{min} = \lceil 60/50 \rceil = 2$ teachers minimum

But **we recommend at least $\lceil C/3 \rceil$** teachers per subject for:
- Schedule flexibility
- Covering absences
- Avoiding back-to-back conflicts

---

## Formula 2: Total Teaching Periods

Total periods that need to be taught across all classes:

$$\text{Total Periods} = \sum_{s=1}^{S} (C \times p_s)$$

**Example:**
| Subject | Periods/Week | × 10 Classes |
|---------|--------------|--------------|
| Math | 6 | 60 |
| Science | 5 | 50 |
| English | 5 | 50 |
| SST | 4 | 40 |
| Hindi | 4 | 40 |
| Kannada | 4 | 40 |
| Sanskrit | 4 | 40 |
| PE | 2 | 20 |
| Computer | 2 | 20 |
| Art | 1 | 10 |
| **Total** | | **370 periods** |

---

## Formula 3: Language Block Synchronization Constraint

**This is the MOST restrictive constraint!**

For language block synchronization, 3 language teachers (Hindi, Kannada, Sanskrit) must ALL be free at the same time slot to teach different groups within a section.

### Key Rule:
If $C_{lb}$ sections have language blocks enabled, and each language teacher triplet serves $n$ sections:

$$n_{max} = \left\lfloor \frac{P_w - \text{other commitments}}{p_{lang} \times \text{buffer}} \right\rfloor$$

Practically, each teacher triplet should serve **AT MOST 2-3 sections** because:
- Each section needs ~4 language periods/week × 3 languages = 12 slots
- Teachers also need buffer periods
- Scheduling conflicts multiply when same triplet serves multiple sections

### Safe Formula:
$$\text{Language Triplets Required} \geq \left\lceil \frac{C_{lb}}{3} \right\rceil$$

**Our Sample:**
- 10 sections with language blocks
- $\lceil 10/3 \rceil = 4$ triplets needed
- **We have 4 triplets:**
  - Set 1: T016, T019, T022 → 6A, 6B (2 sections)
  - Set 2: T017, T020, T023 → 7A, 7B (2 sections)
  - Set 3: T018, T021, T024 → 8A, 8B (2 sections)
  - Set 4: T033, T034, T035 → 9A, 9B, 10A, 10B (4 sections)

---

## Formula 4: Class Teacher Period 1 Constraint

If every class must have their class teacher in period 1 every day:

$$\text{Class Teachers Required} \geq C$$

Each class needs a **unique class teacher** who is:
1. Available period 1 every day
2. Not teaching other classes in period 1

**Implication:** You need at least $C$ teachers who can serve as class teachers.

---

## Formula 5: Lab Resource Constraints

For subjects requiring shared resources (labs):

$$\text{Max Simultaneous Lab Classes} \leq \text{Lab Capacity}$$

If 6 classes have physics lab and capacity is 2:
- Lab periods must be distributed across at least $\lceil 6 \times 2 / 2 \rceil = 6$ different time slots
- Can't schedule more than 2 physics labs at same time

---

## Summary: Recommended Teacher Count by Subject

| Subject | Formula | For 10 Classes |
|---------|---------|----------------|
| Math | $\max(4, \lceil C/3 \rceil)$ | 4 teachers |
| Science | $\max(4, \lceil C/3 \rceil)$ | 4 teachers |
| English | $\max(4, \lceil C/3 \rceil)$ | 4 teachers |
| SST | $\max(3, \lceil C/4 \rceil)$ | 3 teachers |
| Hindi | $\lceil C_{lb}/3 \rceil$ | 4 teachers* |
| Kannada | $\lceil C_{lb}/3 \rceil$ | 4 teachers* |
| Sanskrit | $\lceil C_{lb}/3 \rceil$ | 4 teachers* |
| PE | $\lceil C/4 \rceil$ | 3 teachers |
| Computer | $\lceil C/4 \rceil$ | 3 teachers |
| Art | $\lceil C/5 \rceil$ | 2 teachers |

*Language teachers work in **synchronized triplets** due to language block constraint

---

## Final Recommendation

For **10 classes** with **ALL constraints enabled**:

| Category | Teachers | IDs |
|----------|----------|-----|
| Math | 4 | T001-T004 |
| Science | 4 | T005-T008 |
| English | 4 | T009-T012 |
| SST | 3 | T013-T015 |
| Hindi | 4 | T016-T018, T033 |
| Kannada | 4 | T019-T021, T034 |
| Sanskrit | 4 | T022-T024, T035 |
| PE | 3 | T025-T027 |
| Computer | 3 | T028-T030 |
| Art | 2 | T031-T032 |
| **TOTAL** | **35** | |

---

## Quick Reference Card

```
┌────────────────────────────────────────────────────────────────┐
│               TIMETABLE FEASIBILITY CHECK                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. TOTAL PERIODS CHECK                                        │
│     Required: Σ(C × periods_per_subject)                       │
│     Available: Σ(teachers × max_periods_per_week)              │
│     ✓ Available ≥ Required × 1.2 (20% buffer)                  │
│                                                                │
│  2. LANGUAGE BLOCK CHECK                                       │
│     Language Triplets ≥ ⌈sections_with_lang_block / 3⌉        │
│     Each triplet serves at most 3-4 sections                   │
│                                                                │
│  3. CLASS TEACHER CHECK                                        │
│     Unique class teachers ≥ Number of classes                  │
│     Class teacher must not conflict period 1                   │
│                                                                │
│  4. RESOURCE CHECK                                             │
│     Simultaneous resource use ≤ Resource capacity              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Scaling Guide

| Classes | Math | Sci | Eng | SST | Hindi | Kannada | Sanskrit | PE | Comp | Art | **Total** |
|---------|------|-----|-----|-----|-------|---------|----------|----|----- |-----|-----------|
| 6 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 1 | **19** |
| 10 | 4 | 4 | 4 | 3 | 4 | 4 | 4 | 3 | 3 | 2 | **35** |
| 15 | 5 | 5 | 5 | 4 | 5 | 5 | 5 | 4 | 4 | 3 | **45** |
| 20 | 7 | 7 | 7 | 5 | 7 | 7 | 7 | 5 | 5 | 4 | **61** |
| 30 | 10 | 10 | 10 | 8 | 10 | 10 | 10 | 8 | 8 | 6 | **90** |
