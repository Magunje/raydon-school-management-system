import random
from django.db import transaction
from django.utils import timezone
from academics.models import ClassTimetableEntry
from students.models import SchoolClass
from academics.models import Subject
from accounts.models import UserProfile
from timetable.models import Room, SubjectAllocation, TeacherAvailability, TimetablePeriodConfig
from timetable.services.conflict_checker import ConflictChecker
from timetable.services.room_allocator import RoomAllocator
from timetable.services.workload_manager import WorkloadManager

class TimetableScheduler:
    @staticmethod
    def pre_populate_configs_if_empty():
        if not TimetablePeriodConfig.objects.exists():
            default_periods = [
                (1, "08:00", "08:40", "Lesson", "Period 1"),
                (2, "08:40", "09:20", "Lesson", "Period 2"),
                (3, "09:20", "09:40", "Break", "Tea Break"),
                (4, "09:40", "10:20", "Lesson", "Period 3"),
                (5, "10:20", "11:00", "Lesson", "Period 4"),
                (6, "11:00", "11:40", "Lesson", "Period 5"),
                (7, "11:40", "12:00", "Break", "Short Break"),
                (8, "12:00", "13:00", "Lunch", "Lunch Break"),
                (9, "13:00", "13:40", "Lesson", "Period 6"),
                (10, "13:40", "14:20", "Lesson", "Period 7"),
                (11, "14:20", "15:00", "Lesson", "Period 8"),
            ]
            for p_no, start, end, p_type, label in default_periods:
                TimetablePeriodConfig.objects.create(
                    period_no=p_no,
                    start_time=start,
                    end_time=end,
                    period_type=p_type,
                    label=label
                )

    @staticmethod
    def generate(academic_year, target_class_id=None, replace_existing=False):
        """
        Main entry point for generating timetables.
        - target_class_id: if specified, generates only for that class.
        - replace_existing: if True, deletes unlocked entries before generation.
        """
        # 1. Initialize configs
        TimetableScheduler.pre_populate_configs_if_empty()

        # 2. Get list of active classes to schedule
        classes_query = SchoolClass.objects.filter(academic_year=academic_year)
        if target_class_id:
            classes_query = classes_query.filter(class_id=target_class_id)
        classes = list(classes_query)

        if not classes:
            return {"created": 0, "skipped": 0, "status": "No classes found"}

        # 3. Handle replacement of existing entries
        with transaction.atomic():
            if replace_existing:
                # Delete all unlocked entries for these classes
                del_query = ClassTimetableEntry.objects.filter(
                    academic_year=academic_year,
                    is_locked=False
                )
                if target_class_id:
                    del_query = del_query.filter(class_id=target_class_id)
                del_query.delete()

            # 4. Load period configs & days
            lesson_periods = list(TimetablePeriodConfig.objects.filter(period_type='Lesson').order_by('period_no'))
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            day_orders = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4, "Friday": 5}

            # 5. Populate booked slots (teacher, class, room bookings)
            # booked_teachers: set of (teacher_name, day, period_no)
            booked_teachers = set()
            booked_classes = set()
            booked_rooms = set()

            # Get list of classes being generated
            target_class_ids = set(c.class_id for c in classes)

            # Load remaining entries
            remaining_entries_query = ClassTimetableEntry.objects.filter(academic_year=academic_year)
            if replace_existing:
                remaining_entries_query = remaining_entries_query.exclude(
                    class_id__in=target_class_ids,
                    is_locked=False
                )
            remaining_entries = list(remaining_entries_query)

            for entry in remaining_entries:
                if entry.teacher_name:
                    booked_teachers.add((entry.teacher_name.upper().strip(), entry.day_name, entry.period_no))
                booked_classes.add((entry.class_id, entry.day_name, entry.period_no))
                if entry.room_name:
                    booked_rooms.add((entry.room_name.upper().strip(), entry.day_name, entry.period_no))

            # 6. Load room and teacher configurations in-memory
            all_teachers = UserProfile.objects.filter(role='Teacher', status='Active')
            
            # Pre-cache teacher availabilities
            teacher_availabilities = {}
            for teacher in all_teachers:
                avail = WorkloadManager.get_teacher_availability(teacher.id)
                if avail:
                    avail_days = [d.strip().lower() for d in avail.available_days.split(",") if d.strip()]
                    avail_periods = [p.strip() for p in avail.available_periods.split(",") if p.strip()]
                    teacher_availabilities[teacher.full_name.upper().strip()] = {
                        'max_periods_per_day': avail.max_periods_per_day,
                        'max_periods_per_week': avail.max_periods_per_week,
                        'days': set(avail_days),
                        'periods': set(avail_periods)
                    }

            # Pre-cache workloads
            teacher_weekly_workload = {}
            teacher_daily_workload = {}
            for teacher in all_teachers:
                t_key = teacher.full_name.upper().strip()
                teacher_weekly_workload[t_key] = 0
                for day in days:
                    teacher_daily_workload[(t_key, day)] = 0

            for entry in remaining_entries:
                if entry.teacher_name:
                    t_key = entry.teacher_name.upper().strip()
                    if t_key in teacher_weekly_workload:
                        teacher_weekly_workload[t_key] += 1
                    day_key = (t_key, entry.day_name)
                    if day_key in teacher_daily_workload:
                        teacher_daily_workload[day_key] += 1

            # Class sizes cache
            from students.models import Pupil
            class_sizes = {}
            for c in classes:
                class_sizes[c.class_id] = Pupil.objects.filter(class_id=c.class_id, status='Active').count()

            # Rooms cache by type
            all_rooms = list(Room.objects.all())
            rooms_by_type = {}
            for r_type, _ in Room.ROOM_TYPES:
                rooms_by_type[r_type] = sorted(
                    [r for r in all_rooms if r.room_type == r_type],
                    key=lambda x: x.capacity
                )

            # In-memory helper functions for backtracking
            def check_workload_in_memory(teacher_key, day_name, added_periods=1):
                if not teacher_key:
                    return True
                limits = teacher_availabilities.get(teacher_key)
                if not limits:
                    return True
                weekly_current = teacher_weekly_workload.get(teacher_key, 0)
                if weekly_current + added_periods > limits['max_periods_per_week']:
                    return False
                daily_current = teacher_daily_workload.get((teacher_key, day_name), 0)
                if daily_current + added_periods > limits['max_periods_per_day']:
                    return False
                return True

            def find_room_in_memory(class_id, req_room_type, day_name, period_no):
                class_size = class_sizes.get(class_id, 0)
                candidate_rooms = rooms_by_type.get(req_room_type, [])
                if not candidate_rooms:
                    candidate_rooms = rooms_by_type.get('Classroom', [])
                    if not candidate_rooms:
                        return f"Classroom {class_id}"
                for room in candidate_rooms:
                    if room.capacity >= class_size:
                        room_key = (room.room_name.upper().strip(), day_name, period_no)
                        if room_key not in booked_rooms:
                            return room.room_name
                for room in candidate_rooms:
                    room_key = (room.room_name.upper().strip(), day_name, period_no)
                    if room_key not in booked_rooms:
                        return room.room_name
                return candidate_rooms[0].room_name

            created_count = 0
            skipped_count = 0

            # Generate timetable class-by-class using CSP backtracking
            for school_class in classes:
                # Check if this class already has a timetable generated (and we shouldn't replace it)
                if not replace_existing:
                    exists = ClassTimetableEntry.objects.filter(
                        class_id=school_class.class_id,
                        academic_year=academic_year
                    ).exists()
                    if exists:
                        skipped_count += 1
                        continue

                # Get subject allocations for this class
                allocations = list(SubjectAllocation.objects.filter(school_class=school_class))
                if not allocations:
                    class_teacher_profile = None
                    if school_class.class_teacher_id:
                        class_teacher_profile = UserProfile.objects.filter(id=school_class.class_teacher_id).first()
                    elif school_class.class_teacher:
                        class_teacher_profile = UserProfile.objects.filter(full_name__iexact=school_class.class_teacher).first()

                    if class_teacher_profile and class_teacher_profile.role != 'Teacher':
                        class_teacher_profile = None

                    class_grade_name = school_class.class_name[:3]  # E.g. Form 1 -> Form
                    from academics.views import subjects_for_grade
                    subjects = subjects_for_grade(class_grade_name)
                    if not subjects:
                        subjects = list(Subject.objects.filter(status='Active')[:6])

                    # Exclude teachers who are assigned as class teachers to any class
                    class_teachers = set(c.class_teacher_id for c in classes if c.class_teacher_id)
                    active_teachers_list = [t for t in all_teachers if t.id not in class_teachers]
                    if not active_teachers_list:
                        active_teachers_list = list(all_teachers)

                    if subjects and active_teachers_list:
                        for idx, subject_obj in enumerate(subjects):
                            if isinstance(subject_obj, dict):
                                subject_instance = Subject.objects.get(subject_id=subject_obj['subject_id'])
                            else:
                                subject_instance = subject_obj

                            if class_teacher_profile:
                                teacher_for_subject = class_teacher_profile
                            else:
                                teacher_idx = (school_class.class_id + idx) % len(active_teachers_list)
                                teacher_for_subject = active_teachers_list[teacher_idx]

                            SubjectAllocation.objects.create(
                                school_class=school_class,
                                subject=subject_instance,
                                teacher=teacher_for_subject,
                                periods_per_week=4,
                                required_room_type='Classroom'
                            )
                        allocations = list(SubjectAllocation.objects.filter(school_class=school_class))

                if not allocations:
                    skipped_count += 1
                    continue

                # Prepare the items to schedule
                schedule_items = []
                for alloc in allocations:
                    periods = alloc.periods_per_week
                    is_prac = alloc.is_practical
                    if is_prac:
                        doubles = periods // 2
                        singles = periods % 2
                        for _ in range(doubles):
                            schedule_items.append({"alloc": alloc, "type": "double"})
                        for _ in range(singles):
                            schedule_items.append({"alloc": alloc, "type": "single"})
                    else:
                        for _ in range(periods):
                            schedule_items.append({"alloc": alloc, "type": "single"})

                # Sort: practical doubles first, then specialty rooms, then teacher availability constraint density
                def get_item_difficulty(item):
                    alloc = item["alloc"]
                    score = 0
                    if item["type"] == "double":
                        score += 100
                    if alloc.required_room_type != 'Classroom':
                        score += 50
                    avail_limits = teacher_availabilities.get(alloc.teacher.full_name.upper().strip())
                    if avail_limits:
                        score += (5 - len(avail_limits['days'])) * 10
                    return -score

                schedule_items.sort(key=get_item_difficulty)

                # Initialize local grid for backtracking
                class_slots = {}  # (day, period_no) -> entry_dict

                # Populate class_slots with already existing locked entries for this class
                locked_entries = ClassTimetableEntry.objects.filter(
                    class_id=school_class.class_id,
                    academic_year=academic_year,
                    is_locked=True
                )
                for entry in locked_entries:
                    class_slots[(entry.day_name, entry.period_no)] = {
                        "subject_id": entry.subject_id,
                        "subject_name": entry.subject_name,
                        "teacher_name": entry.teacher_name,
                        "room_name": entry.room_name,
                        "is_locked": True
                    }

                backtrack_count = [0]
                max_backtracks = 1000

                def solve(item_index):
                    backtrack_count[0] += 1
                    if backtrack_count[0] > max_backtracks:
                        return False # Cutoff search
                        
                    if item_index >= len(schedule_items):
                        return True

                    item = schedule_items[item_index]
                    alloc = item["alloc"]
                    teacher_name = alloc.teacher.full_name
                    teacher_key = teacher_name.upper().strip()
                    req_room_type = alloc.required_room_type

                    candidate_slots = []
                    for day in days:
                        if alloc.preferred_days:
                            pref_days = [d.strip().lower() for d in alloc.preferred_days.split(",") if d.strip()]
                            if day.lower() not in pref_days:
                                continue

                        for i, p_config in enumerate(lesson_periods):
                            is_morning = i < (len(lesson_periods) / 2)
                            if alloc.preferred_sessions == 'Morning' and not is_morning:
                                continue
                            if alloc.preferred_sessions == 'Afternoon' and is_morning:
                                continue
                            candidate_slots.append((day, p_config, i))

                    random.shuffle(candidate_slots)

                    if item["type"] == "double":
                        for day, p_config, idx in candidate_slots:
                            if idx + 1 >= len(lesson_periods):
                                continue
                            p_config_next = lesson_periods[idx + 1]

                            if p_config_next.period_no - p_config.period_no != 1:
                                continue

                            slot1 = (day, p_config.period_no)
                            slot2 = (day, p_config_next.period_no)

                            if slot1 in class_slots or slot2 in class_slots:
                                continue

                            if (teacher_key, day, p_config.period_no) in booked_teachers:
                                continue
                            if (teacher_key, day, p_config_next.period_no) in booked_teachers:
                                continue

                            # Availability check
                            t_lims = teacher_availabilities.get(teacher_key)
                            if t_lims:
                                if day.lower() not in t_lims['days']:
                                    continue
                                if str(p_config.period_no) not in t_lims['periods'] or str(p_config_next.period_no) not in t_lims['periods']:
                                    continue

                            # Workload check
                            if not check_workload_in_memory(teacher_key, day, added_periods=2):
                                continue

                            # Find available rooms
                            room1 = find_room_in_memory(school_class.class_id, req_room_type, day, p_config.period_no)
                            room2 = find_room_in_memory(school_class.class_id, req_room_type, day, p_config_next.period_no)

                            # Tentatively allocate
                            class_slots[slot1] = {
                                "subject_id": alloc.subject.subject_id,
                                "subject_name": alloc.subject.subject_name,
                                "teacher_name": teacher_name,
                                "room_name": room1,
                                "is_locked": False
                            }
                            class_slots[slot2] = {
                                "subject_id": alloc.subject.subject_id,
                                "subject_name": alloc.subject.subject_name,
                                "teacher_name": teacher_name,
                                "room_name": room2,
                                "is_locked": False
                            }
                            booked_teachers.add((teacher_key, day, p_config.period_no))
                            booked_teachers.add((teacher_key, day, p_config_next.period_no))
                            booked_rooms.add((room1.upper().strip(), day, p_config.period_no))
                            booked_rooms.add((room2.upper().strip(), day, p_config_next.period_no))
                            teacher_weekly_workload[teacher_key] = teacher_weekly_workload.get(teacher_key, 0) + 2
                            teacher_daily_workload[(teacher_key, day)] = teacher_daily_workload.get((teacher_key, day), 0) + 2

                            if solve(item_index + 1):
                                return True

                            # Backtrack
                            del class_slots[slot1]
                            del class_slots[slot2]
                            booked_teachers.remove((teacher_key, day, p_config.period_no))
                            booked_teachers.remove((teacher_key, day, p_config_next.period_no))
                            booked_rooms.remove((room1.upper().strip(), day, p_config.period_no))
                            booked_rooms.remove((room2.upper().strip(), day, p_config_next.period_no))
                            teacher_weekly_workload[teacher_key] = max(0, teacher_weekly_workload.get(teacher_key, 0) - 2)
                            teacher_daily_workload[(teacher_key, day)] = max(0, teacher_daily_workload.get((teacher_key, day), 0) - 2)

                    else:
                        for day, p_config, idx in candidate_slots:
                            slot = (day, p_config.period_no)
                            if slot in class_slots:
                                continue

                            if (teacher_key, day, p_config.period_no) in booked_teachers:
                                continue

                            t_lims = teacher_availabilities.get(teacher_key)
                            if t_lims:
                                if day.lower() not in t_lims['days']:
                                    continue
                                if str(p_config.period_no) not in t_lims['periods']:
                                    continue

                            if not check_workload_in_memory(teacher_key, day, added_periods=1):
                                continue

                            room = find_room_in_memory(school_class.class_id, req_room_type, day, p_config.period_no)

                            class_slots[slot] = {
                                "subject_id": alloc.subject.subject_id,
                                "subject_name": alloc.subject.subject_name,
                                "teacher_name": teacher_name,
                                "room_name": room,
                                "is_locked": False
                            }
                            booked_teachers.add((teacher_key, day, p_config.period_no))
                            booked_rooms.add((room.upper().strip(), day, p_config.period_no))
                            teacher_weekly_workload[teacher_key] = teacher_weekly_workload.get(teacher_key, 0) + 1
                            teacher_daily_workload[(teacher_key, day)] = teacher_daily_workload.get((teacher_key, day), 0) + 1

                            if solve(item_index + 1):
                                return True

                            del class_slots[slot]
                            booked_teachers.remove((teacher_key, day, p_config.period_no))
                            booked_rooms.remove((room.upper().strip(), day, p_config.period_no))
                            teacher_weekly_workload[teacher_key] = max(0, teacher_weekly_workload.get(teacher_key, 0) - 1)
                            teacher_daily_workload[(teacher_key, day)] = max(0, teacher_daily_workload.get((teacher_key, day), 0) - 1)

                    return False

                solved = solve(0)

                if solved or len(class_slots) > len(locked_entries):
                    for (day, p_no), data in class_slots.items():
                        if data.get("is_locked", False):
                            continue
                            
                        p_config = TimetablePeriodConfig.objects.get(period_no=p_no)
                        
                        ClassTimetableEntry.objects.create(
                            class_id=school_class.class_id,
                            academic_year=academic_year,
                            day_name=day,
                            day_order=day_orders[day],
                            period_no=p_no,
                            start_time=p_config.start_time,
                            end_time=p_config.end_time,
                            subject_id=data["subject_id"],
                            subject_name=data["subject_name"],
                            teacher_name=data["teacher_name"],
                            room_name=data["room_name"],
                            is_locked=False,
                            generated_at=timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                        created_count += 1
                else:
                    skipped_count += 1

        return {
            "created": created_count,
            "skipped": skipped_count,
            "status": "Success"
        }
