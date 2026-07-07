from timetable.models import Room
from students.models import Pupil

class RoomAllocator:
    @staticmethod
    def get_class_size(class_id):
        return Pupil.objects.filter(class_id=class_id, status="Active").count()

    @staticmethod
    def find_suitable_room(class_id, required_room_type, day_name, period_no, academic_year, booked_rooms):
        """
        Finds an available room of the required type for the given class and slot.
        - required_room_type: Classroom, Science Lab, Computer Lab, etc.
        - booked_rooms: set of (room_name, day_name, period_no) that are already allocated.
        """
        class_size = RoomAllocator.get_class_size(class_id)
        
        # Query all rooms matching the type, sorted by capacity (best fit first)
        candidate_rooms = Room.objects.filter(room_type=required_room_type).order_by('capacity')
        
        if not candidate_rooms.exists():
            # Fallback to standard classroom if no lab or specific type exists
            candidate_rooms = Room.objects.filter(room_type='Classroom').order_by('capacity')
            if not candidate_rooms.exists():
                return f"Classroom {class_id}"  # Fallback room name

        # 1. Try to find a room that matches capacity and is not booked
        for room in candidate_rooms:
            if room.capacity >= class_size:
                room_key = (room.room_name, day_name, period_no)
                if room_key not in booked_rooms:
                    return room.room_name
                    
        # 2. If no room fits capacity exactly, try any room of the type that is not booked
        for room in candidate_rooms:
            room_key = (room.room_name, day_name, period_no)
            if room_key not in booked_rooms:
                return room.room_name

        # 3. Last resort fallback
        return candidate_rooms[0].room_name
