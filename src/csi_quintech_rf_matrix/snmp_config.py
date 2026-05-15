#!/usr/bin/env python3
# (c) 2022 The MITRE Corporation, All Rights Reserved
"""! @brief # snmp_config.py for SNMP-based proxies """
##
# @mainpage Common Software Interface PDK
#
# @section description_main Description
# Common SNMP utilities used by SNMP-based proxies

from csi_properties import CSI_Properties
import logging
import threading
import time
from datetime import datetime


class SNMPConfig():

    lock = threading.Lock()
    device_status = 'UNKNOWN'
    device_last_heard = 'NEVER'

    def __init__(self, CSI):
        """
        Update the communication parameters using the 
        current settings. If comms not found in current settings, 
        then communication parameters are invalid.

        Parameters:
        -----------
        self - current instance of class
        CSI - csi object
        """
        self.valid = True
        self.ip = None
        self.read_community = None
        self.write_community = None
        self.snmp_version = None
        self.read_auth_pass = None
        self.read_priv_pass = None
        self.write_auth_pass = None
        self.write_priv_pass = None

        self.update_config(CSI)

        try:
            self.read_auth_pass = CSI.get_property_by_name("read_authentication_password")
            self.read_priv_pass = CSI.get_property_by_name("read_privacy_password")
            self.write_auth_pass = CSI.get_property_by_name("write_authentication_password")
            self.write_priv_pass = CSI.get_property_by_name("write_privacy_password")
        except:
            logging.info('Missing SNMPV3 passwords in csi_properties.yml. If using snmpv3, then expecting to receive them through REST interface')

        if self.valid:
            logging.info(f'DeviceConfig:__init__ -  {self.ip}|{self.read_community}|{self.write_community}|{self.snmp_version}')
        else:
            logging.info(f'DeviceConfig:__init__ - invalid device configuration')

    def update_config(self, CSI):
        current_settings = CSI.get_settings()
    
        if 'device' in current_settings:
            proxycfg = current_settings['device']
            if 'comms' in proxycfg:
                comms = proxycfg['comms']
                if 'ip' in comms:
                    self.ip = comms['ip']
                else:
                    self.valid = False
                if 'read_community' in comms:
                    self.read_community = comms['read_community']
                else:
                    self.valid = False
                if 'write_community' in comms:
                    self.write_community = comms['write_community']
                else:
                    self.valid = False
                if 'snmp_version' in comms:
                    self.snmp_version = comms['snmp_version']
                else:
                    self.valid = False
            else:
                self.valid = False

        else:
            self.valid = False

        if self.valid:
            logging.info(f'ProxyConfig:__init__ -  {self.ip}|{self.read_community}|{self.write_community}|{self.snmp_version}')
        else:
            logging.info(f'ProxyConfig:__init__ - invalid proxy configuration')

    def is_valid(self):
        return self.valid

    def get_ip(self):
        return self.ip

    def get_read_community(self):
        return self.read_community

    def get_write_community(self):
        return self.write_community

    def get_snmp_version(self):
        return self.snmp_version
        
    def get_read_auth_pass(self):
        return self.read_auth_pass
    
    def get_read_priv_pass(self):
        return self.read_priv_pass
    
    def get_write_auth_pass(self):
        return self.write_auth_pass
    
    def get_write_priv_pass(self):
        return self.write_priv_pass
    
    def set_read_auth_pass(self, read_auth_pass):
        self.read_auth_pass = read_auth_pass

    def set_read_priv_pass(self, read_priv_pass):
        self.read_priv_pass = read_priv_pass

    def set_write_auth_pass(self, write_auth_pass):
        self.write_auth_pass = write_auth_pass

    def set_write_priv_pass(self, write_priv_pass):
        self.write_priv_pass = write_priv_pass

    @staticmethod
    def set_device_status(incoming_status='UP'):
        """
        Update current device status
        Print device status and when it was last heard

        Parameters:
        -----------
        incoming_status - either UP, DOWN, UNREACHABLE, default UP if not explicitly stated
        """
        SNMPConfig.device_status = incoming_status
        if incoming_status == 'UP':
            SNMPConfig.device_last_heard = str(datetime.now())
        logging.info(f'set_device_status is {SNMPConfig.device_status}, device_last_heard is {SNMPConfig.device_last_heard}')

    @staticmethod
    def get_device_status():
        return SNMPConfig.device_status

    @staticmethod
    def get_device_last_heard():
        return SNMPConfig.device_last_heard
