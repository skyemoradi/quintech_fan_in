#!/usr/bin/env python3
# (c) 2023 The MITRE Corporation, All Rights Reserved
"""! @brief # snmp polling logic """
##
# @mainpage Common Software Interface PDK
#
# @section description_main Description
# Demonstrates SNMP polling

import threading
import logging
import time
import yaml
import uuid
from csi_properties import CSI_Properties
from snmp_config import SNMPConfig
from easysnmp import Session
from typing import Any

CSI = CSI_Properties("csi_properties.yml")

def restart_snmp_poller(proxycfg: SNMPConfig):
    """
    Starts the snmp poller
    """
    try:
        if SnmpPoller.polling_in_progress is True:
            # bail out with log message
            logging.info('Skipped poll due to polling in progress...')
            return

        logging.info("Initiating SNMP poll")
        proxycfg.update_config(CSI)
        if proxycfg.is_valid():
            ip = proxycfg.get_ip()
            readcomm = proxycfg.get_read_community()
            version = proxycfg.get_snmp_version()
            read_auth_pass = proxycfg.get_read_auth_pass()
            read_priv_pass = proxycfg.get_read_priv_pass()

            snmp_poller = SnmpPoller(hostname=ip, community=readcomm, version=version, proxycfg=proxycfg, 
                                     read_auth_pass=read_auth_pass, read_priv_pass=read_priv_pass)
            snmp_poller.start()
            logging.info(f"Successfully initiated SNMP poll to {ip}")
        
        else:
            logging.info("Not kicking off a new SNMP poll, communication parameters are not valid")

    except Exception as e:
        logging.info(f"Recoverable exception during polling attempt (restart_snmp_poller)...{e}")

def set_poll_again_flag():
    SnmpPoller.poll_again = True

class SnmpPoller(threading.Thread):

    polling_in_progress = False
    poll_again = False

    def __init__(self, hostname='localhost', community='public', version='1', proxycfg=None, read_auth_pass='', read_priv_pass=''):
        super(SnmpPoller, self).__init__()
        logging.info(f'SnmpPoller:__init__ -  parms are {hostname}|{community}|{version}')
        self.hostname = hostname
        self.community = community
        self.version = version
        self.proxycfg = proxycfg
        self.read_auth_pass = read_auth_pass
        self.read_priv_pass = read_priv_pass
        self.current_settings = None
        SnmpPoller.poll_again = False

        SNMP_to_DoF_MAPPING_FILE = CSI.get_property_by_name('snmp_to_dof_mapping_file')
        
        with open(SNMP_to_DoF_MAPPING_FILE) as file:
            self.tracked_snmp_vars = yaml.safe_load(file)
            logging.info("SNMP variables being tracked:")
            logging.info(self.tracked_snmp_vars)

    def __del__(self):
        logging.debug("DESTRUCTING SNMPPOLLER OBJECT")

    def run(self):
        """
        Performs a poll on the device, updates the current settings, and sets the device status

        Parameters:
        -----------
        self - current instance of class
        """
        global CSI
        DEVICE_STATUS = 'UNREACHABLE'
        # Note: polling_in_progress flag is to ensure no more than 1 poll is going on at a time
        try:
            SnmpPoller.polling_in_progress = True
            self.current_settings = CSI.get_settings(CSI.service_name)
            session = self.create_session(self.hostname, self.community, self.version, self.read_auth_pass, self.read_priv_pass)

            if session:
                
                logging.info('------------------------ POLL START --------------------------------')
                self.perform_poll(session)
                self.update_settings_with_hardcoded_fields()
                CSI.update_settings(self.current_settings)
                CSI.pub(msgtype=CSI.SNMP_POLL_SUCCESSFUL)

                DEVICE_STATUS = 'UP'
                logging.info('------------------------ POLL STOP  --------------------------------')
            else:
                msg = 'Could not create SNMP session'
                logging.debug(f'kick_off_poll: {msg}')
                CSI.pub(msgtype=CSI.SNMP_POLL_FAILED, msgdata=msg)
                DEVICE_STATUS = 'DOWN'

        except Exception as e:
           logging.info(f"Recoverable crash during walk...{e}")
           CSI.pub(msgtype=CSI.SNMP_POLL_FAILED, msgdata=repr(e))

        finally:
            SnmpPoller.polling_in_progress = False
            prev_state = SNMPConfig.get_device_status()
            SNMPConfig.set_device_status(DEVICE_STATUS)
            self.update_log_and_ready_state(DEVICE_STATUS, prev_state)

        if SnmpPoller.poll_again is True:
            logging.info('Polling again in a second...')
            time.sleep(1)
            restart_snmp_poller(self.proxycfg)

    def update_settings_with_hardcoded_fields(self):
        """
        Updates current settings with hardcoded fields such as fault_log and ready if
        conditions are met.

        Parameters:
        -----------
        self - current instance of class
        """
        current_state = ""

        #handle any fields that require logic within the proxy - see Tripplite PDUMH20 for example

    def update_log_and_ready_state(self, DEVICE_STATUS, prev_state):
        """
        Updates the log entries and ready state of the device if device is not running

        Parameters:
        -----------
        self - current instance of class
        DEVICE_STATUS - Either DOWN, UNREACHABLE, or UP
        prev_state - the device's previous state, either DOWN, UNREACHABLE, or UP
        """
        # update the ready state and log entry only once
        if (
            (DEVICE_STATUS == "DOWN" and prev_state != "DOWN")
            or (DEVICE_STATUS == "UNREACHABLE" and prev_state != "UNREACHABLE")
        ):
            self.current_settings['parameters']['ready'] = "HARDWARE_UNRESPONSIVE"
            # set log entry index
            j = self.get_new_index('log')

            self.current_settings['log']['state'] = "HAS_ENTRIES"
            self.current_settings['log']['entries'][f"{j}"] = {"index": f"{j}", "id": f"{uuid.uuid4()}", "timestamp": f"{time.time()}", "level": "WARNING", "description": " State of hardware is unresponsive."}  # NOQA E501
            CSI.update_settings(self.current_settings)

    def get_new_index(self, type):
        """
        Set index for a new entry

        Parameters:
        -----------
        self - current instance of class
        type - either log or fault_log

        Returns:
        --------
        i - index for new entry
        """
        i = 1
        if not type in self.current_settings:
            self.current_settings[f'{type}'] = {}
        if not 'entries' in self.current_settings[f'{type}']:
            self.current_settings[f'{type}']['entries'] = {}
        if len(self.current_settings[f'{type}']['entries']) > 0:
                i = int(list(self.current_settings[f'{type}']['entries'])[-1])+1
        return i

    def create_session(self, hostname, community, version, read_auth_pass, read_priv_pass):
        """
        Creates a session object for snmp walk

        Parameters:
        -----------
        self - current instance of class
        hostname - ip address
        community - public
        version - 1, 2, or 3
        read_auth_pass - password required for snmpv3
        read_priv_pass - password required for snmpv3

        Returns:
        --------
        session - session object
        """
        logging.info(f'create_session -  parms are {hostname}|{community}|{version}')
        logging.debug(f'type of version is {type(version)}')
        try:
            if int(version) == 1 or int(version) == 2:
                session = Session(hostname=hostname, community=community, version=int(version))
            elif int(version) == 3:
                logging.debug(f"READ AUTH PASS: {read_auth_pass}, READ PRIV PASS: {read_priv_pass}")
                session = Session(hostname=hostname, version=int(version), security_level='auth_with_privacy',\
                                    security_username=community, privacy_protocol="AES", privacy_password=read_priv_pass, \
                                    auth_protocol="SHA", auth_password=read_auth_pass, timeout=2, retries=1)
            else:
                logging.info("Could not create SNMP session: Invalid version number")
                return None
        except:
           logging.info("Could not create SNMP session: Missing hostname, community, version, or a password if using v3")
           return None

        logging.debug(f'Created SNMP session with {hostname}, {community}, and {version}')
        return session

    def perform_poll(self, session):
        """
        Performs a snmp walk for all oids in polled_oids listed in the mapping file
        and updates setting if a wanted mib is found

        Parameters:
        -----------
        self - current instance of class
        session - session object
        """
        logging.info(f"perform_poll:")
        snmp_results = []
        for oid in self.tracked_snmp_vars['polled_oids']:
            walk_output = session.walk(oid)
            snmp_results = snmp_results + walk_output
            logging.debug(f"walk output for {oid} is now: {walk_output}")
        
        for item in snmp_results:
            oid = item.oid
            oid_index = item.oid_index
            snmp_type = item.snmp_type
            value = item.value
            # Converting int to string for the DoF
            if oid == "outputAllAGCMode":
                if value == "0":
                    value = "DISABLED"
                elif value == "1":
                    value = "ENABLED"
            elif oid == "outputAllInChNr":
                value = self.format_connected_outputs_from_snmp(value)
            self.update_setting_if_tracking(oid, oid_index, snmp_type, value)

    def format_connected_outputs_from_snmp(self, value):
        try:
            output_index = int(value)
        except (TypeError, ValueError):
            logging.warning(f"Invalid outputAllInChNr value from SNMP: {value}")
            return []
            
        if output_index <= 0:
            return []
        
        return [f"out{output_index}"]

    def update_setting_if_tracking(self, oid, oid_index, snmp_type, value):
        """
        Get and save the tracked oids with updated values after the snmp walk

        Parameters:
        -----------
        self - current instance of class
        oid - current oid that's saved in snmp_results
        oid_index - index of current oid
        snmp_type - 1
        value - value of current oid
        """
        # if oid is of interest, remember it in self.current_settings

        logging.debug(f"Checking oid {oid} with index {oid_index}")
        if oid in self.tracked_snmp_vars['properties']:
            logging.debug(f"update_setting_if_needed: oid is {oid}")
            attrvals = self.tracked_snmp_vars['properties'][oid]

            # ignore oid_index unless use_oid_index is true
            if not ('use_oid_index' in attrvals and attrvals['use_oid_index'] is True):
                oid_index = None

            self.dof_update(attrvals['dof_name'], value, oid_index)

    def dof_update(self, dof_name: str, value: Any, oid_index: list):
        """
        Update the current settings with the oids with updated values

        Parameters:
        -----------
        self - current instance of class
        dof_name - dof name that's mapped to the oid, can be any
                   of the fields listed in settings (ex - parameters.ready)
        value - value of the oid
        oid_index - index of the oid
        """
        self.__verify_current_settings()
        subdict = self.current_settings

        logging.debug(f"Merging {dof_name} with value {value}")
        logging.debug(f"current_settings were: {subdict}")

        elements = dof_name.split('.')
        number_of_elements = len(elements)
        iter = 0

        logging.debug(f"STARTING ITERATION in dof_update(), oid_index is {oid_index}")

        for element in elements:
            iter = iter + 1
            logging.debug(f"iter {iter} out of {number_of_elements}: subdict is {subdict}")

            # # Ensure sub-elements exist if they're needed later
            if ((element not in subdict.keys() or subdict[element] is None)):
                if iter != number_of_elements:
                    subdict[element] = {}

            """ The rough order of operations here is to check:
                1. If there is no OID to CSI element index and we're at the value that needs replaced
                2. If there is no OID to CSI element index and we're not at the replacement value
                3. If we're not at the replacement value
                4. If we're at the replacement value, but still need to insert the index
                5. We're just at the replacement value"""
            if oid_index is None and iter == number_of_elements:
                subdict[element] = value
            elif oid_index is None:
                subdict = subdict[element]
            elif iter == number_of_elements-1:
                subdict = subdict[element]
            elif iter == number_of_elements:
                if oid_index not in subdict:
                    subdict[oid_index] = {}
                subdict[oid_index][element] = value
            else:
                subdict = subdict[element]

            logging.debug(f"END of iter {iter} : subdict is {subdict}")
        logging.debug(f"this subdict is {subdict}")

    def __verify_current_settings(self):
        # Verify that the dict exists before operations are taken on it
        if type(self.current_settings) is not dict:
            self.current_settings = {}
