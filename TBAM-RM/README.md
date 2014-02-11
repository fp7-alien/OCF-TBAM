#TBAM Resource Manager

The Resource Manager is a sub-module of the Time-Based Aggregate Manager and is provided as a plugin for [AMsoil](https://github.com/motine/AMsoil).
The Resource Manager is in charge of configuring the ALIEN aggregate and of ensuring that the aggregate is accessed by only one user at a time.

##Architecture
The Resource Manager (RM) implements domain-specific methods to manage the resources [[Resource Manager in the AMsoil architecture](https://github.com/motine/AMsoil/wiki/GENI#wiki-resource-manager)]. In particular the northbound interface of TBAM RM provides a set of methods that the TBAM Delegate uses for interacting with the RM. These methods allow the allocation, provisioning, etc. of resources in a domain-specific way (not [GENI AM API v3](http://groups.geni.net/geni/wiki/GAPI_AM_API_V3)-specific). Instead the southbound interface of the TBAM RM guarantees the booking of resources (through the [scheduling plugin](https://github.com/motine/AMsoil/wiki/Schedule)) and the configuration of the parameters required by the user (through the OFGW TBAM Agent).

The Resrouce Manager also:

- checks the starting or expiration of the experiment based on the time-slot *check_provision()*- checks for the expiration of a allocation (not provisioned) *check_allocate()*

Both methods exploit the [AMsoil worker](https://github.com/motine/AMsoil/wiki/Worker).

###TBAM Delegate <--> TBAM Resource Manager
The domain specific aforementioned methods are:

TBAM Delegate method (GENI)  | Corresponding TBAM Resource Manager call
------------- | -------------
listResources | *getSws():* returns a list of DIPD of the switches <br> *getLinks():* returns a list of Link (e.g. “DPID:port-DPID:port”) <br> *getAvailability():* returns all reserved time-slot (start_time=datetime, end_time=datetime, slice_id) <br> *checkAvailability(start_time, end_time):* returns if the time-slot is available (true or false) <br> The calls are forwarded to the TBAM Agent or scheduling plugin
allocate  | *reserve_aggregate(slice_id, owner_uuid, owner_mail, start_time, end_time, expiry_time):* controls the availability and processes the temporary booking of the entire ALIEN aggregate in the provided time-slot. An allocation is removed, if a provision, that is referring to the same allocation, is not accepted before the *expiry_time*. If the *expiry_time* is not configured, the Scheduling plugin provides a default value of 24 hours. 
provision | *provision_aggregate(ssh_pub_client_cert, slice_id, owner_uuid, owner_mail, start_time, end_time, VLANs, Controller):* provides the booking of the entire aggregate for the provided time-slot. <br>A provision call is accepted and all parameters are saved in the Scheduling plugin database: <br> if there is an allocation call with same slice_id, start_time, end_time (provisioned entry) <br> **OR** <br> if there is a provision with the same slice_id (update of a provisioned entry). <br>Involved parameters: <br>- *ssh_pub_client_cert*: should contains the certificate to authenticate the user, but we do not actually how should be the format. <br> - *VLANs*: permits the correct VLAN mapping between OFELIA and ALIEN and it is based on a python dict *{"10" : "0xffff", "30" : "20"}* mapping OFELIA VLAN -> ALIEN VLAN. <br> - *controller*: contains the OpenFlow ip and port as a pyhton string *"192.168.100.1:6633"*
delete | *delete_aggregate(slice_id)*: releases the aggregate provision or allocate. If the aggregate is started, the call is forwarded to the TBAM Agent to clean (e.g. restore network settings through the MGMT Plane) and to free the resources. Otherwise only the entry in database of the Scheduling plugin is deleted.

The working principle of the RM is divided into two stages. First, the temporary booking of an ALIEN aggregate is achieved through an *allocate* call. This first stage allows to save the temporary reservation in the database. In the second stage the booked aggregate can be confirmed by a provision call. The confirmation is achieved if and only if the time-slots of the provisioning and the allocation are equal.  If the provision is confirmed, the RM updates the DB entry status from "allocated" to "provisioned" and adds the new parameters received.
The RM manages also modification of a provisioned entry (e.g. changing the controller information or extend/reduce the time-slot): provision call on a provisioned entry is processed as an update. As a consequence the update process requires an univocally defined parameter to identify which reservation entry must be updated (currently the parameter is the slice_id). 

### TBAM Resource Manager <--> TBAM Scheduling plugin

The Resource Manager leverages on  the TBAM Scheduling Plugin to record the allocated/provisioned time-slots and to avoid conflicts among different experiments. 
In addition, the API that the Scheduling Plugin exposes to access its internal database has been extended with the following:

- flag allocate/provision. Indicates if the slice in the database has been already provisioned or its just allocated. Allocated slices expire after a pre-determined time (currently set to 48 hours). 
- expire_time. An allocation is removed after the reaching of the expiration time. The scheduling plugin inserts the value as *utcnow() + max_reservation_duration* if not provided in the provision call. The *max_reservation_duration* is a parameter configurable during the initialization of the scheduling plugin.
- flag started/not started. Indicates whether a slice is currently started or not.

Other parameters, that do not require any modification in the existing API, exploit the *resource_spec* of the scheduling plugin:

- ssh_pub_client_cert
- controller IP and port
- VLANs Mapping

### TBAM Resource Manager <--> OFGW TBAM AgentThe TBAM Agent is the entity that physically configures the access for the user and all the parameters needed for the control and data plane. In addition the TBAM Agent permits to retrive the information of the network devices and to access the forwarding plane through some pre-defined functionalities exposed by the Management plane. The communication between the TBAM Resource Manager and TBAM Agent is achieved through a SecureXMLRPC protocol.

TBAM Agent exposed methods   | Functionality offered
------------- | -------------
getSws | collects DPID of the switches through MGMT
getLinks | collects network links between switches through MGMTconfigure or clear the OFGW for the experiment | - set/remUserAuth(ssh_pub_client_cert): user access guarantee through cert <br> - set/remTCPProxy (controller): configure the TCPProxy with the OF controller <br> - set/remOvs(VLANs): configure the VLAN mapping between Alien and OFELIA##INSTALLATION

The TBAM Resource Manager and the TBAM Scheduling plugin are provided as [AMsoil plugin](https://github.com/motine/AMsoil/wiki/Plugin). The installation of AMsoil is described in the [installation section of the wiki](https://github.com/motine/AMsoil/wiki/Installation) while the two plugins must be copied in the src/plugins folder of the AMsoil installation. Moreover, the TBAM Delegate should be adapted to call the methods of the TBAM Resource Manager just installed.

The southbound interface of the TBAM Resource Manager allows the communication with the OFGW through the TBAM Agent. However, for testing purposes, this interface can be disabled and  Resource Manager will use fake fixed data that will be returned to the TBAM Delegate when requested (e.g. with the listResources command). The connection to the TBAM Agent can be enabled by changing the *CONN_WITH_AGENT* parameter to *True* in the *islandRM/islandresourcemanager.py*. Of course, the activation of this connection requires the installation and configuration of the OFGW.



## TODO:

- Substitute the slice_id as univocally defined with another parameter (e.g. the slice_urn)
- Return the correct parameters to the Delegate
- Decide the ssh_pub_client_cert format- Could an integration of the TBAM Agent in the AMsoil be possibile? If not, a way to generate the certificates for the SecureXMLRPC must be provided.
- Log