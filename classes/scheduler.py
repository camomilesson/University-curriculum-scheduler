"""Scheduler engine.

Contains the scheduling algorithm broken into three passes:
  1. pass1_celebrity: place fixed celebrity course assignments
  2. pass2_chains: schedule courses that are part of prerequisite chains
  3. pass3_solitary: fill remaining courses

Also includes helpers to print and export schedule summaries.
"""

import csv


class Scheduler:
    """Orchestrates scheduling using Teacher/Course/Module domain objects.

    Arguments:
        teachers (dict): teacher_name -> Teacher instance
        courses (dict): course_name -> Course instance
        modules (dict): module_number -> Module instance
    """
    def __init__(self, teachers, courses, modules):
        self.teachers = teachers    # dict: teacher_name -> Teacher
        self.courses = courses      # dict: course_name -> Course
        self.modules = modules      # dict: module_number (1..14) -> Module

    # ---------- PASS 1: CELEBRITY COURSES ----------

    def pass1_celebrity(self, celebrity_courses):
        """
        celebrity_courses: list of tuples (course_name, module_num, teacher_name)
        """
        assigned = 0

        for course_name, module_num, teacher_name in celebrity_courses:
            course_name = (course_name or "").strip()
            teacher_name = (teacher_name or "").strip()

            if not course_name or not teacher_name:
                raise ValueError(f"Bad celebrity row: {course_name, module_num, teacher_name}")

            if module_num not in self.modules:
                raise ValueError(f"Invalid module number {module_num} for '{course_name}'")

            if course_name not in self.courses:
                raise KeyError(f"Celebrity course '{course_name}' not found in courses")

            if teacher_name not in self.teachers:
                raise KeyError(f"Celebrity teacher '{teacher_name}' not found in teachers")

            course = self.courses[course_name]
            teacher = self.teachers[teacher_name]
            module = self.modules[module_num]

            if course.module_assigned is not None:
                raise ValueError(f"Course '{course_name}' already assigned to module {course.module_assigned}")

            if teacher_name not in course.possible_teachers:
                raise ValueError(f"Teacher '{teacher_name}' not in possible_teachers for '{course_name}'")

            if not teacher.is_available_for(course_name, module_num):
                raise ValueError(
                    f"Teacher '{teacher_name}' not available for '{course_name}' in module {module_num}"
                )

            if not module.can_accept(course, layer=0, is_celebrity=True):
                raise ValueError(f"Module {module_num} cannot accept celebrity course '{course_name}'")

            ok = teacher.assign_to(course_name, module_num)
            if ok is False:
                raise ValueError(
                    f"Teacher.assign_to failed for '{teacher_name}' -> '{course_name}' in module {module_num}"
                )

            course.module_assigned = module_num
            course.teacher_assigned = teacher_name
            course.is_celebrity = True

            module.add_course(course, layer=0, is_celebrity=True)
            assigned += 1

        return assigned

    # ---------- PASS 2: CHAIN COURSES (HYBRID v1) ----------

    def pass2_chains(self, max_layers=2):
        """
        Hybrid approach to chain scheduling:
          - iterate modules 1..14 (per layer)
          - for each module, choose best ready chain course that fits

        Priority for choosing among ready chain courses:
          1) course with fewest feasible modules in this layer ("most constrained first")
          2) tie-break: highest latest assigned prereq module (keeps chains moving)
          3) final tie-break: course name (stable)

        Returns number of chain courses assigned.
        Raises on deadlock (ready courses exist but none can be placed).
        """

        def is_ready(course, layer):
            if not course.part_of_chain:
                return False
            if course.module_assigned is not None:
                return False
            if layer < course.min_layer:
                return False
            return course.all_prereqs_assigned(self.courses)

        def fits_in_module(course, module_num, layer, strict=False):
            mod = self.modules[module_num]

            # skip celebrity modules for chains
            if mod.has_celebrity_course:
                return False

            # module-level constraints (cap + 1 chain per layer)
            if not mod.can_accept(course, layer=layer, is_celebrity=False):
                return False

            return course.can_be_assigned_to_module(module_num, layer, self.courses, self.teachers, strict=strict)


        def feasible_module_count(course, layer, strict=False):
            cnt = 0
            for m in range(1, 15):
                if fits_in_module(course, m, layer, strict=strict):
                    cnt += 1
            return cnt

        unassigned = [c for c in self.courses.values() if c.part_of_chain and c.module_assigned is None]
        assigned_total = 0
        layer = 0

        while unassigned:

            if layer > max_layers:
                break
                """ raise RuntimeError(
                    f"Too many layers ({layer}) while chain courses still unassigned "
                    f"({len(unassigned)}). Likely impossible constraints. "
                    f"Unassigned chain courses at layer {layer}: {[c.name for c in unassigned]} "
                ) """

            progress_this_layer = 0

            # -------------------------------------------------
            # TWO-PHASE LOOP: STRICT FIRST, THEN SOFT
            # -------------------------------------------------
            for strict in [True, False]:

                progress_phase = 0

                for module_num in range(1, 15):
                    mod = self.modules[module_num]

                    # skip celebrity modules
                    if mod.has_celebrity_course:
                        continue

                    # skip if this layer already has a chain course in this module
                    if mod.chain_count_in_layer(layer) >= 1:
                        continue

                    candidates = []

                    for course in unassigned:

                        if not is_ready(course, layer):
                            continue

                        if not fits_in_module(course, module_num, layer, strict):
                            continue

                        # scoring
                        mc = feasible_module_count(course, layer, strict)
                        latest = (
                            course.get_latest_assigned_prereq(self.courses)
                            if course.prereqs else 0
                        )

                        candidates.append((mc, -latest, course.name, course))

                    if not candidates:
                        continue

                    candidates.sort()
                    chosen = candidates[0][3]

                    ok = chosen.assign_to_module(
                        module_num,
                        layer,
                        self.courses,
                        self.teachers,
                        strict=strict
                    )

                    if not ok:
                        raise RuntimeError(
                            f"Inconsistent state: '{chosen.name}' "
                            f"was feasible but assignment failed."
                        )

                    mod.add_course(chosen, layer=layer, is_celebrity=False)

                    unassigned.remove(chosen)

                    assigned_total += 1
                    progress_phase += 1

                # If strict phase made progress, DO NOT go to into soft mode
                if progress_phase > 0:
                    progress_this_layer += progress_phase
                    break

            # -------------------------------------------------
            # END OF BOTH PHASES
            # -------------------------------------------------

            if progress_this_layer == 0:
                # No strict progress and no soft progress → move to next layer
                layer += 1

        print(f"Layer reached: {layer}")
        return assigned_total


    # ---------- PASS 3 ----------

    def pass3_solitary(self):
        """
        PASS 3:
        - assumes Pass 2 completed (so all chain courses are assigned)
        - fill remaining unassigned courses ("peas")
        - fill emptiest modules first
        - strict phase first, then soft phase
        - celebrity modules allowed
        - no layers conceptually (we pass layer=0 because Module/Course APIs expect it)

        Returns number of courses assigned in Pass 3.
        """

        def teacher_options_count(course, module_num, strict):
            cnt = 0
            for teacher_name in course.possible_teachers:
                teacher = self.teachers.get(teacher_name)
                if teacher is None:
                    continue
                if teacher.is_available_for(course.name, module_num, strict=strict):
                    cnt += 1
            return cnt

        # all remaining unassigned courses
        unassigned = [c for c in self.courses.values() if c.module_assigned is None]

        assigned_total = 0

        # strict first, then soft
        for strict in [True, False]:

            while unassigned:
                progress = 0

                # emptiest module first (recomputed each sweep)
                module_nums = sorted(
                    self.modules.keys(),
                    key=lambda m: (self.modules[m].total_count(), m)
                )

                for module_num in module_nums:
                    mod = self.modules[module_num]

                    # build candidates for this module
                    candidates = []
                    for course in unassigned:

                        # module capacity check happens inside can_accept()
                        if not mod.can_accept(course, layer=0):
                            continue

                        # teacher availability for this module
                        if not course.has_teachers_for_module(
                            module_num, self.teachers, strict=strict
                        ):
                            continue

                        # prefer most constrained for THIS module
                        opts = teacher_options_count(course, module_num, strict)
                        candidates.append((opts, course.name, course))

                    if not candidates:
                        continue

                    candidates.sort()
                    chosen = candidates[0][2]

                    ok = chosen.assign_to_module(
                        module_num,
                        layer=0,
                        courses=self.courses,
                        teachers=self.teachers,
                        strict=strict
                    )

                    if not ok:
                        # if something changed mid-loop (capacity/teacher), just skip
                        continue

                    mod.add_course(chosen, layer=0)

                    unassigned.remove(chosen)
                    assigned_total += 1
                    progress += 1

                # if we couldn't place anything in a full sweep, stop this phase
                if progress == 0:
                    break

            if not unassigned:
                break

        return assigned_total


    # ---------- OUTPUT ----------

    def print_modules(self):
        print("\n=== CURRENT MODULE STATE ===\n")

        for module_number in sorted(self.modules.keys()):
            module = self.modules[module_number]

            print(f"Module {module_number}")
            print("-" * 40)

            if not module.courses:
                print("  (empty)")
            else:
                for course in module.courses:
                    teacher = course.teacher_assigned or "Unassigned"

                    tag = ""
                    if module.has_celebrity_course and course.teacher_assigned:
                        tag = " [CELEBRITY]" if course.is_celebrity else ""

                    print(f"  {course.name}  |  Teacher: {teacher}{tag}")

            print()


    def print_summary(self):
        """
        Quick overview: module loads + soft usage + unassigned.
        """
        # module load
        print("\n=== SUMMARY ===")
        total_assigned = 0
        total_soft = 0

        for mnum in sorted(self.modules.keys()):
            mod = self.modules[mnum]
            count = len(mod.courses)
            total_assigned += count

            soft_here = 0
            for c in mod.courses:
                if c.teacher_assigned:
                    t = self.teachers.get(c.teacher_assigned)
                    if t and t.availability_value(mnum) == 0:
                        soft_here += 1

            total_soft += soft_here
            celeb = "yes" if mod.has_celebrity_course else "no"

            print(f"Module {mnum:>2}: courses={count:>2} | celeb={celeb} | soft(0)={soft_here}")

        unassigned = [c.name for c in self.courses.values() if c.module_assigned is None]
        unassigned.sort()

        print(f"\nTotal assigned: {total_assigned}")
        print(f"Total soft(0) assignments: {total_soft}")
        print(f"Unassigned courses: {len(unassigned)}\n")

        if unassigned:
            print("Unassigned:\n" + ", ".join(unassigned[:10]) + (" (...)" if len(unassigned) > 10 else ""))


    def export_schedule_csv(self, filename="out_schedule.csv"):
        """
        One row per assigned course.
        Columns: module,course,teacher,needs_confirmation if teacher availability used == 0 (soft constraint)
        """
        rows = []

        for course in self.courses.values():
            if course.module_assigned is None:
                continue

            teacher = self.teachers.get(course.teacher_assigned)
            avail_val = ""
            if teacher is not None:
                avail_val = "" if teacher.availability_value(course.module_assigned) == 1 else "Used 0 availability, needs confirmation"

            rows.append((
                course.module_assigned,
                course.name,
                course.teacher_assigned or "",
                avail_val
            ))

        # stable ordering
        rows.sort(key=lambda r: (r[0], r[1], r[2]))

        with open(filename, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["module", "course", "teacher", "needs confirmation"])
            w.writerows(rows)


    def export_soft_violations_csv(self, filename="out_soft_violations.csv"):
        """
        Only rows where teacher_availability == 0.
        Columns: module,course,teacher
        """
        rows = []

        for course in self.courses.values():
            if course.module_assigned is None or not course.teacher_assigned:
                continue

            teacher = self.teachers.get(course.teacher_assigned)
            if teacher is None:
                continue

            if teacher.availability_value(course.module_assigned) == 0:
                rows.append((
                    course.module_assigned,
                    course.name,
                    course.teacher_assigned
                ))

        rows.sort(key=lambda r: (r[0], r[1], r[2]))

        with open(filename, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["module", "course", "teacher"])
            w.writerows(rows)

