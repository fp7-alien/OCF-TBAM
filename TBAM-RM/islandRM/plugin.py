import amsoil.core.pluginmanager as pm


def setup():
    # setup config keys
    config = pm.getService("config")
    
    # TODO: Vanno decise i tempi di allocazione di un allocate.
    config.install("dhcprm.max_reservation_duration", 10 * 60, "Maximum duration a DHCP resource can be held allocated (not provisioned).")
    config.install("dhcprm.max_lease_duration", 24 * 60 * 60, "Maximum duration DHCP lease can be provisioned.")
    config.install("aggregate.dbpath", "deploy/aggregate.db", "Path to the database")
    
    # config.install("dhcprm.dbpath", "deploy/dhcp.db", "Path to the dhcp database (if relative, AMsoil's root will be assumed).")
    
    from islandresourcemanager import islandResourceManager
    rm = islandResourceManager()
    pm.registerService('islandresourcemanager', rm)
    
    import islandrmexceptions as exceptions_package
    pm.registerService('islandrmexceptions', exceptions_package)
