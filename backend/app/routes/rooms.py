from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database.prisma import db

router = APIRouter()


class RoomCreate(BaseModel):
    roomNumber: str
    roomType: str
    capacity: Optional[int] = None


@router.get("/rooms")
async def get_rooms():
    return await db.room.find_many()


@router.post("/rooms")
async def create_room(payload: RoomCreate):
    if payload.roomType not in ("THEORY", "LAB"):
        raise HTTPException(status_code=400, detail="roomType must be THEORY or LAB.")

    existing = await db.room.find_first(where={"roomNumber": payload.roomNumber})
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Room '{payload.roomNumber}' already exists."
        )

    data = {
        "roomNumber": payload.roomNumber,
        "roomType":   payload.roomType,
    }
    if payload.capacity is not None:
        data["capacity"] = payload.capacity

    return await db.room.create(data=data)