"""Scheduler entrypoint.

This module reads CSV inputs from the `csvs/` directory, builds the domain
objects (`Teacher`, `Course`, `Module`), runs the scheduling passes via
`Scheduler`, and writes two output CSVs: `out_schedule.csv` and
`out_soft_violations.csv`.

Expected CSV formats (brief):
- `teacher_availability.csv`: columns "name","capacity","M1".."M14"
- `course_teacher.csv`: rows: course_name,teacher1,teacher2,...
- `prereqs_CSDS.csv`: rows: course_name,min_layer,prereq1,prereq2,...
- `celebrity_courses.csv`: columns "course_name","module","teacher"
"""

from classes import Scheduler

# Loader functions and CSV constants have been moved to `data_loaders.py` to
# separate I/O and building logic from the orchestration in `main.py`.
from data_loaders import (
    build_teachers,
    build_courses,
    build_modules,
    load_celebrity_courses,
    debug_state,
)

DEBUG = True


# ---------- MAIN ----------
def main():
    """Orchestrate data loading, scheduling passes, and CSV exports.

    Flow:
      1. Build teachers, courses and modules.
      2. Create a Scheduler and run three passes:
         - pass1_celebrity: place pre-assigned celebrity courses
         - pass2_chains: schedule prerequisite chains
         - pass3_solitary: schedule remaining standalone courses
      3. Print summaries and export CSV outputs.

    Side effects:
        - Writes `out_schedule.csv` and `out_soft_violations.csv` to cwd.
    """
    teachers = build_teachers()
    courses = build_courses(teachers)
    modules = build_modules()

    scheduler = Scheduler(teachers, courses, modules)

    # Helpful development-only dump when debugging is enabled
    if DEBUG:
        debug_state(teachers, courses, modules)

    # Pass 1: place celebrity courses (fixed module+teacher assignments)
    celebrity_courses = load_celebrity_courses()
    scheduler.pass1_celebrity(celebrity_courses)

    # Pass 2: schedule chained/prerequisite courses
    assigned_chain = scheduler.pass2_chains()
    print(f"\nAssigned {assigned_chain} chain courses.")

    # Pass 3: schedule remaining solitary courses
    assigned_solitary = scheduler.pass3_solitary()
    print(f"Assigned {assigned_solitary} solitary courses")

    # Print result and export CSVs
    scheduler.print_modules()
    scheduler.print_summary()

    scheduler.export_schedule_csv("out_schedule.csv")
    scheduler.export_soft_violations_csv("out_soft_violations.csv")

    print("\nWrote out_schedule.csv and out_soft_violations.csv") 


if __name__ == "__main__":
    main()
