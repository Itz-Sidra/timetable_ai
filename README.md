# AI-Based University Timetable Generator

An intelligent system that automatically generates a **conflict-free university timetable** using **AI constraint solving i.e DFS + Backtracking**.

The system schedules:

- Subjects
- Teachers
- Rooms
- Timeslots
- Divisions
- Batches

while satisfying real-world constraints like **teacher availability, room conflicts, lab sessions, and batch splits**.

The backend exposes APIs using **FastAPI**, stores data in **PostgreSQL (Neon)**, and uses **Prisma ORM** for database interaction.

---

# Project Objective

Universities typically create timetables manually, which is:

- Time consuming
- Error prone
- Difficult to optimize

This project solves that problem by using **AI search algorithms** to automatically generate a **valid timetable satisfying all constraints**.

The system ensures:

- No teacher conflicts
- No room conflicts
- Labs run for correct duration
- Theory lectures distributed across week
- Batches handled correctly
- Division wide lectures handled correctly

---

# Technology Stack

## Frontend

- HTML
- CSS
- JS

## Backend

- Python
- FastAPI

## Database

- PostgreSQL (Neon)
- Prisma ORM (prisma-client-py)

## AI / Algorithm

- Depth First Search
- Backtracking
- Constraint satisfaction

---

# AI Timetable Generation Logic

The timetable is generated using **Constraint Satisfaction Problem (CSP)** techniques.

The system builds sessions and tries assigning:

```

teacher
room
timeslot

```

to each session.

If a constraint is violated, the algorithm **backtracks and tries another possibility**.

---

# AI Implemented

## 1. Session Expansion

Subjects are expanded into sessions based on their hours.

Example:

| Subject | Theory | Lab | Tutorial |
|-------|------|------|------|
| AI | 2 | 2 | 0 |

Expansion:

```

AI THEORY
AI THEORY
AI LAB (2 slots)

```

Electives generate:

```

THEORY
TUTORIAL

```

---

## 2. DFS Search

The scheduler uses **Depth First Search** to assign sessions sequentially.

For each session it tries:

```

teacher
room
timeslot

```

If valid:

```

add to state
continue scheduling

```

If invalid:

```

backtrack
try next option

```

---

## 3. Backtracking

If the algorithm reaches a dead end:

```

undo previous assignment
try another possibility

```

This guarantees a **conflict-free timetable**.

---

# Scheduling Constraints

The timetable must satisfy the following rules.

---

# Teacher Constraints

A teacher **cannot teach two lectures at the same time**.

Database enforcement:

```

@@unique([teacherId, timeslotId])

```

---

# Room Constraints

A room **cannot host two lectures simultaneously**.

Database enforcement:

```

@@unique([roomId, timeslotId])

```

---

# Theory Lecture Constraints

Theory lectures:

- Are **division wide**
- All batches attend together
- Cannot repeat **same subject twice in same day**

Example:

```

Division A
AI Theory
Monday 10:00

```

---

# Lab Constraints

Labs must satisfy:

- Duration = **2 consecutive slots**
- Occur **per batch**
- All batches have labs **at same time**

Example:

| Batch | Subject | Room |
|------|------|------|
| B1 | AI | 4304 |
| B2 | OS | 4007 |
| B3 | ADS | 4008 |

Time:

```

Monday 08:00 - 10:00

```

---

# Tutorial Constraints

Elective subjects may have tutorials instead of labs.

Tutorials behave similar to lab sessions but each batch has 1 hour tutorial, and they are conducted in theory rooms.

| Batch | Subject | Room |
|------|------|------|
| B1 | DV Tut | 4307 |
| B2 | DV Tut | 4005 |
| B3 | DV Tut | 4006 |

---

# Timeslot Constraints

Timeslots exist for:

```

Monday
Tuesday
Wednesday
Thursday
Friday

```

Each day contains:

```

08:00 - 09:00
09:00 - 10:00
10:00 - 11:00
11:00 - 12:00
12:00 - 14:00 (1 hour lunch break either at 12:00-13:00 or 13:00-14:00)
14:00 - 15:00
15:00 - 16:00
16:00 - 17:00
17:00 - 18:00

```

---

# Database Schema

The system stores timetable information using relational models.

---

# Core Tables

## Year

Represents academic year.

Example:

```

SY

```

---

## Division

Each year contains divisions.

Example:

```

A
B
C
D
E
F
SEDA

```

---

## Batch

Each division is split into batches.

Example:

```

A-B1
A-B2
A-B3

```

Batches are used for **lab sessions**.

---

## Teacher

Stores faculty information.

Example:

```

ASK
AGS
KS
RAA
VUR

```

---

## Subject

Stores subject details.

Example:

```

Artificial Intelligence
Operating System
Advanced Data Structure
Automata Theory
Data Visualization

```

Attributes:

```

theoryHours
labHours
tutHours
electiveGroupId

```

---

## Room

Two types of rooms exist.

```

THEORY rooms
LAB rooms

```

```

THEORY/TUTORIAL ROOMS
4307
4006
4005

LAB ROOMS
4304
4007
4008
4003
4105
```

---

## TimeSlot

Represents lecture timing.

Fields:

```

day
startTime
endTime

```

---

## TimetableEntry

Stores final timetable schedule.

Fields:

```

divisionId
batchId
subjectId
teacherId
roomId
timeslotId
lectureType

```

---

# API Endpoints

The backend exposes REST APIs to retrieve schedules.

---

# Generate Timetable

```

POST /generate-timetable

```

Runs the AI scheduler and saves results to database.

---

# Teacher Page

```

GET /timetable/teacher/{code}

```

Example:

```

/timetable/teacher/ASK

```

Displays all lectures assigned to a teacher.

---

# Room Page

```

GET /timetable/room/{room}

```

Example:

```

/timetable/room/4005

```

Shows schedule for a room.

---

# Division Page

```

GET /timetable/division/{division}

```

Example:

```

/timetable/division/A

```

Shows timetable for entire division.

---

# Batch Page

```

GET /timetable/batch/{batch}

```

Example:

```

/timetable/batch/A-B1

```

Shows lab sessions for a specific batch.

---

# Student Page

Students can view timetable based on:

```

division
batch

```

Example:

```

A-B1 timetable

```

Shows:

- Theory lectures (division wide)
- Lab sessions (batch specific)

---

# Room Page

Room page allows checking:

```

which lectures are scheduled
when room is occupied

```

Helps administration avoid room clashes.

---

# Teacher Page

Teacher page shows:

```

weekly teaching schedule
assigned subjects
assigned rooms

```

---

# Example Generated Timetable

Division A

| Day | 8-9 | 9-10 | 10-11 | 11-12 |
|----|----|----|----|----|
| Mon | AI Lab | AI Lab | OS | TOC |
| Tue | Free | Free | AI | Free |

---

Batch B1

| Day | 8-9 | 9-10 |
|----|----|----|
| Mon | AI Lab | AI Lab |

---

Batch B2

| Day | 8-9 | 9-10 |
|----|----|----|
| Mon | OS Lab | OS Lab |

---

Batch B3

| Day | 8-9 | 9-10 |
|----|----|----|
| Mon | ADS Lab | ADS Lab |

---

# Key Features

- Automatic timetable generation
- AI based constraint solving
- Conflict free scheduling
- Batch level lab management
- REST APIs for timetable queries
- Scalable database design
- Real world academic constraints

---

# Future Improvements

Possible future extensions:

- Genetic algorithm scheduling
- Teacher preference optimization
- Holiday handling
- GUI timetable viewer
- Drag and drop rescheduling
- Multi department scheduling
