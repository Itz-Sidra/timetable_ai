from fastapi import FastAPI
from app.database.prisma import db
from app.services.scheduler import generate_timetable
from app.routes.timetable import router as timetable_router

app = FastAPI()
app.include_router(timetable_router)


@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


@app.post("/generate-timetable")
async def generate():

    # ------------------------------------------------------------------ load
    teachers = await db.teacher.find_many()
    subjects = await db.subject.find_many()
    rooms    = await db.room.find_many()
    slots    = await db.timeslot.find_many()
    batches  = await db.batch.find_many(where={"divisionId": 1})

    data = {
        "teachers":  teachers,
        "subjects":  subjects,
        "rooms":     rooms,
        "timeslots": slots,
        "batches":   batches,
    }

    state = generate_timetable(data)

    if state is None:
        return {"error": "No valid timetable found — add more rooms or timeslots"}

    # ---------------------------------------------------------------- clear
    await db.timetableentry.delete_many()

    # ------------------------------------------------- lookup maps
    subject_map = {s.name: s for s in subjects}
    teacher_map = {t.name: t for t in teachers}
    room_map    = {r.roomNumber: r for r in rooms}

    # Dedup guards — mirror the DB unique constraints in memory so we never
    # attempt a duplicate insert.
    used_teacher_slot: set[tuple] = set()
    used_room_slot:    set[tuple] = set()

    # ---------------------------------------------------------- save
    # state is a flat list of Session objects.
    # - THEORY / TUTORIAL sessions: have teacher, room, timeslot set.
    # - LAB original sessions:       have batch_assignments set (non-empty list).
    # - LAB sentinel sessions:       batch_assignments == [] — skip entirely.

    for s in state:

        # ---------------------------------------- skip LAB sentinels
        if s.lecture_type == "LAB" and not s.batch_assignments:
            continue

        subject = subject_map.get(s.subject)
        if not subject:
            continue

        # ---------------------------------------- THEORY / TUTORIAL
        if s.lecture_type in ("THEORY", "TUTORIAL"):

            teacher = teacher_map.get(s.teacher)
            room    = room_map.get(s.room)
            if not teacher or not room:
                continue

            key_t = (teacher.id, s.timeslot)
            key_r = (room.id,    s.timeslot)
            if key_t in used_teacher_slot or key_r in used_room_slot:
                continue   # duplicate guard

            await db.timetableentry.create(
                data={
                    "divisionId":  1,
                    "batchId":     None,          # division-wide, no batch
                    "subjectId":   subject.id,
                    "teacherId":   teacher.id,
                    "roomId":      room.id,
                    "timeslotId":  s.timeslot,
                    "lectureType": s.lecture_type,
                }
            )
            used_teacher_slot.add(key_t)
            used_room_slot.add(key_r)

        # ---------------------------------------- LAB (original session)
        elif s.lecture_type == "LAB":

            # batch_assignments is a list with one entry per batch:
            # { teacher, room, slot_id, next_slot_id, slot_day }
            for i, bc in enumerate(s.batch_assignments):

                teacher = teacher_map.get(bc["teacher"])
                room    = room_map.get(bc["room"])
                batch   = batches[i] if i < len(batches) else None

                if not teacher or not room or not batch:
                    continue

                # Insert one row per consecutive slot for this batch
                for slot_id in (bc["slot_id"], bc["next_slot_id"]):

                    key_t = (teacher.id, slot_id)
                    key_r = (room.id,    slot_id)

                    if key_t in used_teacher_slot or key_r in used_room_slot:
                        continue   # should never happen with a correct scheduler

                    await db.timetableentry.create(
                        data={
                            "divisionId":  1,
                            "batchId":     batch.id,   # ← batch-specific
                            "subjectId":   subject.id,
                            "teacherId":   teacher.id,
                            "roomId":      room.id,
                            "timeslotId":  slot_id,
                            "lectureType": "LAB",
                        }
                    )
                    used_teacher_slot.add(key_t)
                    used_room_slot.add(key_r)

    return {"message": "Timetable generated and saved"}