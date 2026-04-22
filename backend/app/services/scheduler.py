"""
Fixed scheduler.py

Bugs fixed:
1. Theory was only allowed in 10:00-13:00 range, starving later divisions (C, D...) of rooms.
   Fix: Use the FULL time window for theory (08:00-13:00 for MORNING, 10:00-18:00 for AFTERNOON).

2. assign_theory did NOT check batch_slot, so theory was scheduled at the same time as a
   lab session for some batches of the same division.
   Fix: Block any slot where ANY batch of that division already has a lab/tutorial.

3. With 6+ divisions all competing for theory rooms in the 10:00-12:00 window,
   later divisions (C, D ...) ran out of rooms.
   Fix: Expand the allowed theory window to the full time window (fix #1 above).

4. Time window boundaries corrected:
   MORNING:   08:00 - 14:00  (startTime 800  ..< 1400, excluding 1300 lunch)
   AFTERNOON: 10:00 - 18:00  (startTime 1000 ..< 1800, excluding 1300 lunch)
"""

from collections import defaultdict
from app.models.session import Session

LUNCH        = {1300}
LAB_SUBJECTS = ["ADS", "POCACD", "AI", "OS"]
DAYS         = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]

# Each batch index rotates which subject it has in lab on each day
BATCH_LAB_ROTATION = {
    0: {"MONDAY": "ADS",    "TUESDAY": "POCACD", "WEDNESDAY": "AI",  "THURSDAY": "OS"},
    1: {"MONDAY": "POCACD", "TUESDAY": "AI",     "WEDNESDAY": "OS",  "THURSDAY": "ADS"},
    2: {"MONDAY": "AI",     "TUESDAY": "OS",     "WEDNESDAY": "ADS", "THURSDAY": "POCACD"},
}


def expand_sessions(subjects, division, batches):
    subj = {s.code: s for s in subjects}
    sessions = []

    for code in ["AI", "OS", "ADS", "POCACD", "RAAD", "FCTC", "DV"]:
        s = subj.get(code)
        if not s or s.theoryHours == 0:
            continue
        for _ in range(s.theoryHours):
            sessions.append(Session(
                s.code, s.name, "THEORY", 1,
                division_id=division.id,
                elective_group_id=getattr(s, 'electiveGroupId', None)
            ))

    for bidx, batch in enumerate(batches):
        rotation = BATCH_LAB_ROTATION.get(bidx, {})
        for day, lab_code in rotation.items():
            s = subj.get(lab_code)
            if not s or s.labHours == 0:
                continue
            sess = Session(s.code, s.name, "LAB", 2,
                           division_id=division.id, elective_group_id=None)
            sess.batch_index  = bidx
            sess.assigned_day = day
            sessions.append(sess)

    dt = subj.get("DT")
    if dt and dt.tutHours > 0:
        for bidx in range(len(batches)):
            sess = Session(dt.code, dt.name, "TUTORIAL", 1,
                           division_id=division.id, elective_group_id=None)
            sess.batch_index = bidx
            sess.tut_subj    = "DT"
            sessions.append(sess)

    dv = subj.get("DV")
    if dv and dv.tutHours > 0:
        for bidx in range(len(batches)):
            sess = Session(dv.code, dv.name, "TUTORIAL", 1,
                           division_id=division.id,
                           elective_group_id=getattr(dv, 'electiveGroupId', None))
            sess.batch_index = bidx
            sess.tut_subj    = "DV"
            sessions.append(sess)

    return sessions


def is_lunch(slot):
    return slot.startTime in LUNCH


def nxt(slot, by_day):
    day_slots = by_day.get(slot.day, [])
    idx = next((i for i, s in enumerate(day_slots) if s.id == slot.id), None)
    if idx is None or idx + 1 >= len(day_slots):
        return None
    n = day_slots[idx + 1]
    return None if n.startTime in LUNCH else n


def _try_assign_lab_group(group, div_batches, tlist, l_rooms,
                           day_slots, slots_by_day,
                           teacher_slot, room_slot, batch_slot):
    """
    Try every 2-consecutive-slot window in day_slots.
    Returns (slot, nslot, pending_list) on success, or None on failure.
    """
    for slot in day_slots:
        nslot = nxt(slot, slots_by_day)
        if not nslot or nslot.startTime in LUNCH:
            continue

        temp_teacher = set()
        temp_room    = set()
        temp_batch   = set()
        pending      = []
        slot_ok      = True

        for sess in group:
            bidx = sess.batch_index
            if bidx >= len(div_batches):
                slot_ok = False
                break
            batch = div_batches[bidx]

            if ((batch.id, slot.id) in batch_slot or
                    (batch.id, slot.id) in temp_batch):
                slot_ok = False
                break

            found_t = None
            found_r = None
            for t in tlist:
                if ((t.id, slot.id)  in teacher_slot or
                        (t.id, nslot.id) in teacher_slot or
                        (t.id, slot.id)  in temp_teacher  or
                        (t.id, nslot.id) in temp_teacher):
                    continue
                for r in l_rooms:
                    if ((r.id, slot.id)  in room_slot or
                            (r.id, nslot.id) in room_slot or
                            (r.id, slot.id)  in temp_room  or
                            (r.id, nslot.id) in temp_room):
                        continue
                    found_t = t
                    found_r = r
                    break
                if found_t:
                    break

            if not found_t:
                slot_ok = False
                break

            temp_teacher.add((found_t.id, slot.id))
            temp_teacher.add((found_t.id, nslot.id))
            temp_room.add((found_r.id, slot.id))
            temp_room.add((found_r.id, nslot.id))
            temp_batch.add((batch.id, slot.id))
            temp_batch.add((batch.id, nslot.id))
            pending.append((sess, batch, found_t, found_r))

        if slot_ok and len(pending) == len(group):
            return slot, nslot, pending

    return None


def assign_labs_per_division(lab_sessions, batches, ts_map, l_rooms,
                              division_slots, teacher_slot, room_slot, batch_slot):
    """
    Schedule labs division-by-division.
    All batches for a (subject, day) are placed atomically into the SAME slot
    with DIFFERENT rooms/teachers.
    """
    by_division = defaultdict(lambda: defaultdict(list))
    for sess in lab_sessions:
        by_division[sess.division_id][(sess.subject_code, sess.assigned_day)].append(sess)

    for division_id, groups in by_division.items():
        sbd         = division_slots.get(division_id, {})
        div_batches = [b for b in batches if b.divisionId == division_id]

        for (subj_code, day), group in groups.items():
            group.sort(key=lambda s: s.batch_index)
            tlist     = ts_map.get((subj_code, "LAB"), [])
            day_slots = sbd.get(day, [])

            result = _try_assign_lab_group(
                group, div_batches, tlist, l_rooms,
                day_slots, sbd,
                teacher_slot, room_slot, batch_slot
            )

            if result is None:
                codes = [f"B{s.batch_index+1}" for s in group]
                print(f"   LAB {subj_code} div={division_id} {codes} on {day} "
                      f"— unassigned (no valid slot)", flush=True)
                continue

            slot, nslot, pending = result
            for sess, batch, t, r in pending:
                for sid in (slot.id, nslot.id):
                    teacher_slot.add((t.id, sid))
                    room_slot.add((r.id, sid))
                    batch_slot.add((batch.id, sid))
                sess.teacher_id        = t.id
                sess.teacher           = t.shortCode
                sess.room_id           = r.id
                sess.room              = r.roomNumber
                sess.timeslot          = slot.id
                sess.timeslot_day      = slot.day
                sess.batch_assignments = [{
                    "teacher_id":   t.id,
                    "teacher":      t.shortCode,
                    "room_id":      r.id,
                    "room":         r.roomNumber,
                    "slots":        [slot.id, nslot.id],
                    "slot_id":      slot.id,
                    "next_slot_id": nslot.id,
                }]

            batch_labels = [f"B{s.batch_index+1}" for s in group]
            print(f"   LAB {subj_code} div={division_id} {batch_labels} on {day} "
                  f"@ {slot.startTime} committed", flush=True)


def assign_tutorials(tut_sessions, batches, ts_map, t_rooms,
                     division_slots, teacher_slot, room_slot, batch_slot):
    TUT_ROOM_NUMBERS = {"4304B", "4307"}
    tut_rooms = [r for r in t_rooms if r.roomNumber in TUT_ROOM_NUMBERS] or t_rooms

    # Tutorial candidate slots: 12:00 Mon-Thu (avoid Friday morning crunch)
    # or Friday 14:00+ for AFTERNOON divisions
    div_tut_slots = {}
    for div_id, sbd in division_slots.items():
        tslots = []
        for day in DAYS:
            for slot in sbd.get(day, []):
                if day != "FRIDAY" and slot.startTime == 1200:
                    tslots.append(slot)
                elif day == "FRIDAY" and slot.startTime >= 1400 and not is_lunch(slot):
                    tslots.append(slot)
        div_tut_slots[div_id] = tslots

    for sess in tut_sessions:
        bidx        = sess.batch_index
        div_batches = [b for b in batches if b.divisionId == sess.division_id]
        if bidx >= len(div_batches):
            print(f"  TUT {sess.tut_subj} div={sess.division_id} B{bidx+1} "
                  f"no batch object", flush=True)
            continue
        batch    = div_batches[bidx]
        tlist    = ts_map.get((sess.tut_subj, "TUTORIAL"), [])
        tslots   = div_tut_slots.get(sess.division_id, [])
        assigned = False

        for slot in tslots:
            if (batch.id, slot.id) in batch_slot:
                continue
            for t in tlist:
                if (t.id, slot.id) in teacher_slot:
                    continue
                for r in tut_rooms:
                    if (r.id, slot.id) in room_slot:
                        continue
                    teacher_slot.add((t.id, slot.id))
                    room_slot.add((r.id, slot.id))
                    batch_slot.add((batch.id, slot.id))
                    sess.teacher_id   = t.id
                    sess.teacher      = t.shortCode
                    sess.room_id      = r.id
                    sess.room         = r.roomNumber
                    sess.timeslot     = slot.id
                    sess.timeslot_day = slot.day
                    sess._batch_id    = batch.id
                    assigned          = True
                    break
                if assigned:
                    break
            if assigned:
                break

        if not assigned:
            print(f"  TUT {sess.tut_subj} div={sess.division_id} "
                  f"B{bidx+1} unassigned", flush=True)


def assign_theory(theory_sessions, batches, ts_map, t_rooms, division_slots,
                  teacher_slot, room_slot, batch_slot, div_time_windows):
    """
    Assign theory sessions (division-wide, batchId=NULL).

    KEY FIXES vs original:
    - Uses the FULL time window per division (not just 10:00-13:00), so later
      divisions don't run out of available rooms.
    - Checks batch_slot: skips any slot where ANY batch of this division already
      has a lab/tutorial, preventing theory from clashing with a lab for some batches.
    - Day cap raised to 3 per day (was 2) to allow more spread when needed.
    - MORNING:   theory slots = 08:00-14:00, excluding lunch (1300)
    - AFTERNOON: theory slots = 10:00-18:00, excluding lunch (1300)
    """
    div_slot      = set()   # (division_id, slot_id) — at most ONE theory per slot per div
    div_subj_day  = set()   # (division_id, subject_code, day) — no subject twice same day
    div_day_count = {}
    room_count    = {}

    # Build a lookup: division_id -> set of batch_ids
    div_batch_ids = defaultdict(set)
    for b in batches:
        div_batch_ids[b.divisionId].add(b.id)

    # Allow up to 3 theory slots per day per division for flexibility
    day_caps  = {"MONDAY": 3, "TUESDAY": 3, "WEDNESDAY": 3, "THURSDAY": 3, "FRIDAY": 4}
    day_order = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]

    for sess in theory_sessions:
        tw  = div_time_windows.get(sess.division_id, "MORNING")
        sbd = division_slots.get(sess.division_id, {})

        # Build allowed slots for each day based on full time window
        if tw == "AFTERNOON":
            # 10:00 to 18:00, excluding lunch
            def in_window(st): return 1000 <= st < 1800 and st not in LUNCH
        else:
            # MORNING: 08:00 to 14:00, excluding lunch
            def in_window(st): return 800 <= st < 1400 and st not in LUNCH

        allowed = {}
        for day in day_order:
            allowed[day] = [s for s in sbd.get(day, []) if in_window(s.startTime)]

        tlist        = ts_map.get((sess.subject_code, "THEORY"), [])
        sorted_rooms = sorted(t_rooms, key=lambda r: room_count.get(r.id, 0))
        assigned     = False

        # Get all batch IDs for this division (to check batch_slot conflicts)
        this_div_batch_ids = div_batch_ids.get(sess.division_id, set())

        for day in day_order:
            if (sess.division_id, sess.subject_code, day) in div_subj_day:
                continue
            if div_day_count.get((sess.division_id, day), 0) >= day_caps[day]:
                continue

            for slot in allowed.get(day, []):
                if (sess.division_id, slot.id) in div_slot:
                    continue

                # --- FIX: skip slot if ANY batch of this division is busy (lab/tutorial) ---
                batch_conflict = any(
                    (bid, slot.id) in batch_slot
                    for bid in this_div_batch_ids
                )
                if batch_conflict:
                    continue
                # --------------------------------------------------------------------------

                for t in tlist:
                    if (t.id, slot.id) in teacher_slot:
                        continue
                    for r in sorted_rooms:
                        if (r.id, slot.id) in room_slot:
                            continue
                        # Commit
                        teacher_slot.add((t.id, slot.id))
                        room_slot.add((r.id, slot.id))
                        div_slot.add((sess.division_id, slot.id))
                        div_subj_day.add((sess.division_id, sess.subject_code, day))
                        k = (sess.division_id, day)
                        div_day_count[k]  = div_day_count.get(k, 0) + 1
                        room_count[r.id]  = room_count.get(r.id, 0) + 1
                        sess.teacher_id   = t.id
                        sess.teacher      = t.shortCode
                        sess.room_id      = r.id
                        sess.room         = r.roomNumber
                        sess.timeslot     = slot.id
                        sess.timeslot_day = slot.day
                        assigned = True
                        break
                    if assigned:
                        break
                if assigned:
                    break
            if assigned:
                break

        if not assigned:
            print(f"  THEORY {sess.subject_code} div={sess.division_id} unassigned",
                  flush=True)


def generate_timetable(data):
    teachers            = data["teachers"]
    subjects            = data["subjects"]
    rooms               = data["rooms"]
    slots               = data["timeslots"]
    divisions           = data["divisions"]
    batches             = data["batches"]
    teacher_assignments = data["teacher_assignments"]

    if not teachers or not subjects or not rooms:
        print("  Missing teachers, subjects, or rooms", flush=True)
        return None
    if not divisions:
        print("  No divisions found", flush=True)
        return None

    t_rooms = [r for r in rooms if r.roomType == "THEORY"]
    l_rooms = [r for r in rooms if r.roomType == "LAB"]

    full_slots_by_day = {}
    for s in slots:
        full_slots_by_day.setdefault(s.day, []).append(s)
    for d in full_slots_by_day:
        full_slots_by_day[d].sort(key=lambda x: x.startTime)

    teacher_obj = {t.id: t for t in teachers}
    subject_obj = {s.id: s for s in subjects}
    ts_map = {}
    for ts in teacher_assignments:
        subj = subject_obj.get(ts.subjectId)
        t    = teacher_obj.get(ts.teacherId)
        if not subj or not t:
            continue
        key = (subj.code, ts.lectureType)
        ts_map.setdefault(key, [])
        if t not in ts_map[key]:
            ts_map[key].append(t)

    # Per-division slot views filtered by time window
    # MORNING:   08:00 – 14:00  (800  ≤ startTime < 1400)
    # AFTERNOON: 10:00 – 18:00  (1000 ≤ startTime < 1800)
    division_slots    = {}
    div_time_windows  = {}   # division_id -> "MORNING" | "AFTERNOON"

    for division in divisions:
        tw = getattr(division, 'timeWindow', 'MORNING')
        div_time_windows[division.id] = tw

        if tw == "AFTERNOON":
            allowed_start, allowed_end = 1000, 1800
        else:
            allowed_start, allowed_end = 800, 1400

        division_slots[division.id] = {
            d: [s for s in day_slots
                if allowed_start <= s.startTime < allowed_end]
            for d, day_slots in full_slots_by_day.items()
        }

    # Collect all sessions
    all_sessions = []
    for division in divisions:
        tw          = getattr(division, 'timeWindow', 'MORNING')
        div_batches = [b for b in batches if b.divisionId == division.id]
        sessions    = expand_sessions(subjects, division, div_batches)
        for sess in sessions:
            sess.time_window = tw
        lab_c    = sum(1 for s in sessions if s.lecture_type == "LAB")
        tut_c    = sum(1 for s in sessions if s.lecture_type == "TUTORIAL")
        theory_c = sum(1 for s in sessions if s.lecture_type == "THEORY")
        print(f"  Div {division.name} ({tw}): {len(sessions)} sessions "
              f"LAB={lab_c} TUT={tut_c} THEORY={theory_c}", flush=True)
        all_sessions.extend(sessions)

    lab_sessions    = [s for s in all_sessions if s.lecture_type == "LAB"]
    tut_sessions    = [s for s in all_sessions if s.lecture_type == "TUTORIAL"]
    theory_sessions = [s for s in all_sessions if s.lecture_type == "THEORY"]

    # Global conflict sets shared across ALL divisions
    teacher_slot = set()
    room_slot    = set()
    batch_slot   = set()

    # 1. Labs first (they have the most rigid constraints: fixed day, 2-slot blocks)
    assign_labs_per_division(
        lab_sessions, batches, ts_map, l_rooms,
        division_slots, teacher_slot, room_slot, batch_slot
    )

    # 2. Tutorials (12:00 slots Mon-Thu)
    assign_tutorials(
        tut_sessions, batches, ts_map, t_rooms,
        division_slots, teacher_slot, room_slot, batch_slot
    )

    # 3. Theory (division-wide, now checks batch_slot and uses full time window)
    assign_theory(
        theory_sessions, batches, ts_map, t_rooms,
        division_slots, teacher_slot, room_slot, batch_slot,
        div_time_windows
    )

    print(f"  Total sessions scheduled: {len(all_sessions)}", flush=True)
    return all_sessions