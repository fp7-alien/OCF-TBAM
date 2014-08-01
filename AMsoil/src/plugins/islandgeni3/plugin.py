import amsoil.core.pluginmanager as pm
from islanddelegate import ISLANDdelegate


def setup():
    # setup config keys
    # config = pm.getService("config")
    
    delegate = ISLANDdelegate()
    handler = pm.getService('geniv3handler')
    handler.setDelegate(delegate)