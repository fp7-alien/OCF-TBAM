
import amsoil.core.log
import amsoil.core.pluginmanager as pm
from datetime import datetime, timedelta



#logger = amsoil.core.log.getLogger('islanddelegate')

GENIv3DelegateBase = pm.getService('geniv3delegatebase')
geni_ex = pm.getService('geniv3exceptions')
island_ex = pm.getService('islandrmexceptions')



# dhcp_ex = pm.getService('dhcpexceptions')

class ISLANDdelegate(GENIv3DelegateBase):
    """
    """
    
    # URN_PREFIX = 'urn:DHCP_AM' # TODO should also include a changing component, identified by a config key
    
    def __init__(self):
        super(ISLANDdelegate, self).__init__()
        self._resource_manager = pm.getService("islandresourcemanager")
    
    def get_request_extensions_mapping(self):
        """Documentation see [geniv3rpc] GENIv3DelegateBase."""
        return {'aggregate' : 'http://example.com/aggregate'}  # /request.xsd
    
    def get_manifest_extensions_mapping(self):
        """Documentation see [geniv3rpc] GENIv3DelegateBase."""
        return {'aggregate' : 'http://example.com/aggregate'}  # /manifest.xsd
    
    def get_ad_extensions_mapping(self):
        """Documentation see [geniv3rpc] GENIv3DelegateBase."""
        return {'aggregate' : 'http://example.com/aggregate'}  # /ad.xsd
    
    def is_single_allocation(self):
        """Documentation see [geniv3rpc] GENIv3DelegateBase.
        We allow to address single slivers (IPs) rather than the whole slice at once."""
        return False
    
    def get_allocation_mode(self):
        """Documentation see [geniv3rpc] GENIv3DelegateBase.
        We allow to incrementally add new slivers (IPs)."""
        return 'geni_many'

    def list_resources(self, client_cert, credentials, geni_available):
        """Documentation see [geniv3rpc] GENIv3DelegateBase."""
    
         
        # client_urn, client_uuid, client_email = self.auth(client_cert, credentials, None, ('listslices',))
        
        root_node = self.lxml_ad_root()
        E = self.lxml_ad_element_maker('aggregate')
        r = E.resources()
        try:
        
            for sw in self._resource_manager.getSws():
                r.append(E.switch(dpid=sw["dipd"]))
        
            for link in self._resource_manager.getLinks():
                r.append(E.link(dpidSrc=link["dpidSrc"], portSrc=link["portSrc"], dpidDst=link["dpidDst"], portDst=link["portDst"]))
        
            for time in self._resource_manager.getAvailability():
                r.append(E.reservation(slice_urn=time["slice_urn"], start_time=time["start_time"], end_time=time["end_time"])) 
        
        except island_ex.IslandRMRPCError as e:
            raise geni_ex.GENIv3ServerError("%s" % (str(e)))        
                
        root_node.append(r)

        #print(datetime.utcnow())
        
        return self.lxml_to_string(root_node)
        
    
    def describe(self, urns, client_cert, credentials):
        rspec, sliver_list = self.status(urns, client_cert, credentials)
        
        raise geni_ex.GENIv3GeneralError("Method not implemented")
        return None

    def allocate(self, slice_urn, client_cert, credentials, rspec, end_time=None):
        """Documentation see [geniv3rpc] GENIv3DelegateBase."""
        # client_urn, client_uuid, client_email = self.auth(client_cert, credentials, slice_urn, ('createsliver',))
        
        requested_res = {}
        VLANs = {}
        # parse RSpec -> requested_ips
        rspec_root = self.lxml_parse_rspec(rspec)
        for elm in rspec_root.getchildren():
            if not self.lxml_elm_has_request_prefix(elm, 'aggregate'):
                raise geni_ex.GENIv3BadArgsError("RSpec contains unknown elements/namespaces (%s)." % (elm,))
            if (self.lxml_elm_equals_request_tag(elm, 'aggregate', 'slice')):
                requested_res["slice_urn"] = elm.get("slice_urn")
            elif (self.lxml_elm_equals_request_tag(elm, 'aggregate', 'timeslot')):
                requested_res["start_time"] = elm.get("start_time")
                requested_res["end_time"] = elm.get("end_time")
            elif (self.lxml_elm_equals_request_tag(elm, 'aggregate', 'controller')):
                requested_res["controller"] = elm.get("url").strip("tcp:")
            elif (self.lxml_elm_equals_request_tag(elm, 'aggregate', 'VLAN')):
                d = VLANs
                d[elm.get("OFELIA")] = elm.get("ALIEN")
                VLANs = d
            elif (self.lxml_elm_equals_request_tag(elm, 'aggregate', 'project')):
                projectInfo = elm.get("projectID") + "_" + elm.get("projectName")  
            else:
                raise geni_ex.GENIv3BadArgsError("RSpec contains an unknown element (%s)." % (elm,))
        
        if not VLANs:
            VLANs = None
        if not requested_res.get("controller"):
            requested_res["controller"] = None
        
        if not requested_res.get("slice_urn"): 
            raise geni_ex.GENIv3BadArgsError("RSpec does not contain slice_urn")
        if not (requested_res.get("start_time")) or not (requested_res.get("end_time")): 
            raise geni_ex.GENIv3BadArgsError("RSpec does not contain a valid time-slot")
        if not projectInfo:
            raise geni_ex.GENIv3BadArgsError("RSpec must contains a not empty field project")
        try:
            reservation = self._resource_manager.reserve_aggregate(slice_urn, owner_uuid=None, owner_mail=None,
            start_time=requested_res["start_time"], end_time=requested_res["end_time"],
            VLANs=VLANs, controller=requested_res["controller"], projectInfo=projectInfo)
        except island_ex.IslandRMAlreadyReserved as e:
            raise geni_ex.GENIv3AlreadyExistsError("%s" % (str(e)))
        except island_ex.IslandRMNotUnivocal as e:
            raise geni_ex.GENIv3AlreadyExistsError("The slice_urn (%s) is already used and not provisioned" % (str(slice_urn)))
        except island_ex.IslandRMMoreSliceWithSameID as e:
            raise geni_ex.GENIv3GeneralError("%s" % (str(e)))
        except island_ex.IslandRMRPCError as e:
            raise geni_ex.GENIv3ServerError("%s" % (str(e)))
        
        # assemble sliver list
        sliver_list = [self._get_sliver_status_hash(reservation.slice_urn, True, False, "")]
        return self.lxml_to_string(self._get_manifest_rspec(reservation)), sliver_list


    def renew(self, urns, client_cert, credentials, expiration_time, best_effort):
        raise geni_ex.GENIv3GeneralError("Method not implemented")
        return None
    
    
    def provision(self, urns, client_cert, credentials, best_effort, end_time, geni_users):
        for urn in urns:
            if (self.urn_type(urn) == 'slice'):
                # client_urn, client_uuid, client_email = self.auth(client_cert, credentials, urn, ('createsliver',)) # authenticate for each given slice

                try:
                    approved = self._resource_manager.approve_aggregate(slice_urn=urn)
                except island_ex.IslandRMMoreSliceWithSameID as e:
                    raise geni_ex.GENIv3GeneralError("%s" % (str(e)))
                except island_ex.IslandRMNotAllocated as e:
                    raise geni_ex.GENIv3SearchFailedError("%s" % (str(e)))
                except island_ex.IslandRMRPCError as e:
                    raise geni_ex.GENIv3ServerError("%s" % (str(e)))
            else:
                raise geni_ex.GENIv3OperationUnsupportedError('Only slice URNs can be provisioned by this aggregate')
        
        if (not approved):
            raise geni_ex.GENIv3SearchFailedError("There are no allocation with slice_urn %s; perform allocate first" % (str(urn)))
        
        sliver_list = [self._get_sliver_status_hash(approved.slice_urn, True, True, "")]
        return self.lxml_to_string(self._get_manifest_rspec(approved)), sliver_list
        

    def status(self, urns, client_cert, credentials):
        """Documentation see [geniv3rpc] GENIv3DelegateBase."""
        # This code is similar to the provision call.
        raise geni_ex.GENIv3ForbiddenError("Method not implemented")
        return None

    def perform_operational_action(self, urns, client_cert, credentials, action, best_effort):
        # could have similar structure like the provision call
        # You should check for the GENI-default actions like GENIv3DelegateBase.OPERATIONAL_ACTION_xxx
        raise geni_ex.GENIv3OperationUnsupportedError("DHCP leases do not have operational state.")

    def delete(self, urns, client_cert, credentials, best_effort):                
        for urn in urns:
            if (self.urn_type(urn) == 'slice'):
                # client_urn, client_uuid, client_email = self.auth(client_cert, credentials, urn, ('createsliver',)) # authenticate for each given slice

                try:
                    removed = self._resource_manager.delete_aggregate(slice_urn=urn)
                except island_ex.IslandRMMoreSliceWithSameID as e:
                    raise geni_ex.GENIv3GeneralError("%s" % (str(e)))
                except island_ex.IslandRMNotAllocated as e:
                    raise geni_ex.GENIv3SearchFailedError("%s" % (str(e)))
            else:
                raise geni_ex.GENIv3OperationUnsupportedError('Only slice URNs can be provisioned by this aggregate')
        
        if (not removed):
            raise geni_ex.GENIv3SearchFailedError("There are no allocation with slice_urn %s; perform allocate first" % (str(urn)))

        return [self._get_sliver_status_hash(removed.slice_urn, False, False, "")]
    
    def shutdown(self, slice_urn, client_cert, credentials):
        # client_urn, client_uuid, client_email = self.auth(client_cert, credentials, slice_urn, ('shutdown',))
        raise geni_ex.GENIv3GeneralError("Method not implemented")
        return None
    


    # Helper methods
    def _get_sliver_status_hash(self, urn, include_allocation_status=False, include_operational_status=False, error_message=None):
        """Helper method to create the sliver_status return values of allocate and other calls."""
        result = {'geni_sliver_urn' : urn,

                  'geni_expires'    : None,
                  'geni_allocation_status' : self.ALLOCATION_STATE_ALLOCATED}
        if(not include_allocation_status): 
            result['geni_allocation_status'] = self.ALLOCATION_STATE_UNALLOCATED
        if (include_operational_status):  # there is no state to an ip, so we always return ready
            result['geni_operational_status'] = self.OPERATIONAL_STATE_CONFIGURING
        if (error_message):
            result['geni_error'] = error_message
        return result
    
    def _get_manifest_rspec(self, aggregate):
        
        E = self.lxml_manifest_element_maker('aggregate')
        manifest = self.lxml_manifest_root()
        r = E.sliver()
        r.append(E.slice(slice_urn=aggregate["slice_urn"]))
        r.append(E.timeslot(start_time=aggregate["start_time"], end_time=aggregate["end_time"]))
        
        if aggregate.resource_spec.get("VLANs"):
            for key, value in aggregate.resource_spec.get("VLANs").iteritems():
                r.append(E.VLAN(OFELIA=key, ALIEN=value))
        
        if aggregate.resource_spec.get("controller"):   
            r.append(E.controller(url=aggregate.resource_spec.get("controller")))
        manifest.append(r)
        return manifest


