#TBAM Resource Manager

The Resource Manager is a sub-module of the Time-Based Aggregate Manager and is provided as a plugin for [AMsoil](https://github.com/motine/AMsoil).
The Resource Manager is in charge of configuring the ALIEN aggregate and of ensuring that the aggregate is accessed by only one user at a time.

##Architecture
The Resource Manager (RM) implements domain-specific methods to manage the resources (see also [Resource Manager in the AMsoil architecture](https://github.com/motine/AMsoil/wiki/GENI#wiki-resource-manager)). In particular the northbound interface of TBAM RM provides a set of methods that the TBAM Delegate uses to interact with the RM and to perform operations like the allocation and provisioning of the resources. On the other side, the southbound interface of the TBAM RM guarantees the booking of resources (through the [scheduling plugin](https://github.com/motine/AMsoil/wiki/Schedule)) and the configuration of the parameters required by the user (through the OFGW TBAM Agent).

The Resource Manager also:

- checks the start or expiration of the experiment based on the time-slot *check_provision()*
- checks for the expiration of an allocation (not approved or provisioned) *check_allocate()*

Both methods exploit the [AMsoil worker](https://github.com/motine/AMsoil/wiki/Worker).


###Northbound interface: TBAM Delegate <--> TBAM Resource Manager

The RM operations are divided into two stages. First, the temporary booking of an ALIEN aggregate for a given time-slot is achieved through an *allocate* call. Nothing is configured on the ALIEN devices, the RM just updates the database of the Scheduling Plugin. In a second stage, the booked time-slot is approved through a *provision* call. Also in this stage the only operation performed by the RM is updating the database entry status from "allocated" to "approved" and adding the new parameters received. The *provision* is not approved if the time-slot is different from the one provided during the allocation.
The real provisioning of the slice is performed automatically by the RM by sending the configuration parameters to the OpenFlow Gateway (OFGW) at the beginning of the time-slot.
The *provision* call is also used to update already approved slices (e.g. to change the controller information or to extend/reduce the time-slot). This is achieved through a parameter that identifies the slice (slice_id). 

The following table lists the APIs exposed by the Resource Manager on the northbound interface. The table is organized as follows: on the leftmost column are listed the GENI v3 API methods that the TBAM delegate exposes to the TB Plugin for Expedient. On the rightmost column, the corresponding TBAM RM methods are provided.

GENI API  v3  | Corresponding TBAM Resource Manager methods
------------- | -------------
listResources | *getSws():* returns a list of DPIDs of the switches <br> *getLinks():* returns a list of links (e.g. “DPID:port-DPID:port”) <br> *getAvailability():* returns all reserved time-slot (start_time=datetime, end_time=datetime, slice_id) <br> *checkAvailability(start_time, end_time):* returns *true* if the time-slot is available 
allocate  | *reserve_aggregate(slice_id, owner_uuid, owner_mail, start_time, end_time, expiration_time):* controls the availability and processes the temporary booking of the entire ALIEN aggregate in the provided time-slot. An allocation is deleted, if the provision command is not issued before the *expiration_time*. If the *expiration_time* is not set, the Scheduling plugin will use the default value set to 48 hours. 
provision | *approve_aggregate(ssh_pub_client_cert, slice_id, owner_uuid, owner_mail, start_time, end_time, VLANs, Controller):* configures the OFGW with the provided parameters (user's account, user's controller IP address, etc.). <br>The provision is approved and all parameters are saved in the Scheduling plugin database if: <br> there has been a previous allocation with same slice_id, start_time, end_time <br> **OR** <br> a slice with the same slice_id has been already approved (update of an approved entry). <br> Parameters: <br>- *ssh_pub_client_cert*: contains the certificate that will allow the user to access the OFGW. <br> - *VLANs*: permits the VLAN tag rewriting for the network traffic exchanged between OFELIA and ALIEN islands. It is based on a python dict, for instance *{"10" : "0xffff", "30" : "20"}* OFELIA VLAN 10 is set as untagged within ALIEN  and OFELIA VLAN 30 is rewritten to the ALIEN VLAN 20. <br> - *controller*: contains the user's  OpenFlow controller IP address and port as a pyhton string *"192.168.100.1:6633"*
delete | *delete_aggregate(slice_id)*: releases an allocated or approved slice identified by *slice_id* by deleting the entry in the Scheduling Plugin database. If the slice has already been started, the Resource Manager tells the TBAM Agent to restore the resources and its internal modules to the default configuration. 

### TBAM Resource Manager <--> TBAM Scheduling plugin

The Resource Manager leverages on the TBAM Scheduling Plugin to record the allocated/provisioned time-slots and to avoid conflicts among different experiments. 
In addition, the API that the Scheduling Plugin exposes to access its internal database has been extended with the following:

- flag allocate/approved. Indicates if the slice in the database has been already provisioned or just allocated. Allocated slices expire after a pre-determined time (set by default to 48 hours). 
- expire_time. An allocation is removed after the expiration time is reached. The scheduling plugin inserts the value as *utcnow() + max_reservation_duration* if not provided in the provision call. The *max_reservation_duration* is a parameter configurable during the initialization of the scheduling plugin.
- flag started/not started. Indicates whether an approved slice is currently started or not.

Other parameters, that do not require any modification in the existing API, exploit the *resource_spec* of the scheduling plugin:

- ssh_pub_client_cert
- controller IP and port
- VLANs Mapping


### Southbound interface: TBAM Resource Manager <--> OFGW TBAM Agent
The TBAM Agent is an internal OFGW sub-module that is invoked by the TBAM RM to provision/reset the resources. In addition the TBAM Agent permits to retrieve the information of the network devices and to access the forwarding plane through some pre-defined functionalities exposed by the Management plane. The communication between the TBAM Resource Manager and TBAM Agent is achieved through a SecureXMLRPC protocol.

TBAM Agent exposed methods   | Functionality
------------- | -------------
getSws | returns the DPIDs of the switches retrieved through MGMT interface
getLinks | returns the links between switches retrieved through MGMT interface
set/remUserAuth(ssh_pub_client_cert) |  manages the user's credentials needed by the user to access the OFGW
set/remTCPProxy (controller) |  configures the TCP Proxy daemon with the user's controllers coordinates
set/remOvs(VLANs) | configures the VLAN mapping between Alien and OFELIA forwarding planes


##INSTALLATION

The TBAM Resource Manager and the TBAM Scheduling plugin are provided as [AMsoil plugin](https://github.com/motine/AMsoil/wiki/Plugin). The installation of AMsoil is described in the [installation section of the wiki](https://github.com/motine/AMsoil/wiki/Installation) while the two plugins must be copied in the src/plugins folder of the AMsoil installation. Moreover, the TBAM Delegate should be adapted to call the methods of the TBAM RM northbound interface.

The southbound interface of the TBAM Resource Manager allows the communication with the OFGW through the TBAM Agent. However, for testing purposes, this interface can be disabled and Resource Manager will use fake fixed data that will be returned to the TBAM Delegate when requested (e.g. with the listResources command). The connection to the TBAM Agent can be enabled/disabled by changing the *CONN_WITH_AGENT* parameter to *True*/*False* in the *islandRM/islandresourcemanager.py*. Obviously, the activation of this connection requires the installation and configuration of the OFGW.