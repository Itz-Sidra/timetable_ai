class Session:

    def __init__(self, subject, lecture_type, duration):
        self.subject = subject
        self.lecture_type = lecture_type
        self.duration = duration

        # Used by THEORY / TUTORIAL
        self.teacher = None
        self.room = None
        self.timeslot = None
        self.timeslot_day = None

        # Used by LAB — list of {"teacher": ..., "room": ..., "batch_index": i}
        # One entry per batch; all share the same timeslot pair
        self.batch_assignments: list[dict] = []

    def __repr__(self):
        return f"{self.subject} {self.lecture_type}"