from classes import module


"""Teacher domain object and availability helpers."""


class Teacher:
    """Represents a teacher and their availability/capacity state.

    Attributes:
        name (str): teacher name
        can_teach_courses (set[str]): set of course names this teacher can teach
        availability (list[int]): 14 ints where 1 = preferred, 0 = soft/ok, -1 = forbidden
        capacity_total (int): initial capacity
        capacity_left (int): remaining capacity
        teaches (list[tuple[str,int]]): assigned (course_name, module)
        assigned_modules (set[int]): modules already taken by this teacher
    """
    def __init__(self, name: str, can_teach_courses, availability, capacity: int):
        self.name = name
        self.can_teach_courses = set(can_teach_courses)   # course names
        self.availability = list(availability)            # 14 ints: 1/0/-1 (declared)
        self.capacity_total = int(capacity)
        self.capacity_left = int(capacity)

        self.teaches = []              # list of (course_name, module)
        self.assigned_modules = set()  # modules already taken (1..14)


    def is_available_for(self, course_name: str, module: int, strict: bool = False) -> bool:
        """Return True when this teacher can teach `course_name` in `module`.

        Args:
            course_name (str): name of the course to check
            module (int): module number (1..14)
            strict (bool): when True, treat availability==0 as unavailable
        """
        if self.capacity_left < 1:
            return False
        if module in self.assigned_modules:
            return False
        if self.availability[module - 1] == -1:  # if forbidden
            return False
        if strict and self.availability[module - 1] == 0:  # if not declared and strict mode
            return False
        if course_name not in self.can_teach_courses:
            return False
        return True
    

    def availability_score(self, module):
        """Return a small score for availability preference (lower is better).

        Returns 0 for declared availability (1), 1 for soft availability (0).
        """
        val = self.availability[module - 1]
        if val == 1:
            return 0
        if val == 0:
            return 1


    def assign_to(self, course_name: str, module: int) -> bool:
        """Assign the teacher to a course in a module, updating state.

        Returns True if assignment succeeded; False otherwise.
        """
        if not self.is_available_for(course_name, module):
            return False
        self.teaches.append((course_name, module))
        self.assigned_modules.add(module)
        self.capacity_left -= 1
        return True


    def availability_value(self, module):
        """Return the raw availability int for the module (1/0/-1)."""
        return self.availability[module - 1]


    def __repr__(self):
        return (
            f"Teacher(name={self.name!r}, "
            f"capacity={self.capacity_left}/{self.capacity_total}, "
            f"modules={sorted(self.assigned_modules)}, "
            f"courses={[c for c, _ in self.teaches]})"
        )
