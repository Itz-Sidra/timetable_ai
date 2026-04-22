import asyncio
from app.database.prisma import db

DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
SLOTS = [
    (800,  900), (900,  1000), (1000, 1100), (1100, 1200),
    (1200, 1300), (1300, 1400),
    (1400, 1500), (1500, 1600), (1600, 1700),
]

SY_DIVISIONS = [
    ("A", "MORNING"),
    ("B", "MORNING"),
    ("C", "MORNING"),
    ("D", "MORNING"),
    ("E", "AFTERNOON"),
    ("F", "AFTERNOON"),
]

TY_DIVISIONS = [
    ("A", "AFTERNOON"),
    ("B", "AFTERNOON"),
]


async def seed():
    # Timeslots
    for day in DAYS:
        for (st, en) in SLOTS:
            await db.timeslot.create(data={"day": day, "startTime": st, "endTime": en})
    print(f"  Timeslots: {len(DAYS) * len(SLOTS)}")

    # SY year + divisions
    sy = await db.year.create(data={"name": "SY"})
    for div_name, tw in SY_DIVISIONS:
        div = await db.division.create(data={
            "name": div_name,
            "timeWindow": tw,
            "year": {"connect": {"id": sy.id}},
        })
        for n in [1, 2, 3]:
            await db.batch.create(data={
                "name": f"{div_name}-B{n}",
                "division": {"connect": {"id": div.id}},
            })
        print(f"  SY Division {div_name} ({tw})  Batches: 3")

    # TY year + divisions
    ty = await db.year.create(data={"name": "TY"})
    for div_name, tw in TY_DIVISIONS:
        div = await db.division.create(data={
            "name": div_name,
            "timeWindow": tw,
            "year": {"connect": {"id": ty.id}},
        })
        for n in [1, 2, 3]:
            await db.batch.create(data={
                "name": f"{div_name}-B{n}",
                "division": {"connect": {"id": div.id}},
            })
        print(f"  TY Division {div_name} ({tw})  Batches: 3")

    print("✅ Seed complete")


if __name__ == "__main__":
    async def main():
        await db.connect()
        await seed()
        await db.disconnect()
    asyncio.run(main())