# (c) 2022 The MITRE Corporation, All Rights Reserved
"""! @brief CSI_Properties class """
##
# @mainpage Common Software Interface PDK
#
# @section description_main Description
# Simplesdr common routines within the CSI PDK

import yaml, os, shutil, json, logging, hashlib

from csi_properties.database import make_database
# from database import make_database
# from pdkapi.utils import make_stdout_logger, debug_action

from csi_properties.utils import make_stdout_logger, debug_action


class CSI_Properties:
    def __init__(self, filename):
        self.properties = {}
        with open(filename) as file:
            self.properties = yaml.safe_load(file)

        # Override service_name property if env variable is set
        csi_svcname = os.environ.get("CSI_SERVICENAME")
        if csi_svcname is not None:
            # logging.info("CSI_SERVICENAME environment variable overriding service name: " + csi_svcname)
            self.properties['service_name'] = csi_svcname

        self.properties['dbkey'] = self.DBKEY_PREFIX + self.properties['service_name']
        self.properties['settings_key'] = self.properties['dbkey'] + self.SETTINGS_SUFFIX
        self.properties['landing_page_key'] = self.properties['dbkey'] + self.LANDING_PAGE_SUFFIX
        self.properties['discover_key'] = self.properties['dbkey'] + self.DISCOVER_SUFFIX

        self.properties['msgkey'] = self.MSGKEY_PREFIX + self.properties['service_name']
        
        # Now establish a key to both the database and the message bus, and remember it in 'properties'
        self.properties['msgbus'] = make_database(self.properties['service_name'])
        self.properties['db'] = make_database(self.properties['service_name'])

    def display(self):
        for item, val in self.properties.items():
            logging.info(item + ": " + str(val))

    def get_property_by_name(self, propname):
        # self.display()
        return self.properties[propname]

    @property
    def service_name(self):
        return self.properties['service_name']

    @property
    def settings_key(self):
        return self.properties['settings_key']

    @property
    def landing_page_key(self):
        return self.properties['landing_page_key']

    @property
    def discover_key(self):
        return self.properties['discover_key']

    @property
    def msgkey(self):
        return self.properties['msgkey']

    @property
    def msgbus(self):
        return self.properties['msgbus']

    @property
    def db(self):
        return self.properties['db']

    @property
    def outgoing_dir(self):
        return self.properties['outgoing_dir']

    @property
    def keepalive_secs(self):
        return self.properties['keepalive_secs']

    @property
    def rest_server_port(self):
        return self.properties['rest_server_port']

    def update_settings(self, msgdata):
        # Returns False if the update fails, True if it succeeds
        logging.info(f'Updating {self.settings_key}')

        # Get the current settings out of the database, fail if not found
        logging.info(f'update_settings retrieving {self.settings_key}')
        settings = self.db.get(self.settings_key)

        if settings is None:
            logging.info('Could not find settings in db')
            return False

        # Merge the incoming msgdata with the settings pulled out of the database
        # logging.info(f'Current settings: {settings}')
        logging.info(f'Updating settings with: {msgdata}')
        settings.update(msgdata)

        # Place updated settings into the database
        # logging.info(f'Updated settings in DB to: {settings}')
        self.db.put(self.settings_key, settings)
        return True

    def get_settings(self, service=None):
        if service is None:
            return self.db.get(self.settings_key)
        # Otherwise, return settings for service passed in
        dbkey = self.DBKEY_PREFIX + service + self.SETTINGS_SUFFIX
        return self.db.get(dbkey)

    def get_discover(self, service=None):
        if service is None:
            return self.db.get(self.discover_key)
        dbkey = self.DBKEY_PREFIX + service + self.DISCOVER_SUFFIX
        return self.db.get(dbkey)

    def get_landing_page(self, service=None):
        if service is None:
            return self.db.get(self.landing_page_key)
        dbkey = self.DBKEY_PREFIX + service + self.LANDING_PAGE_SUFFIX
        return self.db.get(dbkey)

    def create_sha256_file(self, filename):
        logging.info(f'Generating SHA256 for {filename}')

        sha256_hash = hashlib.sha256()
        with open(filename, "rb") as f:
            for byte_block in iter(lambda: f.read(4096),b""):
                sha256_hash.update(byte_block)

        logging.info("Generated hash...")
        sha256_filename = filename + '.sha256'
        with open(sha256_filename,"w") as f:
            f.write(sha256_hash.hexdigest())

    def prep_file_and_notify(self, filename, dest='c2hub', priority="medium", src=None):
        if src is None:
            src = self.service_name
                
        # Make the outgoing directory, may already exist
        logging.info("Creating outgoing directory: " + self.outgoing_dir)
        # Note: destdir is where it will be copied to
        # /data + {dest} + {priority} + {src}
        destdir = self.outgoing_dir + '/' + dest + '/' + priority + '/' + src
        os.makedirs(destdir, exist_ok = True)

        # Copy logfile to destination, generate SHA256
        msgdata = {"filename": os.path.basename(filename), "outgoing_dir": self.outgoing_dir,
                   "destdir": destdir, "priority": priority}
        logging.info(f'filename is {os.path.basename(filename)}, destination directory is {destdir}')
        logging.info(f'base name is {os.path.basename(filename)}')
        shutil.copy(filename, destdir)

        fullpathname = destdir + '/' + os.path.basename(filename)
        logging.info(f'destdir is {destdir}')
        logging.info(f'Creating SHA256 for {fullpathname}')
        self.create_sha256_file(fullpathname)

        self.pub(service=dest,
                 msgtype=self.FILE_TRANSFER_OUT,
                 msgdata=msgdata)

    def pub(self, msgtype, msgdata="", service=None):
        if service is None:
            service = self.service_name
        topic = self.MSGKEY_PREFIX + service + msgtype
        logging.info("Publishing message: " + topic)

        payload={}
        payload['src'] = self.service_name
        payload['dest'] = service
        payload['msgtype'] = msgtype
        payload['msgdata'] = msgdata

        (self.msgbus).publish(topic, payload)

    def sub(self, msgtype, callback, service=None):
        if service is None:
            service = self.service_name
        topic = self.MSGKEY_PREFIX + service + msgtype
        logging.info("Subscribing to " + topic)
        (self.msgbus).subscribe(topic, callback)

    def update_discovery_and_notify(self, discover_settings):
        self.db.put(self.discover_key, discover_settings)    
        self.pub(service=self.service_name,
                 msgtype=self.DISCOVER_UPDATE,
                 msgdata=discover_settings)


    # Published message constants

    SNMP_POLL_SUCCESSFUL = '/snmp-poll-successful'
    SNMP_POLL_FAILED = '/snmp-poll-failed'
    LOG_MESSAGE = '/log-message'

    STATE_CHANGE_REQUEST = '/state-change-request'
    STATE_CHANGE_SUCCESS = '/state-change-success'
    STATE_CHANGE_FAILURE = '/state-change-failure'

    STATUS_UPDATE_RUNNING = '/status-update-running'
    STATUS_UPDATE_STOPPING = '/status-update-stopping'
    DISCOVER_UPDATE = '/discover-update'

    FILE_TRANSFER_OUT = '/file-transfer-out'

    DBKEY_PREFIX = '/service/'
    SETTINGS_SUFFIX = '/settings'
    LANDING_PAGE_SUFFIX = '/landing_page'
    DISCOVER_SUFFIX = '/discover'
    MSGKEY_PREFIX = '/service/'

# Notes on the above:
# DoF is kept in the 'settings' document for the service
#
# The settings document name is formed by concatenating
# {dbkey_prefix} + {service_name} + {settings_suffix}
#
# With a dbkey_prefix of /service/ and a service_name of 
# simplesdr and a settings_suffix of /settings,
# the settings document name would be:
#
# /service/simplesdr/settings
#
# Landing page and discover document names are:
#
# /service/simplesdr/landing_page
# /service/simplesdr/discover
#
# dbkey_prefix: /service/
# settings_suffix: /settings
# landing_page_suffix: /landing_page
# discover_suffix: /discover
# msgkey_prefix: /service/
#
# The message bus uses a similar scheme to the database
# A message destination is formed by concatenating
# the msgkey_prefix + [the destination service] + [a suffix]
#
# MSGBUS.publish(CSI.msgkey + '/state-change-success', payload)
# or, using the 'publish' convenience routine from CSI_Properties:
# CSI.publish(CSI.STATE_CHANGE_SUCCESS, payload)
#
# Similarly, to subscribe to incoming /state-change-request messages:
#
# MSGBUS.subscribe(CSI.msgkey + '/state-change-request', state_change_handler)
# or, using the 'subscribe' convenience routine from CSI_Properties:
# CSI.subscribe(CSI.STATE_CHANGE_REQUEST, state_change_handler)
