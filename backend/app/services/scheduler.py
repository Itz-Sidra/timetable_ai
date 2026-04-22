"""
Fixed scheduler.py

Key fixes:
1. Lab day spread: each subject gets its OWN base day offset so 4 subjects
   don't all land on the same day, exhausting slots.
2. Elective filter: TY-A gets MPBDA only, TY-B gets IFSSD only — others skipped.
3. Tutorial slots expanded: also try 14:00-17:00 Mon-Thu for AFTERNOON divisions.
4. Theory time window: MORNING 08-14, AFTERNOON 10-18.
5. Year filtering done in generate_timetable via pre-built dict (bypasses Prisma attr issue).
"""

from collections import defaultdict
from app.models.session import Session

LUNCH = {1300}
DAYS  = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]


def expand_sessions(subjects, division, batches):
    """
    subjects are ALREADY filtered to this division's year by generate_timetable.
    """
    sessions = []

    rotation_days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY"]
    div_offset = division.id % len(rotation_days)

    for subj_idx, subject in enumerate(subjects):
        elective_group_id = subject.electiveGroupId

        # ── ELECTIVE FILTER ─────────────────────────────────────────────────
        if elective_group_id is not None:
            if division.name == "A" and subject.code != "MPBDA":
                continue
            if division.name == "B" and subject.code != "IFSSD":
                continue
        # ────────────────────────────────────────────────────────────────────

        theory_hours = subject.theoryHours or 0
        lab_hours    = subject.labHours    or 0
        tut_hours    = subject.tutHours    or 0

        print(f"    [expand] Div={division.name} INCLUDE {subject.code} "
              f"T={theory_hours} L={lab_hours} TUT={tut_hours}", flush=True)

        # ── THEORY ──────────────────────────────────────────────────────────
        for _ in range(theory_hours):
            sessions.append(Session(
                subject.code, subject.name, "THEORY", 1,
                division_id=division.id,
                elective_group_id=elective_group_id,
            ))

        # ── LAB — one session per batch ──────────────────────────────────────
        # subj_idx shifts base day so each subject lands on a different day
        if lab_hours > 0:
            for bidx in range(len(batches)):
                day = rotation_days[(bidx + div_offset + subj_idx) % len(rotation_days)]
                sess = Session(
                    subject.code, subject.name, "LAB", 2,
                    division_id=division.id,
                    elective_group_id=None,
                )
                sess.batch_index  = bidx
                sess.assigned_day = day
                sessions.append(sess)

        # ── TUTORIAL — one session per batch ────────────────────────────────
        if tut_hours > 0:
            for bidx in range(len(batches)):
                sess = Session(
                    subject.code, subject.name, "TUTORIAL", 1,
                    division_id=division.id,
                    elective_group_id=elective_group_id,
                )
                sess.batch_index = bidx
                sess.tut_subj    = subject.code
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

    # Expanded tutorial candidate slots:
    # 12:00 Mon-Thu  +  14:00-17:00 any day (covers AFTERNOON TY divisions)
    div_tut_slots = {}
    for div_id, sbd in division_slots.items():
        tslots = []
        for day in DAYS:
            for slot in sbd.get(day, []):
                if is_lunch(slot):
                    continue
                if day != "FRIDAY" and slot.startTime == 1200:
                    tslots.append(slot)
                elif 1400 <= slot.startTime <= 1700:
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
    div_slot      = set()
    div_subj_day  = set()
    div_day_count = {}
    room_count    = {}

    div_batch_ids = defaultdict(set)
    for b in batches:
        div_batch_ids[b.divisionId].add(b.id)

    day_caps  = {"MONDAY": 3, "TUESDAY": 3, "WEDNESDAY": 3, "THURSDAY": 3, "FRIDAY": 4}
    day_order = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]

    for sess in theory_sessions:
        tw  = div_time_windows.get(sess.division_id, "MORNING")
        sbd = division_slots.get(sess.division_id, {})

        if tw == "AFTERNOON":
            def in_window(st): return 1000 <= st < 1800 and st not in LUNCH
        else:
            def in_window(st): return 800 <= st < 1400 and st not in LUNCH

        allowed = {}
        for day in day_order:
            allowed[day] = [s for s in sbd.get(day, []) if in_window(s.startTime)]

        tlist        = ts_map.get((sess.subject_code, "THEORY"), [])
        sorted_rooms = sorted(t_rooms, key=lambda r: room_count.get(r.id, 0))
        assigned     = False

        this_div_batch_ids = div_batch_ids.get(sess.division_id, set())

        for day in day_order:
            if (sess.division_id, sess.subject_code, day) in div_subj_day:
                continue
            if div_day_count.get((sess.division_id, day), 0) >= day_caps[day]:
                continue

            for slot in allowed.get(day, []):
                if (sess.division_id, slot.id) in div_slot:
                    continue

                batch_conflict = any(
                    (bid, slot.id) in batch_slot
                    for bid in this_div_batch_ids
                )
                if batch_conflict:
                    continue

                for t in tlist:
                    if (t.id, slot.id) in teacher_slot:
                        continue
                    for r in sorted_rooms:
                        if (r.id, slot.id) in room_slot:
                            continue
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

    # ── PRE-BUILD: subjects grouped by yearId (bypasses Prisma attr issue) ──
    subjects_by_year: dict = defaultdict(list)
    for s in subjects:
        yr = s.yearId
        if yr is not None:
            subjects_by_year[yr].append(s)
        else:
            print(f"  [warn] Subject {s.code} has yearId=None — skipped", flush=True)

    print(f"  Subjects by year: { {k: [s.code for s in v] for k,v in subjects_by_year.items()} }",
          flush=True)
    # ────────────────────────────────────────────────────────────────────────

    division_slots   = {}
    div_time_windows = {}

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

    all_sessions = []
    for division in divisions:
        tw          = getattr(division, 'timeWindow', 'MORNING')
        div_batches = [b for b in batches if b.divisionId == division.id]

        div_year_id  = division.yearId
        div_subjects = subjects_by_year.get(div_year_id, [])

        print(f"  [gen] Div={division.name} id={division.id} yearId={div_year_id} "
              f"subjects={[s.code for s in div_subjects]}", flush=True)

        sessions = expand_sessions(div_subjects, division, div_batches)
        for sess in sessions:
            sess.time_window = tw

        lab_c    = sum(1 for s in sessions if s.lecture_type == "LAB")
        tut_c    = sum(1 for s in sessions if s.lecture_type == "TUTORIAL")
        theory_c = sum(1 for s in sessions if s.lecture_type == "THEORY")
        print(f"  Div {division.name} id={division.id} ({tw}): {len(sessions)} sessions "
              f"LAB={lab_c} TUT={tut_c} THEORY={theory_c}", flush=True)

        all_sessions.extend(sessions)

    lab_sessions    = [s for s in all_sessions if s.lecture_type == "LAB"]
    tut_sessions    = [s for s in all_sessions if s.lecture_type == "TUTORIAL"]
    theory_sessions = [s for s in all_sessions if s.lecture_type == "THEORY"]

    teacher_slot = set()
    room_slot    = set()
    batch_slot   = set()

    assign_labs_per_division(
        lab_sessions, batches, ts_map, l_rooms,
        division_slots, teacher_slot, room_slot, batch_slot
    )

    assign_tutorials(
        tut_sessions, batches, ts_map, t_rooms,
        division_slots, teacher_slot, room_slot, batch_slot
    )

    assign_theory(
        theory_sessions, batches, ts_map, t_rooms,
        division_slots, teacher_slot, room_slot, batch_slot,
        div_time_windows
    )

    print(f"  Total sessions scheduled: {len(all_sessions)}", flush=True)
    return all_sessions