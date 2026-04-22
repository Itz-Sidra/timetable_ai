from fastapi import APIRouter
from app.database.prisma import db

router = APIRouter()

INCLUDE_ALL = {
    "subject":  True,
    "teacher":  True,
    "room":     True,
    "timeslot": True,
    "batch":    True,
}


@router.get("/divisions/all")
async def get_all_divisions():
    return await db.division.find_many(
        include={"year": True},
        order=[{"year": {"name": "asc"}}, {"name": "asc"}]
    )


@router.get("/timetable/teacher/{code}")
async def teacher_timetable(code: str):
    teacher = await db.teacher.find_first(where={"shortCode": code})
    if not teacher:
        return {"error": "Teacher not found"}
    return await db.timetableentry.find_many(
        where={"teacherId": teacher.id},
        include=INCLUDE_ALL
    )


@router.get("/timetable/room/{room}")
async def room_timetable(room: str):
    r = await db.room.find_first(where={"roomNumber": room})
    if not r:
        return {"error": "Room not found"}
    return await db.timetableentry.find_many(
        where={"roomId": r.id},
        include=INCLUDE_ALL
    )


# ── Division timetable — requires year + division name to avoid ambiguity ──
@router.get("/timetable/division/{year_name}/{div_name}")
async def division_timetable(year_name: str, div_name: str):
    year = await db.year.find_first(where={"name": year_name.upper()})
    if not year:
        return {"error": f"Year '{year_name}' not found"}

    div = await db.division.find_first(where={
        "name":   div_name.upper(),
        "yearId": year.id,
    })
    if not div:
        return {"error": f"Division '{div_name}' not found in year '{year_name}'"}

    return await db.timetableentry.find_many(
        where={"divisionId": div.id},
        include=INCLUDE_ALL
    )


@router.get("/timetable/batch/{batch}")
async def batch_timetable(batch: str):
    b = await db.batch.find_first(where={"name": batch})
    if not b:
        return {"error": "Batch not found"}

    div_entries = await db.timetableentry.find_many(
        where={
            "divisionId": b.divisionId,
            "batchId":    {"equals": None},
            "lectureType": "THEORY",
        },
        include=INCLUDE_ALL
    )
    lab_entries = await db.timetableentry.find_many(
        where={"batchId": b.id},
        include=INCLUDE_ALL
    )
    tut_entries = await db.timetableentry.find_many(
        where={
            "divisionId": b.divisionId,
            "batchId":    {"equals": None},
            "lectureType": "TUTORIAL",
        },
        include=INCLUDE_ALL
    )
    return div_entries + lab_entries + tut_entries


# ── Batches — requires year + division name to avoid ambiguity ──
@router.get("/batches/{year_name}/{div_name}")
async def get_batches(year_name: str, div_name: str):
    year = await db.year.find_first(where={"name": year_name.upper()})
    if not year:
        return []
    div = await db.division.find_first(where={
        "name":   div_name.upper(),
        "yearId": year.id,
    })
    if not div:
        return []
    return await db.batch.find_many(where={"divisionId": div.id})


@router.get("/divisions")
async def get_divisions():
    year = await db.year.find_first(where={"name": "SY"})
    if not year:
        return []
    return await db.division.find_many(where={"yearId": year.id})