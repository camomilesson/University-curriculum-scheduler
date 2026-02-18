"""CSV loaders and builders for the scheduler.

This module centralises reading CSV inputs and constructing domain objects
(`Teacher`, `Course`, `Module`) so `main.py` can remain a thin orchestration
layer. File-path constants live here by default but the functions can be
adapted to accept paths as parameters for testing.
"""

import csv

from classes import Teacher, Course, Module


# Paths to CSV input files used by the script.
TEACHER_AVAIL_FILE = "csvs/teacher_availability.csv"
PREREQS_FILE = "csvs/prereqs_CSDS.csv"
COURSE_TEACHER_FILE = "csvs/course_teacher.csv"
CELEBRITY_FILE = "csvs/celebrity_courses.csv"



def load_teacher_availability():
    """Parse the teacher availability CSV and return metadata per teacher.

    Returns:
        dict[str, dict]: mapping teacher name -> {"availability": list[int], "capacity": int}
    """
    teachers_data = {}

    with open(TEACHER_AVAIL_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            name = row["name"].strip()

            # Parse module availability columns M1..M14 into integers
            availability = [int(row[f"M{i}"]) for i in range(1, 15)]
            capacity = int(row["capacity"])

            teachers_data[name] = {
                "availability": availability,
                "capacity": capacity,
            }

    return teachers_data


def load_course_teacher_rows():
    """Read `course_teacher.csv` and return (course, [teachers...]) rows.

    Returns:
        list[tuple[str, list[str]]]: list of (course_name, teacher_names)
    """
    rows = []
    with open(COURSE_TEACHER_FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)

        for row in reader:
            if not row:
                continue
            course_name = row[0].strip()
            teacher_names = [t.strip() for t in row[1:] if t.strip()]
            rows.append((course_name, teacher_names))
    return rows


def build_teachers():
    """Build `Teacher` objects from availability and course->teacher mapping.

    Returns:
        dict[str, Teacher]: mapping teacher name -> Teacher instance
    """
    teacher_availability = load_teacher_availability()

    # Invert course->teachers into teacher->courses for quick lookup when creating
    # Teacher objects.
    teacher_to_courses = {}
    for course_name, teacher_names in load_course_teacher_rows():
        for t in teacher_names:
            teacher_to_courses.setdefault(t, set()).add(course_name)

    teachers = {}
    for name, data in teacher_availability.items():
        can_teach_courses = teacher_to_courses.get(name, set())

        teachers[name] = Teacher(
            name=name,
            can_teach_courses=can_teach_courses,
            availability=data["availability"],
            capacity=data["capacity"],
        )

    return teachers


def build_courses_from_course_teacher(teachers):
    """Create Course objects from `course_teacher.csv` and populate teachers."""
    courses = {}

    for course_name, teacher_names in load_course_teacher_rows():
        course = courses.get(course_name)
        if course is None:
            course = Course(course_name)
            courses[course_name] = course

        # attach teacher names (ensure teacher exists)
        for t in teacher_names:
            if t not in teachers:
                teachers[t] = Teacher(
                    name=t,
                    can_teach_courses=set(),
                    availability=[-1]*14,
                    capacity=0
                )
            course.possible_teachers.add(t)

    return courses


def load_prereqs_into_courses(courses):
    """Load prerequisite relationships from `prereqs_CSDS.csv` into `courses`."""
    with open(PREREQS_FILE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)

        for row in reader:
            if not row:
                continue

            course_name = row[0].strip()
            min_layer = int(row[1].strip()) if row[1].strip() else 0
            prereq_names = [c.strip() for c in row[2:] if c.strip()]

            if course_name not in courses:
                raise KeyError(
                    f"prereqs_CSDS.csv course '{course_name}' not found in course_teacher.csv"
                )

            course = courses[course_name]
            course.min_layer = min_layer
            course.prereqs.update(prereq_names)
            course.part_of_chain = True

            for prereq in prereq_names:
                if prereq not in courses:
                    raise KeyError(
                        f"prereqs_CSDS.csv prereq '{prereq}' not found in course_teacher.csv"
                    )


def build_courses(teachers):
    courses = build_courses_from_course_teacher(teachers)
    load_prereqs_into_courses(courses)
    return courses


def load_celebrity_courses():
    """Parse celebrity courses CSV and return list of (course, module, teacher)."""
    celebrity_courses = []
    with open(CELEBRITY_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            course_name = row["course_name"].strip()
            module_num = int(row["module"])
            teacher_name = row["teacher"].strip()
            celebrity_courses.append((course_name, module_num, teacher_name))
    return celebrity_courses


def build_modules(total_modules=14, max_capacity=9):
    """Create Module objects for module indices 1..total_modules."""
    modules = {}

    for i in range(1, total_modules + 1):
        modules[i] = Module(number=i, max_capacity=max_capacity)

    return modules


def debug_state(teachers, courses, modules):
    """Print a compact debug summary of loaded domain objects."""
    print(f"Loaded {len(teachers)} teachers")
    print(f"Loaded {len(courses)} courses")
    print(f"Loaded {len(modules)} modules")

    chain_courses = [c for c in courses.values() if c.part_of_chain]
    print(f"Chain courses: {len(chain_courses)}")

    print("\n--- sample courses ---")
    for c in list(courses.values())[:5]:
        print(c)

    print("\n--- sample teachers ---")
    for t in list(teachers.values())[:5]:
        print(t)

    print("\n--- sample modules ---")
    for m in list(modules.values())[:5]:
        print(m)
