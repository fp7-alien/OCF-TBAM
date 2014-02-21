#TBAM Delegate

The Delegate is a sub-module of the Time-Based Aggregate Manager and is provided as a plugin for [AMsoil](https://github.com/motine/AMsoil). 
The Delegate sites between the GENIv3 Handler and the [TBAM Resource Manager](https://github.com/fp7-alien/OCF-TBAM/tree/master/TBAM-RM#tbam-resource-manager). It translates the GENIv3 call to the domain-specific call of the Resource Manager, in particular the [Resource Specification (RSpec)](http://groups.geni.net/geni/wiki/GeniRspec) into Time-based Resource Manager values (and back). Moreover, it handles the Resource Manager’s exceptions and re-throws them as the GENIv3 method API.

##Architecture

TBAM Delegate methods corresponding to the GENIv3 API are:

- *list_resources(client_cert, credentials, geni_available)*: retrieves the information of the network devices and the reserved time-slots through the Resource Manager. It returns an advertisement RSpec, for e.g.

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
  	</rspec>
	```

	If the reservation is allocated, the Delegate returns to the GENIv3 Handler both geni_allocated status and a RSpec containing the information of the allocated resource. If the allocation fails, the Delegate raises one of these GENIv3 standard errors:
	
	- *BADARGS*: indicates a malformed RSpec.
	- *ERROR*: the database contains at least two entry with same *slice_urn*. This error should never happen, because the Resource Manager is in-charge of controlling the uniqueness of the *slice_urn*.
	- *ALREADYEXISTS*: the error is triggered by either an already used *slice_urn* or an overbooking of the time-slot.
	- *SERVERERROR*: the communication between TBAM Resource Manager and TBAM Agent has encountered a problem.

- *provision(urns, client_cert, credentials, best_effort, end_time, geni_users)*: translates the provision to the Resource Manager *approve_aggregate* request. If the request is approved, the Delegate returns *geni_allocated* status, *geni_configuring* operational status and an RSpec equal the one of the *allocate* method. In case of errors the method will raise:
	- *BADARGS, ERROR*: equals to the aforementioned.
	- *SEARCHFAILED*: a previous allocation having the same *slice_urn* is not found.  
	- *ALREADYEXISTS*: more allocation or approval exist with same *slice_urn*
	
- *delete(self, urns, client_cert, credentials, best_effort)*: translate the *delete* to the Resource Manager *delete_aggregate*. It returns a *geni_unallocated* status or it throws:
	- *BADARGS, ERROR*, *ALREADYEXISTS*: equals to the *provision* errors.
	- *SEARCHFAILED*: a previous allocation or approval having the same *slice_urn* is not found.




##INSTALLATION

The TBAM Delegate plugin is provided as [AMsoil plugin](https://github.com/motine/AMsoil/wiki/Plugin). The installation of AMsoil is described in the [installation section of the wiki](https://github.com/motine/AMsoil/wiki/Installation) while the plugin must be copied in the src/plugins folder of the AMsoil installation. Moreover, the TBAM Delegate requires the [installation of TBAM Resource Manager](https://github.com/fp7-alien/OCF-TBAM/tree/master/TBAM-RM#installation).
