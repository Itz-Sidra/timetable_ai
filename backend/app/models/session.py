class Session:
    def __init__(self, subject_code, subject_name, lecture_type, duration,
                 division_id=None, elective_group_id=None):
        self.subject_code      = subject_code
        self.subject_name      = subject_name
        self.subject           = subject_name   # alias used in scheduler
        self.lecture_type      = lecture_type
        self.duration          = duration
        self.division_id       = division_id
        self.elective_group_id = elective_group_id

        # THEORY / TUTORIAL
        self.teacher      = None
        self.teacher_id   = None
        self.room         = None
        self.room_id      = None
        self.timeslot     = None
        self.timeslot_day = None

        # LAB — list of per-batch dicts
        self.batch_assignments: list[dict] = []

    def __repr__(self):
        return f"<{self.subject_code} {self.lecture_type} div={self.division_id}>"