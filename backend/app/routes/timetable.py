from fastapi import APIRouter
from app.database.prisma import db

router = APIRouter()


@router.get("/timetable/teacher/{code}")
async def teacher_timetable(code: str):

    teacher = await db.teacher.find_first(
        where={"shortCode": code}
    )

    entries = await db.timetableentry.find_many(
        where={"teacherId": teacher.id},
        include={
            "subject": True,
            "room": True,
            "timeslot": True
        }
    )

    return entries

@router.get("/timetable/room/{room}")
async def room_timetable(room: str):

    r = await db.room.find_first(
        where={"roomNumber": room}
    )

    entries = await db.timetableentry.find_many(
        where={"roomId": r.id},
        include={
            "subject": True,
            "teacher": True,
            "timeslot": True
        }
    )

    return entries

@router.get("/timetable/division/{division}")
async def division_timetable(division: str):

    div = await db.division.find_first(
        where={"name": division}
    )

    if not div:
        return {"error": "Division not found"}

    entries = await db.timetableentry.find_many(
        where={"divisionId": div.id},
        include={
            "subject": True,
            "teacher": True,
            "room": True,
            "timeslot": True
        }
    )

    return entries

@router.get("/timetable/batch/{batch}")
async def batch_timetable(batch: str):

    b = await db.batch.find_first(
        where={"name": batch}
    )

    if not b:
        return {"error": "Batch not found"}

    entries = await db.timetableentry.find_many(
        where={"batchId": b.id},
        include={
            "subject": True,
            "teacher": True,
            "room": True,
            "timeslot": True
        }
    )

    return entries