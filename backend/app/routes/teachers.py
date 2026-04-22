from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.database.prisma import db

router = APIRouter()


class TeacherCreate(BaseModel):
    name: str
    shortCode: str
    subjectIds: List[int] = []
    lectureTypes: List[str] = []


@router.get("/teachers")
async def get_teachers():
    return await db.teacher.find_many(
        include={"subjects": {"include": {"subject": True}}}
    )


@router.post("/teachers")
async def create_teacher(payload: TeacherCreate):
    existing = await db.teacher.find_first(where={"shortCode": payload.shortCode})
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Teacher code '{payload.shortCode}' already exists."
        )

    teacher = await db.teacher.create(data={
        "name":      payload.name,
        "shortCode": payload.shortCode,
    })

    for subject_id in payload.subjectIds:
        for lecture_type in payload.lectureTypes:
            try:
                await db.teachersubject.create(data={
                    "lectureType": lecture_type,
                    "teacher": {"connect": {"id": teacher.id}},
                    "subject": {"connect": {"id": subject_id}},
                })
            except Exception:
                pass  # skip duplicates

    return teacher