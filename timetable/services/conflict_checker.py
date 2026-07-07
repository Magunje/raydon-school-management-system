from academics.models import ClassTimetableEntry
from timetable.models import TeacherAvailability, Room
from accounts.models import UserProfile

class ConflictChecker:
    @staticmethod
    def check_conflicts(class_id, teacher_name, room_name, day_name, period_no, academic_year, exclude_id=None):
        """
        Checks for any schedule conflicts for a prospective slot.
        Returns a list of dictionaries, each describing a conflict.
        """
        conflicts = []
        
        # 1. Class Period Overlap: One class having two subjects at the same time
        class_overlap_query = ClassTimetableEntry.objects.filter(
            class_id=class_id,
            day_name=day_name,
            period_no=period_no,
            academic_year=academic_year
        )
        if exclude_id:
            class_overlap_query = class_overlap_query.exclude(timetable_id=exclude_id)
            
        class_overlap = class_overlap_query.first()
        if class_overlap:
            conflicts.append({
                "type": "Class Period Overlap",
                "message": f"Class is already scheduled for '{class_overlap.subject_name}' with teacher '{class_overlap.teacher_name}'."
            })

        # 2. Teacher Double Booking: One teacher teaching two classes at the same time
        if teacher_name:
            teacher_overlap_query = ClassTimetableEntry.objects.filter(
                teacher_name__iexact=teacher_name.strip(),
                day_name=day_name,
                period_no=period_no,
                academic_year=academic_year
            )
            if exclude_id:
                teacher_overlap_query = teacher_overlap_query.exclude(timetable_id=exclude_id)
                
            teacher_overlap = teacher_overlap_query.first()
            if teacher_overlap:
                from students.models import SchoolClass
                try:
                    c_obj = SchoolClass.objects.get(class_id=teacher_overlap.class_id)
                    c_name = c_obj.class_name
                except SchoolClass.DoesNotExist:
                    c_name = f"Class ID {teacher_overlap.class_id}"
                
                conflicts.append({
                    "type": "Teacher Double Booking",
                    "message": f"Teacher '{teacher_name}' is already teaching class '{c_name}' at this time."
                })

            # 3. Teacher Availability Violation
            try:
                profile = UserProfile.objects.get(full_name__iexact=teacher_name.strip(), role='Teacher')
                availability = TeacherAvailability.objects.filter(teacher=profile).first()
                if availability:
                    # check days
                    avail_days = [d.strip().lower() for d in availability.available_days.split(",") if d.strip()]
                    if day_name.lower() not in avail_days:
                        conflicts.append({
                            "type": "Teacher Unavailable",
                            "message": f"Teacher '{teacher_name}' is not marked available on {day_name}."
                        })
                    # check periods
                    avail_periods = [p.strip() for p in availability.available_periods.split(",") if p.strip()]
                    if str(period_no) not in avail_periods:
                        conflicts.append({
                            "type": "Teacher Unavailable",
                            "message": f"Teacher '{teacher_name}' is not marked available during Period {period_no}."
                        })
            except UserProfile.DoesNotExist:
                pass

        # 4. Room Double Booking: One room allocated to two classes simultaneously
        if room_name:
            room_overlap_query = ClassTimetableEntry.objects.filter(
                room_name__iexact=room_name.strip(),
                day_name=day_name,
                period_no=period_no,
                academic_year=academic_year
            )
            if exclude_id:
                room_overlap_query = room_overlap_query.exclude(timetable_id=exclude_id)
                
            room_overlap = room_overlap_query.first()
            if room_overlap:
                from students.models import SchoolClass
                try:
                    c_obj = SchoolClass.objects.get(class_id=room_overlap.class_id)
                    c_name = c_obj.class_name
                except SchoolClass.DoesNotExist:
                    c_name = f"Class ID {room_overlap.class_id}"
                    
                conflicts.append({
                    "type": "Room Double Booking",
                    "message": f"Room '{room_name}' is already allocated to class '{c_name}' at this time."
                })

        return conflicts
