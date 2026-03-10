from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.prisma import db
from app.services.scheduler import generate_timetable
from app.routes.timetable import router as timetable_router
from app.routes.teachers import router as teachers_router
from app.routes.rooms import router as rooms_router
from app.routes.subjects import router as subjects_router
from app.routes.timeslots import router as timeslots_router
from app.database.seed import seed

app = FastAPI(title="AI Timetable Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(timetable_router)
app.include_router(teachers_router)
app.include_router(rooms_router)
app.include_router(subjects_router)
app.include_router(timeslots_router)


@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


@app.post("/seed")
async def run_seed():
    await seed()
    return {"message": "Database seeded"}


@app.post("/generate-timetable")
async def generate():
    year = await db.year.find_first(where={"name": "SY"})
    if not year:
        return {"error": "Run /seed first"}

    teachers            = await db.teacher.find_many()
    subjects            = await db.subject.find_many(where={"yearId": year.id})
    rooms               = await db.room.find_many()
    slots               = await db.timeslot.find_many(order=[{"day": "asc"}, {"startTime": "asc"}])
    divisions           = await db.division.find_many(where={"yearId": year.id})
    batches             = await db.batch.find_many()
    teacher_assignments = await db.teachersubject.find_many()

    data = {
        "teachers":            teachers,
        "subjects":            subjects,
        "rooms":               rooms,
        "timeslots":           slots,
        "divisions":           divisions,
        "batches":             batches,
        "teacher_assignments": teacher_assignments,
    }

    sessions = generate_timetable(data)

    if sessions is None:
        return {"error": "No valid timetable found — constraints too tight"}

    print("Reconnecting to DB before save...", flush=True)
    try:
        await db.disconnect()
    except Exception:
        pass
    await db.connect()

    await db.timetableentry.delete_many()

    subject_map = {s.code: s for s in subjects}
    room_map    = {r.roomNumber: r for r in rooms}
    batches_by_div = {}
    for b in batches:
        batches_by_div.setdefault(b.divisionId, []).append(b)

    saved  = 0
    errors = 0

    for s in sessions:
        subj = subject_map.get(s.subject_code)
        if not subj:
            continue

        if s.lecture_type == "THEORY":
            if not s.teacher_id or not s.room_id or not s.timeslot:
                continue
            try:
                await db.timetableentry.create(data={
                    "divisionId":  s.division_id,
                    "subjectId":   subj.id,
                    "teacherId":   s.teacher_id,
                    "roomId":      s.room_id,
                    "timeslotId":  s.timeslot,
                    "lectureType": "THEORY",
                })
                saved += 1
            except Exception as e:
                errors += 1
                print(f"Skip THEORY {s.subject_code}: {e}")

        elif s.lecture_type == "TUTORIAL":
            if not s.teacher_id or not s.room_id or not s.timeslot:
                continue
            bidx = getattr(s, "batch_index", None)
            if bidx is not None:
                batch_obj = div_batches[bidx] if bidx < len(div_batches) else None
                batch_id = batch_obj.id if batch_obj else None
            else:
                batch_id = getattr(s, "_batch_id", None)
            try:
                await db.timetableentry.create(data={
                    "divisionId":  s.division_id,
                    "batchId":     batch_id,
                    "subjectId":   subj.id,
                    "teacherId":   s.teacher_id,
                    "roomId":      s.room_id,
                    "timeslotId":  s.timeslot,
                    "lectureType": "TUTORIAL",
                })
                saved += 1
            except Exception as e:
                errors += 1
                print(f"Skip TUTORIAL {s.subject_code}: {e}")

        elif s.lecture_type == "LAB" and s.batch_assignments:
            div_batches = batches_by_div.get(s.division_id, [])
            batch_idx   = getattr(s, "batch_index", 0)
            batch       = div_batches[batch_idx] if batch_idx < len(div_batches) else None
            if not batch:
                print(f"Skip LAB {s.subject_code}: no batch at index {batch_idx}")
                continue

            bc   = s.batch_assignments[0]
            room = room_map.get(bc["room"])
            if not room:
                print(f"Skip LAB {s.subject_code}: room {bc['room']} not found")
                continue

            for slot_id in (bc["slot_id"], bc["next_slot_id"]):
                try:
                    await db.timetableentry.create(data={
                        "divisionId":  s.division_id,
                        "batchId":     batch.id,
                        "subjectId":   subj.id,
                        "teacherId":   bc["teacher_id"],
                        "roomId":      room.id,
                        "timeslotId":  slot_id,
                        "lectureType": "LAB",
                    })
                    saved += 1
                except Exception as e:
                    errors += 1
                    print(f"Skip LAB slot {s.subject_code}: {e}")

    print(f"  Saved: {saved}  Errors: {errors}")
    return {"message": f"Timetable generated — {saved} entries saved ({errors} skipped)"}