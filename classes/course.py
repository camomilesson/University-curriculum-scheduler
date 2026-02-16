"""Course domain object and helpers.

This module defines the Course class which stores metadata parsed from CSVs
and provides helper methods used during scheduling (prereq checks,
teacher selection and assignment helpers).
"""


class Course:
    """Represents a single course to be scheduled.

    Attributes:
        name (str): Course identifier.
        part_of_chain (bool): True when course has prereqs.
        min_layer (int): minimum scheduling layer (0-based) allowed for course.
        prereqs (set[str]): names of prerequisite courses.
        possible_teachers (set[str]): teacher names who can teach this course.
        module_assigned (int|None): assigned module number (1..14) or None.
        teacher_assigned (str|None): assigned teacher name or None.
        layer_assigned (int|None): assigned scheduling layer or None.
        is_celebrity (bool): whether this course was fixed by celebrity CSV.
    """
    def __init__(self, name):
        self.name = name

        # update externally while loading CSVs
        self.part_of_chain = False
        self.min_layer = 0

        # store prereqs and teachers as names (strings)
        self.prereqs = set()
        self.possible_teachers = set()

        # scheduling state
        self.module_assigned = None
        self.teacher_assigned = None
        self.layer_assigned = None
        self.is_celebrity = False

    # ---------- prereq helpers ----------

    def all_prereqs_assigned(self, courses):
        """Return True when all prerequisite courses have been assigned a module.

        Args:
            courses (dict): mapping course_name -> Course object (used to resolve prereq names).

        Raises:
            KeyError: if a referenced prerequisite is missing from the provided map.
        """
        for prereq_name in self.prereqs:
            prereq = courses.get(prereq_name)
            if prereq is None:
                raise KeyError(
                    f"Missing prereq '{prereq_name}' for course '{self.name}'"
                )
            if prereq.module_assigned is None:
                return False
        return True

    def get_latest_assigned_prereq(self, courses):
        """Return the highest module number among assigned prerequisites.

        Raises ValueError if any prereq exists but has not been assigned yet.
        """
        latest = 0
        for prereq_name in self.prereqs:
            prereq_module = courses[prereq_name].module_assigned
            if prereq_module is None:
                raise ValueError(
                    f"Prereq '{prereq_name}' for course '{self.name}' not assigned."
                )
            latest = max(latest, prereq_module)
        return latest

    # ---------- teacher helpers ----------

    def has_teachers_for_module(self, module, teachers, strict=False):
        """Return True if any possible teacher can teach this course in the module.

        This performs a lightweight availability check using Teacher.is_available_for.
        """
        for teacher_name in self.possible_teachers:
            teacher = teachers.get(teacher_name)

            if teacher.is_available_for(self.name, module, strict=strict):
                return True

        return False


    def get_teacher_for_module(self, module, teachers, strict=False):
        """Choose the best available teacher for this course in the module.

        Selection heuristic (lower is better):
          1) availability_score (declared availability preferred)
          2) specialization (fewer courses means more specialized)
          3) capacity left (prefer teachers with more remaining capacity)

        Returns selected teacher name or None if none are available.
        """
        available = []

        for teacher_name in self.possible_teachers:
            teacher = teachers.get(teacher_name)
            if teacher is None:
                raise KeyError(
                    f"Teacher '{teacher_name}' missing for course '{self.name}'"
                )

            if teacher.is_available_for(self.name, module, strict=strict):
                specialization = len(teacher.can_teach_courses)
                capacity_left = teacher.capacity_left
                availability_score = teacher.availability_score(module)
                available.append((teacher_name, availability_score, specialization, capacity_left))

        if not available:
            return None

        best = min(available, key=lambda t: (t[1], t[2], -t[3]))
        return best[0]


    # ---------- assignment ----------

    def can_be_assigned_to_module(self, module, layer, courses, teachers, strict=False):
        """Return True if this course can be placed in (module, layer).

        Checks:
          - not already assigned
          - layer meets min_layer
          - all prereqs are assigned and scheduled before this slot
          - at least one teacher is available for the slot
        """
        if self.module_assigned is not None:
            return False

        if layer < self.min_layer:
            return False

        if not self.all_prereqs_assigned(courses):
            return False

        absolute_current = layer * 14 + module

        for prereq_name in self.prereqs:
            prereq = courses[prereq_name]

            if prereq.layer_assigned is None:
                return False

            absolute_prereq = prereq.layer_assigned * 14 + prereq.module_assigned

            if absolute_current <= absolute_prereq:
                return False

        if not self.has_teachers_for_module(module, teachers, strict=strict):
            return False

        return True

    def assign_to_module(self, module, layer, courses, teachers, strict=False):
        """Assign this course to a module+layer using the best available teacher.

        Returns True when assignment succeeded and teacher/module state were updated.
        """
        if not self.can_be_assigned_to_module(module, layer, courses, teachers, strict=strict):
            return False

        chosen_teacher = self.get_teacher_for_module(module, teachers, strict=strict)
        if chosen_teacher is None:
            return False

        ok = teachers[chosen_teacher].assign_to(self.name, module)
        if ok is False:
            return False

        self.module_assigned = module
        self.layer_assigned = layer
        self.teacher_assigned = chosen_teacher
        return True

    def __repr__(self):
        return (
            f"Course(name={self.name!r}, "
            f"module={self.module_assigned}, "
            f"teacher={self.teacher_assigned})"
        )
