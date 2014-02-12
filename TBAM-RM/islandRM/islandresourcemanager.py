from datetime import datetime, timedelta
from pprint import pprint
import xmlrpclib
import os

from amsoil.config import expand_amsoil_path
import amsoil.core.log
import amsoil.core.log
import amsoil.core.pluginmanager as pm
import amsoil.core.pluginmanager as pm
import islandrmexceptions as islandex

import pickle



import httplib
import socket
import sys
import M2Crypto.SSL
from web.db import database


logger = amsoil.core.log.getLogger('islandresourcemanager')

#If set to False: avoid the connection to the TBAM Agent. 
CONN_WITH_AGENT = False

if(CONN_WITH_AGENT):
    CLIENT_KEY_PATH = "/root/AlienAM/Original/.gcf/alice-key.pem"
    CLIENT_CERT_PATH =  "/root/AlienAM/Original/.gcf/alice-cert.pem"


worker = pm.getService('worker')
config = pm.getService("config")
schedule = pm.getService('schedule')
scheduleex = pm.getService('scheduleexceptions')

class islandResourceManager(object):
    
    #86400 sec = 24 hours: default expiry time is not given
    #604800 sec = 7 days: default delta between start_time and stop_time is stop_time is not given.
    #see scheduling plugin for more information
    aggregate_schedule = schedule('aggregate', 604800, 86400)
    
    
    AGGREGATE_CHECK_INTERVAL = 3600  # sec = 1 hour
    ALLOCATE_CHECK_INTERVAL = 3600 # sec = 1 hour
   
    def __init__(self):
        super(islandResourceManager, self).__init__()
        #Check the starting or expiration of the experiment 
        worker.addAsReccurring("islandresourcemanager", "check_provision", None, self.AGGREGATE_CHECK_INTERVAL)
        #Check for the expiration of a allocate (not provisioned).
        worker.addAsReccurring("islandresourcemanager", "check_allocate", None, self.ALLOCATE_CHECK_INTERVAL)
        
        
    def getSws(self):
        #TODO: The client provides a Secure RPC connection with the TBAM Agent. 
        #We can keep this call (but the certs must be generated) or we can integrate the TBAM Agent in the AMsoil
        if(CONN_WITH_AGENT):
            client = make_client("https://localhost:8234", CLIENT_KEY_PATH, CLIENT_CERT_PATH);
            
            try:
                sws = client.getSws()
            except Exception, err:
                raise islandex.IslandRMRPCError(err)
        else:
            sws = ["00:00:00:00:00:00:00", "00:00:00:00:00:00:01"]
        return sws  

    def getLinks(self):
        #TODO: The client provides a Secure RPC connection with the TBAM Agent. 
        #We can keep this call (but the certs must be generated) or we can integrate the TBAM Agent in the AMsoil
        if(CONN_WITH_AGENT):
            client = make_client("https://localhost:8234", CLIENT_KEY_PATH, "/root/AlienAM/Original/.gcf/alice-cert.pem");
            
            try:
                links = client.getLinks()
            except Exception, err:
                raise islandex.IslandRMRPCError(err)
        else:
            links = []
            links.append({"dpidSrc" : "00:00:00:00:00:00:00", "portSrc" : 5, "dpidDst":"00:00:00:00:00:00:01", "portDst": 1})
            links.append({"dpidSrc" : "00:00:00:00:00:00:00", "portSrc" : 6, "dpidDst":"00:00:00:00:00:00:01", "portDst": 7})
        return links

    def getAvailability(self):
        #it returns only the timeslot and the slice_id. It is possible to return also other parameters
        scheduleTimeSlot = self.aggregate_schedule.find()
        reservedTimeSlot = []
        
        for entry in scheduleTimeSlot:
            reservedTimeSlot.append(TimeSlot(slice_id=entry.slice_id, start_time=entry.start_time, end_time=entry.end_time))   
        
        return reservedTimeSlot
    
    def checkAvailability(self, start_time, end_time):
        slot = self.aggregate_schedule.find(start_time=start_time, end_time=end_time)
        if slot:
            return False
        else:
            return True
    
    
    def reserve_aggregate(self, slice_id, owner_uuid, owner_mail, start_time, end_time, expiry_time): 
        search = self.aggregate_schedule.find(slice_id=slice_id)
        if(search):
            raise islandex.IslandRMNotUnivocal(slice_id)
        
        reserve = self.aggregate_schedule.reserve(resource_id="CN2", resource_spec=None, slice_id=slice_id, user_id=owner_uuid, start_time=start_time, end_time=end_time, allocate=True, started=False, expiry_time=expiry_time)
        
        return reserve
    
    def approve_aggregate(self, client_cert, slice_id, owner_uuid, owner_mail, start_time, end_time, VLANs, controller): 
        search = self.aggregate_schedule.find(slice_id=slice_id)
        if(len(search) > 1):
            raise islandex.IslandRMMoreSliceWithSameID(slice_id)
        if(not search):
            raise islandex.IslandRMNotAllocated(slice_id)
        for entry in search:
            if (not entry.get("allocate")):
            # Update of a provision
                # Checks if timeslot is equal; If they are not equal, it controls that is available.
                if((not entry.start_time == start_time) or (not entry.end_time == end_time)):
                        
                    if(not self.checkAvailability(start_time, end_time)):
                        raise islandex.IslandRMAlreadyReserved(start_time, end_time)
                
                if(not entry.get("started")):
                    # If the experiment is not started, it updates only the db.
                    update = self.aggregate_schedule.update(entry.reservation_id, resource_spec={"VLANs" : VLANs, "controller" : controller, "client_cert" : client_cert}, start_time=start_time, end_time=end_time, allocate=False, started=False)
                    
                else:
                    # If the experiment is started, I need to propagate the update through the TBAM Agent if there is an
                    # update of VLANs or Contoller or client_pub_cert
                    
                    #TODO: The client provides a Secure RPC connection with the TBAM Agent. 
                    #We can keep this call (but the certs must be generated) or we can integrate the TBAM Agent in the AMsoil
                    client = make_client("https://localhost:8234", CLIENT_KEY_PATH, CLIENT_CERT_PATH);

                    if(not entry.resource_spec.get("VLANs") == VLANs):
                        if(CONN_WITH_AGENT):                    
                            try:
                                if not entry.resource_spec.get("VLANs") is None:
                                    client.remOvS(entry.resource_spec.get("VLANs"))
                                if not VLANs is None:
                                    client.setOvS(VLANs)
                            except Exception, err:
                                raise islandex.IslandRMRPCError(err)
                        
                    if(not entry.resource_spec.get("controller") == controller):
                        if(CONN_WITH_AGENT):
                            try:
                                if not entry.resource_spec.get("controller") is None: 
                                    client.remTCPProxy(entry.resource_spec.get("controller"))
                                if not controller is None:
                                    client.setTCPProxy(controller)
                            except Exception, err:
                                raise islandex.IslandRMRPCError(err)
                        
                    if(not entry.resource_spec.get("client_cert") == client_cert):
                        if(CONN_WITH_AGENT):
                            try:
                                if not entry.resource_spec.get("client_cert") is None:
                                    client.remUserAuth(entry.resource_spec.get("client_cert"))
                                if not client_cert is None:
                                    client.setUserAuth(client_cert)
                            except Exception, err:
                                raise islandex.IslandRMRPCError(err)
                        
                        
                        
                    update = self.aggregate_schedule.update(entry.reservation_id, resource_spec={"VLANs" : VLANs, "controller" : controller, "client_cert" : client_cert}, start_time=start_time, end_time=end_time, allocate=False, started=False)
                    
                return update
            else:
                # Previous allocation found            
                # It checks that there is not difference between allocate and provision: the 
                # time slot and the owner _uuid must be the same. 
                if(entry.start_time == start_time and entry.end_time == end_time and entry.user_id == owner_uuid):
                    
                    reserve = self.aggregate_schedule.update(entry.reservation_id, resource_spec={"VLANs" : VLANs, "controller" : controller, "client_cert" : client_cert}, start_time=start_time, end_time=end_time, allocate=False, started=False)
                    
                else: raise islandex.IslandRMNotAllocated(slice_id)
            return reserve
    
    def delete_aggregate(self, slice_id):

        search = self.aggregate_schedule.find(slice_id=slice_id)
        if(len(search) > 1):
            raise islandex.IslandRMMoreSliceWithSameID(slice_id)
        if(not search):
            raise islandex.IslandRMNotAllocated(slice_id)
        
        if(CONN_WITH_AGENT):
            client = make_client("https://localhost:8234", CLIENT_KEY_PATH, CLIENT_CERT_PATH);
        for entry in search:
            #TODO: The client provides a Secure RPC connection with the TBAM Agent. 
            #We can keep this call (but the certs must be generated) or we can integrate the TBAM Agent in the AMsoil
            if(CONN_WITH_AGENT):
                try:
                    if not entry.resource_spec.get("controller") is None:
                        client.remTCPProxy(entry.resource_spec.get("controller"))
                    if not entry.resource_spec.get("VLANs") is None:
                        client.remOvS(entry.resource_spec.get("VLANs"))
                    if not entry.resource_spec.get("client_cert") is None:
                        client.remUserAuth(entry.resource_spec.get("client_cert"))
                except Exception, err:
                    raise islandex.IslandRMRPCError(err) 
            self.aggregate_schedule.cancel(entry.reservation_id)
        
        return entry
    
    def status_island(self, slice_id):
        
        search = self.aggregate_schedule.find(slice_id=slice_id)
        if(len(search) > 1):
            raise islandex.IslandRMMoreSliceWithSameID(slice_id)
        if(not search):
            raise islandex.IslandRMNotAllocated(slice_id)
        
        for entry in search:
            return entry
        return None
    
    @worker.outsideprocess
    def check_provision(self, params):
        print("check provision")
        #TODO: The client provides a Secure RPC connection with the TBAM Agent. 
        #We can keep this call (but the certs must be generated) or we can integrate the TBAM Agent in the AMsoil
        if(CONN_WITH_AGENT):
            client = make_client("https://localhost:8234", CLIENT_KEY_PATH, CLIENT_CERT_PATH);
        
        list = self.aggregate_schedule.find(allocate=False, started=True)
            
        for entry in list:
            if(entry.end_time < datetime.utcnow()):
                print("stopping %s", entry.slice_id)
                
                if(CONN_WITH_AGENT):
                    try:
    
                        if not entry.resource_spec.get("controller") is None:
                            client.remTCPProxy(entry.resource_spec.get("controller"))
                        if not entry.resource_spec.get("VLANs") is None:
                            client.remOvS(entry.resource_spec.get("VLANs"))
                        if not entry.resource_spec.get("client_cert") is None:
                            client.remUserAuth(entry.resource_spec.get("client_cert"))
                    except Exception, err:
                            raise islandex.IslandRMRPCError(err)    
                self.aggregate_schedule.cancel(entry.reservation_id)
        
        list = self.aggregate_schedule.find(start_time=datetime.utcnow(), allocate=False, started=False)
        for entry in list:
            print("starting %s", entry.slice_id)
                            
            if(CONN_WITH_AGENT):

                try:
                    if not entry.resource_spec.get("controller") is None:
                        client.setTCPProxy(entry.resource_spec.get("controller"))
                    if not entry.resource_spec.get("VLANs") is None:
                        client.setOvS(entry.resource_spec.get("VLANs"))
                    if not entry.resource_spec.get("client_cert") is None:
                        client.setUserAuth(entry.resource_spec.get("client_cert"))
                except Exception, err:
                    raise islandex.IslandRMRPCError(err)
            self.aggregate_schedule.update(entry.reservation_id, started=True)
        
        return
 
    @worker.outsideprocess
    def check_allocate(self, params):
        # It checks for the expiration of a allocate (not provisioned)
        list = self.aggregate_schedule.find(allocate=True, expiry_time=datetime.utcnow())
        for entry in list:
            self.aggregate_schedule.cancel(entry.reservation_id)
            print("expire time for allocate %s", entry.slice_id)
        return
    


class TimeSlot(object):
    slice_id = "";
    start_time = 0;
    end_time = 0;
    def __init__(self, slice_id, start_time, end_time):
        self.start_time = start_time
        self.end_time = end_time
        self.slice_id = slice_id
    
class SafeTransportWithCert(xmlrpclib.SafeTransport):
    def __init__(self, use_datetime=0, keyfile=None, certfile=None,
                 timeout=None):
        xmlrpclib.SafeTransport.__init__(self, use_datetime)
        self.__x509 = dict()
        if keyfile:
            self.__x509['key_file'] = keyfile
        if certfile:
            self.__x509['cert_file'] = certfile
        self._timeout = timeout

    def make_connection(self, host):
        host_tuple = (host, self.__x509)
        conn = xmlrpclib.SafeTransport.make_connection(self, host_tuple)
        if self._timeout:
            conn._conn.timeout = self._timeout
        return conn
    

    
def make_client(url, keyfile, certfile, verbose=True, timeout=None):
    """Create an SSL connection to an XML RPC server.
        Returns the XML RPC server proxy.
    """
    cert_transport = SafeTransportWithCert(keyfile=keyfile, certfile=certfile,
                                           timeout=timeout)
    return xmlrpclib.ServerProxy(url, transport=cert_transport,
                                 verbose=verbose)
