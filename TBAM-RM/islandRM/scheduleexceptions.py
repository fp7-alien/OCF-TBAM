from amsoil.core.exception import CoreException
        
class ScheduleException(CoreException):
    def __init__(self, desc):
        self._desc = desc
    def __str__(self):
        return "Schedule: %s" % (self._desc,)

class ScheduleOverbookingError(ScheduleException):
    def __init__(self, schedule_subject, resource_id, start_time, end_time):
        """All parameters should be strings or be able to str(...) itself."""
        super(ScheduleOverbookingError, self).__init__("There are already reservations for %s during [%s - %s] in the %s schedule." % (str(resource_id), str(start_time), str(end_time), str(schedule_subject)))

class ScheduleNoSuchReservationError(ScheduleException):
    def __init__(self, reservation_id):
        super(ScheduleNoSuchReservationError, self).__init__("Could not find reservation with id %d." % (reservation_id))
        
class ScheduleExpired(ScheduleException):
    def __init__(self, slice_id):
        super(ScheduleExpired, self).__init__("The expire time of reservation with slice id %s is already expired" % (str(slice_id)))
        
class ScheduleNoAllocate(ScheduleException):
    def __init__(self, slice_id):
        super(ScheduleNoAllocate, self).__init__("The field 'allocate' of reservation with slice id %s cannot be None." % (str(slice_id)))