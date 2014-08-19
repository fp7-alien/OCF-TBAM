#OCF-TBAM

The Time-Based Aggregate Manager (TBAM) provides the integration of ALIEN hardware into the [Ofelia Control Framework (OCF)](https://github.com/fp7-ofelia/ocf).

The TBAM is developed using the [AMsoil](https://github.com/motine/AMsoil) framework and the new functionalities are provided through three different plug-ins.

In particular, the TBAM integrates a calendar-like aggregate manager ([TBAM Scheduling Plug-in](https://github.com/fp7-alien/OCF-TBAM/tree/master/AMsoil/src/plugins/schedule)), a resource manager which performs the actual provisioning of the slices (the [TBAM RM](https://github.com/fp7-alien/OCF-TBAM/tree/master/AMsoil/src/plugins/islandRM)) and a module that translates the requests for the RM (the [TBAM Delegate](https://github.com/fp7-alien/OCF-TBAM/tree/master/AMsoil/src/plugins/islandgeni3). The TBAM is connected to ALIEN resources via the [OpenFlow Gateway (OFGW)](https://github.com/fp7-alien/OCF-OFGW) and to the Expedient via the Time Based plugin ([TB Plugin](https://github.com/fp7-alien/OCF-TBPlugin)) as depicted on [figure](https://wiki.man.poznan.pl/alien/img_auth.php/a/a4/Work_distribution.png).

##TBAM Delegate

The Delegate sits between the GENIv3 Handler and the [TBAM Resource Manager](https://github.com/fp7-alien/OCF-TBAM/tree/master/TBAM-RM#tbam-resource-manager). It translates the GENIv3 call to the domain-specific call of the Resource Manager, in particular the [Resource Specification (RSpec)](http://groups.geni.net/geni/wiki/GeniRspec) into Time-based Resource Manager values (and back). Moreover, it handles the Resource Manager’s exceptions and re-throws them as the GENIv3 method API.

###Interfaces

TBAM Delegate methods corresponding to the GENIv3 API are:

- *list_resources(client_cert, credentials, geni_available)*: retrieves the information of the network devices and the reserved time-slots through the Resource Manager. It returns an advertisement RSpec, e.g.:

	```
 	 <rspec aggregate="http://example.com/aggregate" type="advertisement">  
    <aggregate:resources xmlns:aggregate="http://example.com/aggregate">    
        <aggregate:switch dpid="00:00:00:00:00:00:00"/>    
        <aggregate:switch dpid="00:00:00:00:00:00:01"/>    
        <aggregate:link dpidDst="00:00:00:00:00:00:01" dpidSrc="00:00:00:00:00:00:00" portDst="1" portSrc="5"/> 
        <aggregate:link dpidDst="00:00:00:00:00:00:01" dpidSrc="00:00:00:00:00:00:00" portDst="7" portSrc="6"/>  
        <aggregate:reservation end_time="20/02/2014 15:42:30" slice_urn="urn:publicid:IDN+geni:gpo:gcf+slice+testing" start_time="20/02/2014 15:42:00"/>  
    </aggregate:resources>  
</rspec>
	``` 
	The Delegate can throw a *SERVERERROR* GENIv3 exception in case of connection problems between the Resource Manager and the TBAM Agent.
		
- *allocate(slice_urn, client_cert, credentials, rspec, end_time=None)*: translates the RSpec of the allocation to a Resource Manager *reserve_aggregate* request. An example of the RSpec is:

	```
	<rspec type="request"
         xmlns="http://www.geni.net/resources/rspec/3"
         xmlns:xs="http://www.w3.org/2001/XMLSchema-instance"
         xmlns:aggregate="http://example.com/aggregate"
         xs:schemaLocation="http://www.geni.net/resources/rspec/3 http://www.geni.net/resources/rspec/3/ad.xsd http://example.com/dhcp/req.xsd">
        <aggregate:slice  slice_urn="urn:publicid:IDN+geni:gpo:gcf+slice+testing"/>
        <aggregate:timeslot start_time="20/2/2014 15:45:0" end_time="20/2/2014 15:47:00"/>   
        <aggregate:VLAN ALIEN="0xffff" OFELIA="10"/>    
        <aggregate:VLAN ALIEN="30" OFELIA="40"/>
        <aggregate:controller url="192.168.1.2:6633" />   
        <aggregate:project projectID="612cca94-1a7a-4431-87d0-8572399385aa" projectName="Project_test" />  
  	</rspec>
	```

	If the reservation is allocated, the Delegate returns to the GENIv3 Handler both the geni_allocated status and the RSpec containing the information of the allocated resource. If the allocation fails, the Delegate raises one of these GENIv3 standard errors:
	
	- *BADARGS*: indicates a malformed RSpec.
	- *ERROR*: the database contains at least two entries with the same *slice_urn*. This error should never happen, because the Resource Manager is in-charge of controlling the uniqueness of the *slice_urn*.
	- *ALREADYEXISTS*: the error is triggered by either an already used *slice_urn* or an overbooking of the time-slot.
	- *SERVERERROR*: the communication between TBAM Resource Manager and TBAM Agent has encountered a problem.

- *provision(urns, client_cert, credentials, best_effort, end_time, geni_users)*: translates the provision to the Resource Manager *approve_aggregate* request. If the request is approved, the Delegate returns the *geni_allocated* status, the *geni_configuring* operational status and the RSpec equal the one of the *allocate* method. In case of errors the method will raise:
	- *BADARGS*: indicates a malformed RSpec.
	- *ERROR*: the database contains at least two entries with the same *slice_urn*. This error should never happen, because the Resource Manager is in-charge of controlling the uniqueness of the *slice_urn*.
	- *SEARCHFAILED*: a previous allocation having the same *slice_urn* is not found.  
	- *ALREADYEXISTS*: another allocation or approval entry exists with same *slice_urn*
	
- *delete(self, urns, client_cert, credentials, best_effort)*: translates the *delete* to the Resource Manager *delete_aggregate*. It returns a *geni_unallocated* status or it throws:
	- *BADARGS, ERROR*, *ALREADYEXISTS*: equals to the *provision* errors.
	- *SEARCHFAILED*: a previous allocation or approval having the same *slice_urn* is not found.



##TBAM Resource Manager
The Resource Manager is a sub-module of the Time-Based Aggregate Manager and is provided as a plugin for AMsoil. The Resource Manager is in charge of configuring the ALIEN aggregate and of ensuring that the aggregate is accessed by only users assigned to the ongoing experiment. The TBAM RM implements domain-specific methods to manage the resources (see also [Resource Manager in the AMsoil architecture](https://github.com/motine/AMsoil/wiki/GENI#wiki-resource-manager). In particular the northbound interface of TBAM RM provides a set of methods that the TBAM Delegate uses to interact with the TBAM RM and to perform operations like the allocation and provisioning of the resources. On the other side, the southbound interface of the TBAM RM guarantees the booking of resources (through the [scheduling plugin](https://github.com/fp7-alien/OCF-TBAM/tree/master/AMsoil/src/plugins/schedule)) and the configuration of the parameters required by the user (through the OFGW TBAM Agent).Finally, the TBAM RM checks the start or expiration of the experiments through a mechanism which is based on the AMsoil worker services [AMsoil worker](https://github.com/motine/AMsoil/wiki/Worker).


###Northbound interface: TBAM Delegate <--> TBAM Resource Manager

The RM operations are divided into two stages. First, the temporary booking of an ALIEN aggregate for a given time-slot is achieved through an *allocate* call. Nothing is configured on the ALIEN devices, the RM just updates the database of the Scheduling Plugin. In a second stage, the booked time-slot is approved through a *provision* call. Also in this stage the only operation performed by the RM is updating the database entry status from "allocated" to "approved". The *provision* is not approved if the time-slot is different from the one provided during the allocation.
The real provisioning of the slice is performed automatically by the RM by sending the configuration parameters to the OpenFlow Gateway (OFGW) at the beginning of the time-slot.
The *allocate* call is also used to update already approved or provisioned slices (e.g., to change the controller information or to extend/reduce the time-slot). This is achieved through a parameter that identifies the slice (slice_urn). 

The following table lists the APIs exposed by the Resource Manager on the northbound interface. The table is organized as follows: on the leftmost column are listed the GENI v3 API methods that the TBAM delegate exposes to the TB Plugin for Expedient. On the rightmost column, the corresponding TBAM RM methods are provided.

GENI API  v3  | Corresponding TBAM Resource Manager methods |
------------- | -------------
listResources | *getSws():* returns a list of DPIDs of the switches <br> *getLinks():* returns a list of links (e.g. “srcDPID srcPort dstDPID pdstPort”) <br> *getAvailability():* returns all reserved time-slot (start_time=datetime, end_time=datetime, slice_urn) <br> *checkAvailability(start_time, end_time):* returns *true* if the time-slot is available
allocate  | *reserve_aggregate(slice_urn, owner_uuid, owner_mail, start_time, end_time, VLANs, Controller, projectInfo):* controls the availability and processes the temporary booking of the entire ALIEN aggregate in the provided time-slot. Also the provided parameters are saved in the database thanks to the Scheduling plugin: <br>- *projectInfo*: contains the project information (project id and name) that will allow the user to access the OFGW (detailed in the [OFGW TBAM-Agent](https://github.com/fp7-alien/OCF-OFGW/tree/master/TBAM-Agent#users-authentication)). <br> - *VLANs*: permits the VLAN tag rewriting for the network traffic exchanged between OFELIA and ALIEN islands. It is based on a python dict, for instance *{"10" : "0xffff", "30" : "20"}* OFELIA VLAN 10 is set as untagged within ALIEN and OFELIA VLAN 30 is rewritten to the ALIEN VLAN 20. <br> - *controller*: contains the user's  OpenFlow controller IP address and port as a python string *"192.168.100.1:6633"* <br> The allocate method provides also the update of an approved or provisioned entry. In particular when an allocate with same *slice_urn* is received, all the parameters are updated. If the approved entry is started, the update process will involved also the TBAM Agent for install the new configurations.
provision | *approve_aggregate(slice_urn):* The provision is approved if there is previous allocation with same *slice_urn* 
delete | *delete_aggregate(slice_urn)*: releases an allocated or approved slice identified by *slice_urn* by deleting the entry in the Scheduling Plugin database. If the slice has already been started, the Resource Manager tells the TBAM Agent to restore the resources and its internal modules to the default configuration.

The TBAM Resource Manager raises these errors when encountering exceptions:

-	IslandRMRPCError: the connection from TBAM RM and TBAM Agent returns an error. All aforementioned TBAM RM methods can raise this error;-	IslandRMMoreSliceWithSameID: can be raised by reserve_aggregate and approve_aggregate and the error means that the TBAM Scheduling Plugin contains at least two slices having the same slice_urn.-	IslandRMNotUnivocal: the TBAM RM have found a conflict with an already existing slice_urn during the reserve_aggregate;-	IslandRMNotAllocated: delete_aggregate and approve_aggregate are called for a slice not already allocated or approved;-	IslandRMAlreadyReserved: it is used by the reserve_aggregate when the TBAM Scheduling Plugin finds an overbooking error.

### Southbound interface: TBAM Resource Manager <--> OFGW TBAM Agent
The TBAM Agent is an internal OFGW sub-module that is invoked by the TBAM RM to provision/reset the resources. In addition the TBAM Agent permits to retrieve the information of the network devices and to access the forwarding plane through some pre-defined functionalities exposed by the Management plane. The communication between the TBAM Resource Manager and TBAM Agent is achieved through a SecureXMLRPC protocol.

TBAM Agent exposed methods   | Functionality
------------- | -------------
getSws | returns the DPIDs of the switches retrieved through MGMT interface
getLinks | returns the links between switches retrieved through MGMT interface
set/remUserAuth(projectInfo) |  manages the user's credentials needed by the user to access the OFGW
set/remTCPProxy (controller) |  configures the TCP Proxy daemon with the user's controllers coordinates
set/remOvs(VLANs) | configures the VLAN mapping between Alien and OFELIA forwarding planes


## TBAM Scheduling plugin

The Resource Manager leverages on the TBAM Scheduling Plug-in to record the allocated/provisioned time-slots and to avoid conflicts among different experiments. 
In addition, the API that the [Scheduling Plug-in](https://github.com/motine/AMsoil/wiki/Schedule) exposes to access its internal database has been extended with the following:

- flag allocate/approved. Indicates if the slice in the database has been already approved or just allocated. Allocated slices expire after a pre-determined time (set by default to 48 hours). 
- flag started/not started. Indicates whether an approved slice is currently started or not (in other words if it is provisioned or not). 

Other parameters, that do not require any modification in the existing API, exploit the *resource_spec* of the scheduling plugin:

- project id and name
- controller IP and port
- VLANs Mapping

##INSTALLATION

AMSoil requires Python version 2.7 [AMsoil installation](https://github.com/motine/AMsoil/wiki/Installation), therefore a Debian 7 Linux OS is recommended. However, during the testing phase we were able to install both Expedient and the TBAM on the same Debian 6 machine (required by Expedient) by adding the version 2.7 of Python to the system.The repository contains the AMsoil code tree with the three aforementioned modules already installed in the AMsoil/src/plugins (see [TBAM Delegate](https://github.com/fp7-alien/OCF-TBAM/tree/master/AMsoil/src/plugins/islandgeni3), [TBAM RM](https://github.com/fp7-alien/OCF-TBAM/tree/master/AMsoil/src/plugins/islandRM) and [TBAM scheduling plugin](https://github.com/fp7-alien/OCF-TBAM/tree/master/AMsoil/src/plugins/schedule)). To start the TBAM, first run command python AMsoil/src/main.py and then AMsoil/src/main.py –worker to start the worker server.

The southbound interface of the TBAM Resource Manager allows the communication with the OFGW through the TBAM Agent. However, for testing purposes, this interface can be disabled and Resource Manager will use fake fixed data that will be returned to the TBAM Delegate when requested (e.g. with the listResources command). The connection to the TBAM Agent can be enabled/disabled by changing the CONN_WITH_AGENT parameter to True/False. 
The connection to the TBAM Agent uses other three parameters OFGW IP address (OFGW_ADDRESS) and port (OFGW_PORT) and certificates for the SecureXMLRPC (see [TBAM-AGENT Installation](https://github.com/fp7-alien/OCF-OFGW/tree/master/TBAM-Agent#installation) (CLIENT_KEY_PATH and CLIENT_CERT_PATH).
These parameters can be changed through the [AMsoil configuration](https://github.com/motine/AMsoil/wiki/Configuration): e.g, *cd AMsoil/admin && python config_client.py --set CONN_WITH_AGENT=1*.
Obviously, the activation of this connection requires the installation and configuration of the OFGW as detailed in [TBAM-AGENT Installation](https://github.com/fp7-alien/OCF-OFGW/tree/master/TBAM-Agent#installation). 
