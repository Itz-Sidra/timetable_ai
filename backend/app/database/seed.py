from app.database.prisma import db


async def seed():

    # Teachers
    await db.teacher.upsert(
        where={"shortCode": "ASK"},
        data={
            "create": {"name": "ASK", "shortCode": "ASK"},
            "update": {}
        }
    )

    await db.teacher.upsert(
        where={"shortCode": "AGS"},
        data={
            "create": {"name": "AGS", "shortCode": "AGS"},
            "update": {}
        }
    )

    # Subjects
    await db.subject.upsert(
        where={"code": "AI"},
        data={
            "create": {
                "name": "Artificial Intelligence",
                "code": "AI",
                "theoryHours": 2,
                "labHours": 2,
                "tutHours": 0
            },
            "update": {}
        }
    )

    await db.subject.upsert(
        where={"code": "OS"},
        data={
            "create": {
                "name": "Operating Systems",
                "code": "OS",
                "theoryHours": 2,
                "labHours": 2,
                "tutHours": 0
            },
            "update": {}
        }
    )

    # Rooms
    await db.room.upsert(
        where={"roomNumber": "4005"},
        data={
            "create": {"roomNumber": "4005", "roomType": "THEORY"},
            "update": {}
        }
    )

    await db.room.upsert(
        where={"roomNumber": "4304"},
        data={
            "create": {"roomNumber": "4304", "roomType": "LAB"},
            "update": {}
        }
    )

    # Timeslots
    await db.timeslot.create(
        data={
            "day": "MONDAY",
            "startTime": "08:00",
            "endTime": "09:00"
        }
    )

    await db.timeslot.create(
        data={
            "day": "MONDAY",
            "startTime": "09:00",
            "endTime": "10:00"
        }
    )