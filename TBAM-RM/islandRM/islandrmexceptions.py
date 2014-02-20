from amsoil.core.exception import CoreException


class IslandRMException(CoreException):
    def __init__(self, desc):
        self._desc = desc
    def __str__(self):
        return "IslandResourceManager: %s" % (self._desc,)

class IslandRMAlreadyReserved(IslandRMException):
    def __init__(self, start_time, end_time):
        super(IslandRMAlreadyReserved, self).__init__("The island is already reserved from %s to %s" % (str(start_time), str(end_time)))

class IslandRMNotAllocated(IslandRMException):
    def __init__(self, slice_id):
        super(IslandRMNotAllocated, self).__init__("The slice %s has not previously allocated or approved" % (str(slice_id)))
        
class IslandRMNotUnivocal(IslandRMException):
    def __init__(self, slice_id):
        super(IslandRMNotUnivocal, self).__init__("The slice_urn %s is already used and it is not yet provisioned" % (str(slice_id)))
        
class IslandRMMoreSliceWithSameID(IslandRMException):
    def __init__(self, slice_id):
        super(IslandRMMoreSliceWithSameID, self).__init__("More slice with same urn %s" % (str(slice_id)))
                
class IslandRMRPCError(IslandRMException):
    def __init__(self, err):
        super(IslandRMRPCError, self).__init__("The connection from TBAM Resource Manager and TBAM Agent returns error: %s" % (err))