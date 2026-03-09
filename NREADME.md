# VIT SY AI Timetable Generator
**CSE (AI&ML) · A.Y. 2025-26 · DFS + Backtracking CSP**

## Quick Start

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
prisma generate
prisma db push
uvicorn app.main:app --reload --port 8000
```

### 2. Set Environment Variable
Create `backend/.env`:
```
DATABASE_URL="postgresql://user:password@host/dbname?sslmode=require"
```

### 3. Frontend
Open `frontend/index.html` in browser (or serve it).

### 4. Usage
1. Click **⚡ Seed DB** — populates all teachers, subjects, rooms, timeslots, divisions, batches
2. Click **✦ Generate Timetable** — runs DFS scheduler, saves to DB
3. Browse timetables by Division / Batch / Teacher / Room

---

## Architecture

```
backend/
├── app/
│   ├── main.py                  # FastAPI app + /generate-timetable
│   ├── database/
│   │   ├── prisma.py            # Prisma client
│   │   └── seed.py              # Full SY data seed
│   ├── models/
│   │   └── session.py           # Session object
│   ├── routes/
│   │   ├── timetable.py         # GET /timetable/{teacher,room,division,batch}
│   │   ├── teachers.py
│   │   ├── rooms.py
│   │   ├── subjects.py
│   │   └── timeslots.py
│   └── services/
│       └── scheduler.py         # DFS + Backtracking CSP
├── prisma/
│   └── schema.prisma
└── requirements.txt

frontend/
└── index.html                   # Full SPA — no build required
```

---

## Subjects (SY)

| Code   | Subject                           | Theory | Lab | Tut | Type    |
|--------|-----------------------------------|--------|-----|-----|---------|
| AI     | Artificial Intelligence           | 2      | 2   | 0   | Core    |
| OS     | Operating System                  | 2      | 2   | 0   | Core    |
| ADS    | Advanced Data Structure           | 2      | 2   | 0   | Core    |
| POCACD | Automata Theory & Compiler Design | 2      | 2   | 0   | Core    |
| RAAD   | Reasoning & Aptitude Development  | 2      | 0   | 0   | Core    |
| FCTC   | From Campus to Corporate          | 1      | 0   | 0   | Core    |
| DT     | Design Thinking                   | 0      | 0   | 1   | Core    |
| DV     | Data Visualization                | 2      | 0   | 1   | Elective|
| IOT    | Internet of Things                | 2      | 0   | 1   | Elective|

---

## AI Constraints Solved

- **No teacher double-booking** — global teacher×slot uniqueness
- **No room double-booking** — global room×slot uniqueness  
- **No division double-booking** — division×slot uniqueness
- **Theory same-subject once/day** — per division, per subject, per day
- **Labs = 2 consecutive slots** — bridging lunch is prevented
- **Labs = parallel batches** — all 3 batches get lab at same time, different rooms/teachers
- **Lunch slots reserved** — 12:00-13:00 and 13:00-14:00 not scheduled

---

## Faculty

| Code | Name                          | Subjects           |
|------|-------------------------------|---------------------|
| ASK  | Mr. Ankesh Suresh Khare       | AI(T), RAAD(T), DT(Tut) |
| KS   | Dr. Kailash Shaw              | ADS(T), ADS(L)      |
| RAA  | Rashmi Aniket Asole           | ADS(L)              |
| VUR  | Dr. Vijay Uttam Rathod        | POCACD(T,L), DT(Tut)|
| VSB  | Mrs. Vanita Sharad Babanne    | AI(L)               |
| ABK  | Ms. Asmita Balasaheb Kalamkar | FCTC(T)             |
| GZZ  | Ms. Geeta Balkrushna Zaware   | OS(L), DT(Tut)      |
| AGS  | Ms. Ashlesha Gopinath Sawant  | OS(T,L)             |
| DAG  | Mrs. Dipti Ajitkumar Gaikwad  | AI(L), DV(Tut)      |
| OSD  | Omkar Shailendra Dubal        | OS(L)               |
| ACA  | Dr. Amruta Chandrakant Amune  | OS(L)               |
| KG   | Dr. Kalyani Ghughe            | DV(T,Tut)           |
| VKS  | Mr. Vivekanand Sharma         | IOT(T,Tut)          |