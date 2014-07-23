from datetime import datetime, timedelta
import time
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
    CLIENT_KEY_PATH = "/root/.gcf/alice-key.pem"
    CLIENT_CERT_PATH =  "/root/.gcf/alice-cert.pem"

OFGW_ADDRESS = "localhost"
OFGW_PORT = 8234

worker = pm.getService('worker')
config = pm.getService("config")
schedule = pm.getService('schedule')
scheduleex = pm.getService('scheduleexceptions')

class islandResourceManager(object):
    
    #604800 sec = 7 days: default delta between start_time and stop_time is stop_time is not given.
    #see scheduling plugin for more information
    aggregate_schedule = schedule('aggregate', 604800)
    

    AGGREGATE_CHECK_INTERVAL = 3600  # sec = 1 hour
   
    def __init__(self):
        super(islandResourceManager, self).__init__()
        #Check the starting or expiration of the experiment 
        worker.addAsReccurring("islandresourcemanager", "check_provision", None, self.AGGREGATE_CHECK_INTERVAL)
        
    def getSws(self):
        #TODO: The client provides a Secure RPC connection with the TBAM Agent. 
        #We can keep this call (but the certs must be generated) or we can integrate the TBAM Agent in the AMsoil
        if(CONN_WITH_AGENT):
            client = make_client("https://%s:%d" %(OFGW_ADDRESS, OFGW_PORT), CLIENT_KEY_PATH, CLIENT_CERT_PATH);
            
            try:
                sws = client.getSws()
            except Exception, err:
                    raise islandex.IslandRMRPCError(err)
        else:
            sws = []
            sws.append({"dipd" : "00:00:00:00:00:00:00"})
            sws.append({"dipd" : "00:00:00:00:00:00:01"})
        return sws  

    def getLinks(self):
        #TODO: The client provides a Secure RPC connection with the TBAM Agent. 
        #We can keep this call (but the certs must be generated) or we can integrate the TBAM Agent in the AMsoil
        if(CONN_WITH_AGENT):
            client = make_client("https://%s:%d" %(OFGW_ADDRESS, OFGW_PORT), CLIENT_KEY_PATH, CLIENT_CERT_PATH);
            
            try:
                links = client.getLinks()
            except Exception, err:
                raise islandex.IslandRMRPCError(err)
        else:
            links = []
            #links.append("00:00:00:00:00:00:00")
            links.append({"dpidSrc" : "00:00:00:00:00:00:00", "portSrc" : "5", "dpidDst" : "00:00:00:00:00:00:01", "portDst": "1"})
            links.append({"dpidSrc" : "00:00:00:00:00:00:00", "portSrc" : "6", "dpidDst" : "00:00:00:00:00:00:01", "portDst": "7"})
        return links

    def getAvailability(self):
        #it returns only the timeslot and the slice_urn. It is possible to return also other parameters
        scheduleTimeSlot = self.aggregate_schedule.find()
        reservedTimeSlot = []
        
        for entry in scheduleTimeSlot:
            reservedTimeSlot.append({"slice_urn" : entry.slice_urn, "start_time" : entry.start_time.strftime('%d/%m/%Y %H:%M:%S'), 
                                     "end_time" : entry.end_time.strftime('%d/%m/%Y %H:%M:%S')})  

        
        return reservedTimeSlot
    
    def checkAvailability(self, start_time, end_time):
        slot = self.aggregate_schedule.find(start_time=start_time, end_time=end_time)
        if slot:
            return False
        else:
            return True
    
    
    def reserve_aggregate(self, slice_urn, owner_uuid, owner_mail, start_time, end_time, VLANs, controller, projectInfo): 
        search = self.aggregate_schedule.find(slice_urn=slice_urn)
        start_time = datetime.strptime(start_time, '%d/%m/%Y %H:%M:%S')
        end_time = datetime.strptime(end_time, '%d/%m/%Y %H:%M:%S')
        #new allocate: insert in the database
        if(not search):
            try:
                reserve = self.aggregate_schedule.reserve(resource_id="Alien", slice_urn=slice_urn, user_id=str(owner_uuid),
                                                      start_time=start_time, end_time=end_time, allocate=True, started=False,
                                                      resource_spec={"VLANs" : VLANs, "controller" : controller, "projectInfo" : projectInfo})
            except scheduleex.ScheduleOverbookingError as e:
                    raise islandex.IslandRMAlreadyReserved(start_time = start_time, end_time = end_time)
            reserve.start_time = reserve.start_time.strftime('%d/%m/%Y %H:%M:%S')
            reserve.end_time = reserve.end_time.strftime('%d/%m/%Y %H:%M:%S')
            
            return reserve
        #if there are more approved entries, raise exception. (Should be impossible)
        elif(len(search) > 1):
            raise islandex.IslandRMMoreSliceWithSameID(slice_urn)
        
        #if an allocate exists raise exception: 
        elif(search[0].allocate):
            raise islandex.IslandRMNotUnivocal(slice_urn)
        
        #this is an update of an approved entry
        else:
            # Update of a approved entry
                # Checks if timeslot is equal; If they are not equal, it controls that is available.
                if((not search[0].start_time == start_time) or (not search[0].end_time == end_time)):
                    list = self.aggregate_schedule.find(start_time=start_time, end_time=end_time)
                    #More reservation...
                    if(len(list) > 1):
                        raise islandex.IslandRMAlreadyReserved(start_time, end_time)
                    #Control if the reservation is the same
                    elif (len(list) == 1):
                        if(list[0].slice_urn != slice_urn):
                            raise islandex.IslandRMAlreadyReserved(start_time, end_time)
                
                if(not search[0].started):
                    print("not started")
                    # If the experiment is not started, it updates only the db.
                    update = self.aggregate_schedule.update(search[0].reservation_id, resource_spec={"VLANs" : VLANs, "controller" : controller, "projectInfo" : projectInfo}, 
                                                            start_time=start_time, end_time=end_time)
                #Started but reservation moved to the feature
                elif(start_time > datetime.utcnow()):
                    if(CONN_WITH_AGENT):
                        client = make_client("https://%s:%d" %(OFGW_ADDRESS, OFGW_PORT), CLIENT_KEY_PATH, CLIENT_CERT_PATH);
                        self.remove_settings(client, search[0])
                    update = self.aggregate_schedule.update(search[0].reservation_id, resource_spec={"VLANs" : VLANs, "controller" : controller, "projectInfo" : projectInfo}, 
                                                            start_time=start_time, end_time=end_time)
                    
                #Only started
                else:
                    # If the experiment is started, I need to propagate the update through the TBAM Agent if there is an
                    # update of VLANs or Contoller or client_pub_cert
                    
                    #TODO: The client provides a Secure RPC connection with the TBAM Agent. 
                    #We can keep this call (but the certs must be generated) or we can integrate the TBAM Agent in the AMsoil
                    if(CONN_WITH_AGENT):
                        client = make_client("https://%s:%d" %(OFGW_ADDRESS, OFGW_PORT), CLIENT_KEY_PATH, CLIENT_CERT_PATH);

                    if(not search[0].resource_spec.get("VLANs") == VLANs):
                        if(CONN_WITH_AGENT):                    
                            try:
                                if not search[0].resource_spec.get("VLANs") is None:
                                    client.remOvS(search[0].resource_spec.get("VLANs"))
                                if not VLANs is None:
                                    client.setOvS(VLANs)
                            except Exception, err:
                                raise islandex.IslandRMRPCError(err)
                        
                    if(not search[0].resource_spec.get("controller") == controller):
                        if(CONN_WITH_AGENT):
                            try:
                                if not search[0].resource_spec.get("controller") is None: 
                                    client.remTCPProxy(search[0].resource_spec.get("controller"))
                                if not controller is None:
                                    client.setTCPProxy(controller)
                            except Exception, err:
                                raise islandex.IslandRMRPCError(err)
                        
                    if(not search[0].resource_spec.get("projectInfo") == projectInfo):
                        if(CONN_WITH_AGENT):
                            try:
                                if not search[0].resource_spec.get("projectInfo") is None:
                                    client.remUserAuth(search[0].resource_spec.get("projectInfo"))
                                if not projectInfo is None:
                                    client.setUserAuth(projectInfo)
                            except Exception, err:
                                raise islandex.IslandRMRPCError(err)
                        
                        
                        
                    update = self.aggregate_schedule.update(search[0].reservation_id, resource_spec={"VLANs" : VLANs, "controller" : controller, "projectInfo" : projectInfo}, 
                                                            start_time=start_time, end_time=end_time)
                update.start_time = update.start_time.strftime('%d/%m/%Y %H:%M:%S')
                update.end_time = update.end_time.strftime('%d/%m/%Y %H:%M:%S')
                return update        
        
    
    def approve_aggregate(self, slice_urn): 
        search = self.aggregate_schedule.find(slice_urn=slice_urn)
        if(len(search) > 1):
            raise islandex.IslandRMMoreSliceWithSameID(slice_urn)
        if(not search):
            raise islandex.IslandRMNotAllocated(slice_urn)
        
        # Previous allocation found                    
        # It checks that there is not difference between allocate and provision: the 
        # time slot and the owner _uuid must be the same. 
        approve = self.aggregate_schedule.update(search[0].reservation_id, allocate=False, started=False)
        
        list = self.aggregate_schedule.find(allocate=False)
        print("approved:")
        for entry in list:
            print(entry.slice_urn)
        
        approve.start_time = approve.start_time.strftime('%d/%m/%Y %H:%M:%S')
        approve.end_time = approve.end_time.strftime('%d/%m/%Y %H:%M:%S')
        return approve
    
    def delete_aggregate(self, slice_urn):

        search = self.aggregate_schedule.find(slice_urn=slice_urn)
        if(len(search) > 1):
            raise islandex.IslandRMMoreSliceWithSameID(slice_urn)
        if(not search):
            raise islandex.IslandRMNotAllocated(slice_urn)
        
        if(CONN_WITH_AGENT):
            client = make_client("https://%s:%d" %(OFGW_ADDRESS, OFGW_PORT), CLIENT_KEY_PATH, CLIENT_CERT_PATH);
        for entry in search:
            #TODO: The client provides a Secure RPC connection with the TBAM Agent. 
            #We can keep this call (but the certs must be generated) or we can integrate the TBAM Agent in the AMsoil
            if(entry.started):
                if(CONN_WITH_AGENT):
                    self.remove_settings(client, entry)
                    removed = self.aggregate_schedule.cancel(entry.reservation_id)
            else:
                removed = self.aggregate_schedule.cancel(entry.reservation_id)
        
        removed.start_time = removed.start_time.strftime('%d/%m/%Y %H:%M:%S')
        removed.end_time = removed.end_time.strftime('%d/%m/%Y %H:%M:%S')
        return removed
    
    def status_island(self, slice_urn):
        
        search = self.aggregate_schedule.find(slice_urn=slice_urn)
        if(len(search) > 1):
            raise islandex.IslandRMMoreSliceWithSameID(slice_urn)
        if(not search):
            raise islandex.IslandRMNotAllocated(slice_urn)
        
        search.start_time = search.start_time.strftime('%d/%m/%Y %H:%M:%S')
        search.end_time = search.end_time.strftime('%d/%m/%Y %H:%M:%S')
        return search[0]

    @worker.outsideprocess
    def check_provision(self, params):
        #TODO: The client provides a Secure RPC connection with the TBAM Agent. 
        #We can keep this call (but the certs must be generated) or we can integrate the TBAM Agent in the AMsoil
        if(CONN_WITH_AGENT):
            client = make_client("https://%s:%d" %(OFGW_ADDRESS, OFGW_PORT), CLIENT_KEY_PATH, CLIENT_CERT_PATH);
        
        list = self.aggregate_schedule.find(allocate=False, started=True)
            
        if(list):
            if(list[0].end_time < datetime.utcnow()):
                print("stopping %s", list[0].slice_urn)
                
                if(CONN_WITH_AGENT):
                    self.remove_settings(client, list[0])
                
                self.aggregate_schedule.cancel(list[0].reservation_id)
        
        list = self.aggregate_schedule.find(start_time=datetime.utcnow(), allocate=False, started=False)
        if(list):
            print("starting %s", list[0].slice_urn)
                            
            if(CONN_WITH_AGENT):

                try:
                    if not list[0].resource_spec.get("controller") is None:
                        client.setTCPProxy(list[0].resource_spec.get("controller"))
                    if not list[0].resource_spec.get("VLANs") is None:
                        client.setOvS(list[0].resource_spec.get("VLANs"))
                    if not list[0].resource_spec.get("projectInfo") is None:
                        client.setUserAuth(list[0].resource_spec.get("projectInfo"))
                except Exception, err:
                    raise islandex.IslandRMRPCError(err)
            self.aggregate_schedule.update(list[0].reservation_id, started=True)
        
        return
    
    
    def remove_settings(self, client, entry):
        try:
            if not entry.resource_spec.get("controller") is None:
                client.remTCPProxy(entry.resource_spec.get("controller"))
            if not entry.resource_spec.get("VLANs") is None:
                client.remOvS(entry.resource_spec.get("VLANs"))
            if not entry.resource_spec.get("projectInfo") is None:
                client.remUserAuth(entry.resource_spec.get("projectInfo"))
        except Exception, err:
            raise islandex.IslandRMRPCError(err)  
        return
                
    
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
