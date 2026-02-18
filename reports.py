import csv


def write_zero_capacity_teachers_report(
    teachers: dict,
    courses: dict,
    filepath: str = "csvs/teachers_capacity_zero.csv",
) -> None:
    """
    Writes a CSV report for teachers with capacity == 0.

    Output:
      teacher, occurrences, course1, course2, ...
    """

    rows = []

    for teacher_name, teacher in teachers.items():
        if teacher.capacity_total != 0:
            continue

        matching_courses = []

        for course_name, course in courses.items():
            if teacher_name in course.possible_teachers:
                matching_courses.append(course_name)

        if matching_courses:
            matching_courses.sort()
            rows.append((teacher_name, matching_courses))

    rows.sort(key=lambda x: x[0].lower())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["teacher", "occurrences", "courses..."])

        for teacher_name, course_list in rows:
            writer.writerow([teacher_name, len(course_list), *course_list])
