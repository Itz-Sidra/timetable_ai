from fastapi import APIRouter
from app.database.prisma import db

router = APIRouter()

@router.get("/timeslots")
async def get_timeslots():
    return await db.timeslot.find_many()