#!/usr/bin/env python3
# (c) 2022 The MITRE Corporation, All Rights Reserved
"""! @brief # proxy_backend.py: where execution begins """
##
# @mainpage Common Software Interface PDK
#
# @section description_main Description
# Demonstrates an SNMP-based proxy
import threading

import logging
import time
import schedule
import uuid

from quintech_rf_matrix_settings import QuintechRFMatrixSettings
from mergedeep import merge

from csi_properties import CSI_Properties
from snmp_poller import restart_snmp_poller
from snmp_setter import perform_snmp_set
from snmp_config import SNMPConfig

from quintech_rf_matrix_mocker import QUINTECH_RF_MATRIX_TEST
from easysnmp import Session

CSI = CSI_Properties("csi_properties.yml")

_HEARTBEAT_PERIOD_SECONDS = CSI.get_property_by_name('heartbeat_interval_msecs')

def proxy_backend_start() -> None:
    """
    Starts the main processing thread of the proxy backend

    Parameters:
    -----------
    None

    Returns:
    --------
    None
    """
    try:
        proxy = ProxyBackend()
        logging.info("Starting up proxy backend...")
        proxy.start()
        
    except Exception as e:
        logging.info(f"Could not start up proxy backend...{e}")


class ProxyBackend(threading.Thread):
    __heartbeat_job = None
    __poll_job = None
    __DEBUG = CSI.get_property_by_name('debug_mode')
    _proxycfg = None

    @staticmethod
    def __print_heartbeat():
        """
        Logs a heartbeat message, indicating that the proxy is running

        Parameters:
        -----------
        None

        Returns:
        --------
        None
        """
        localtime = time.localtime()
        localtime_str = time.strftime("%I:%M:%S %p", localtime)
        logging.info(f"HEARTBEAT: {localtime_str}")
        CSI.update_settings({'heartbeat': {"heartbeat_interval_msec": _HEARTBEAT_PERIOD_SECONDS, "last_sent": localtime_str}})

    @staticmethod
    def __send_keepalive_msg():
        """
        Publishes a message about the device's current status, when device was last heard, and if csi proxy is running

        Parameters:
        -----------
        None

        Returns:
        --------
        None
        """
        global CSI

        # get device status and last heard time
        addlinfo = { "device_status": SNMPConfig.get_device_status(),
                     "device_last_heard": SNMPConfig.get_device_last_heard()}
        logging.info(f'Publishing status update message with device info: {addlinfo}')
        CSI.pub(msgtype=CSI.STATUS_UPDATE_RUNNING, msgdata=addlinfo)

        localtime = time.localtime()
        localtime_str = time.strftime("%I:%M:%S %p", localtime)
        logging.info(f"{CSI.service_name} running as of {localtime_str}")
        logging.info(f'CSI is: {CSI.properties}')

    def __init__(self) -> None:
        super().__init__()
       
        self._msgdata = QuintechRFMatrixSettings.initialize_database()
    
        self._session = None

        ProxyBackend._proxycfg = SNMPConfig(CSI)


    def __connect_to_device(self) -> None:
        """
        Attempts to create a session with the device and prints a warning if it is not able to.

        Parameters:
        -----------
        None

        Returns:
        --------
        None
        """
        try:
            self._session = Session(hostname=self._msgdata['device']['comms']['ip'],
                                    community=self._msgdata['device']['comms']['write_community'],
                                    version=int(self._msgdata['device']['comms']['snmp_version']))
        except Exception as e: 
            logging.warning(f"Could not establish SNMP session...{e}")

    def __init_device(self) -> bool:
        """
        Perform any actions that are needed to initially set up the device.

        Parameters:
        -----------
        None

        Returns:
        --------
        True - the device is successfully initialized
        False - the device is not initialized
        """
        return True

    def __start_poll(self) -> None:
        """
        Kicks off the initial poll and schedules a poll to occur for every poll interval.

        Parameters:
        -----------
        None

        Returns:
        --------
        None
        """
        if "REFLECTOR" in ProxyBackend.__DEBUG:
            # run mocker
            QUINTECH_RF_MATRIX_TEST.mock_restart_snmp_poller()
            poll_interval = CSI.get_property_by_name('poll_interval')
            ProxyBackend.__poll_job = schedule.every(poll_interval).seconds.do(QUINTECH_RF_MATRIX_TEST.mock_restart_snmp_poller)
        else:
            restart_snmp_poller(ProxyBackend._proxycfg)
            poll_interval = CSI.get_property_by_name('poll_interval')
            ProxyBackend.__poll_job = schedule.every(poll_interval).seconds.do(restart_snmp_poller, ProxyBackend._proxycfg)

    def run(self) -> None:
        """
        Updates the current settings in database with default common information from csi_properties.yml. 
        Starts heartbeat, keep alive, and snmp_poller threads.

        Parameters:
        -----------
        self - current instance of class

        Returns:
        --------
        None
        """
        global CSI
        logging.info("ProxyBackend main loop starting")

        # Use CSI.sub convenience routine to listen for state changes
        CSI.sub(service=CSI.service_name,
                msgtype=CSI.STATE_CHANGE_REQUEST,
                callback=ProxyBackend.handle_state_change)

        # Schedule periodic heartbeat and keepalive messages
        ProxyBackend.__heartbeat_job = schedule.every(CSI.get_property_by_name("heartbeat_interval_msecs")/1000).seconds.do(ProxyBackend.__print_heartbeat)
        schedule.every(CSI.keepalive_secs).seconds.do(ProxyBackend.__send_keepalive_msg)

        # Initialize variables that will hold proxy configuration parameters 
        logging.info("Loading default common information...")

        # Establish communication with device
        self.__connect_to_device()
        is_device_initialized = False
        if "REFLECTOR" in ProxyBackend.__DEBUG:
            is_device_initialized = True
        else:
            is_device_initialized = self.__init_device()

        if not is_device_initialized:
            logging.warning('Device is not initialized')

        if "REFLECTOR" in ProxyBackend.__DEBUG:
            logging.info("DEBUG REFLECTOR: Updating default common info...")

            current_settings = QuintechRFMatrixSettings.initialize_reflector_settings(CSI)

            merge(self._msgdata, current_settings)

        # Push updated settings to the database
        is_update_successful = CSI.update_settings(self._msgdata)

        # If all initialization was successful, publish state change success. Else, publish state change failure
        if is_device_initialized and is_update_successful:
            CSI.pub(service=CSI.service_name,
                    msgtype=CSI.STATE_CHANGE_SUCCESS,
                    msgdata=self._msgdata)
        else:
            CSI.pub(service=CSI.service_name,
                    msgtype=CSI.STATE_CHANGE_FAILURE,
                    msgdata=self._msgdata)

        # Allow time for set before polling device
        time.sleep(2)

        # Schdule thread to handle periodic communication with the device
        self.__start_poll()

        while True:
            schedule.run_pending()
            time.sleep(1)

    @staticmethod
    def update_log_entry_index(current_settings) -> tuple[int, dict]:
        """
        Sets the index for a new log entry

        Parameters:
        -----------
        current_settings - current settings in the database to check logs for

        Returns:
        --------
        i - int with log index
        current_settings - database settings with log and entries initialized
        """
        # get log entry index
        i = 1

        if not 'log' in current_settings:
            current_settings['log'] = {}
        if not 'entries' in current_settings['log']:
            current_settings['log']['entries'] = {}

        if len(current_settings['log']['entries']) > 0:
            i = int(list(current_settings['log']['entries'])[-1])+1
        return i, current_settings
    
    @staticmethod
    def create_response(result, current_settings, msgdata) -> tuple[dict, str]:
        """
        Creates a state_change_success or state_change_failure response

        Parameters:
        -----------
        self - current instance of class

        Returns:
        --------
        i - int
        """
        # set log entry index
        i, current_settings = ProxyBackend.update_log_entry_index(current_settings)

        current_settings['log']['state'] = "HAS_ENTRIES"
        
        if result == 'success':
            # update response fields as success
            sessionID = uuid.uuid4()
            #current_settings['response'].update({"response_type": "NEW_SESSION", "session_id": f"{sessionID}"})
            #current_settings['session_id'] = f"{sessionID}"
            # Clear previous logs
            current_settings['log']['entries'] = {}
            current_settings['log']['entries'][f"{i}"] = {"index": f"{i}", "id": f"{uuid.uuid4()}", "timestamp": f"{time.time()}", "level": "INFO", "description": f"Sucessfully changing configurations with {msgdata}."}
            csi_message_type = CSI.STATE_CHANGE_SUCCESS
        elif result == 'failure':
            # update response fields as failure
            #current_settings['response'].update({"response_type": "SESSION_REJECT", "session_id": "proxy"})
            #current_settings['session_id'] = ""
            # Clear previous logs
            current_settings['log']['entries'] = {}
            current_settings['log']['entries'][f"{i}"] = {"index": f"{i}", "id": f"{uuid.uuid4()}", "timestamp": f"{time.time()}", "level": "ERROR", "description": f"Failure in changing configurations with {msgdata}."}
            csi_message_type = CSI.STATE_CHANGE_FAILURE
        else:
            logging.info("Invalid response type, cannot create response")

        return current_settings, csi_message_type

    @staticmethod
    def handle_state_change(channel, pattern, payload) -> None:
        """
        Handles all state changes with the device

        Parameters:
        -----------
        channel - refers to the service url (example - /service/csi_apc_srt3000/state-change-request)
        pattern - 
        payload - command in json
        """
        logging.warning(f"handle_state_change(): payload is {payload}")

        if 'msgdata' not in payload:
            logging.warning(f"msgdata not found in payload")
            return

        incoming_msgdata = payload['msgdata']
        user_roles = []

        logging.info(f"state_change_handler(): incoming_msgdata is {incoming_msgdata}")

        current_settings = CSI.get_settings(CSI.service_name)

        current_settings['parameters']['ready'] = "HARDWARE_BUSY"
        successful = CSI.update_settings(current_settings)

        #start as failure
        csi_message_type = CSI.STATE_CHANGE_FAILURE
        
        #handle message accordingly
        if 'device' in incoming_msgdata and 'comms' in incoming_msgdata['device']: 
            logging.info("Changing device configuration")
            if 'snmpv3_passwords' in incoming_msgdata['device']['comms']:
                passwords_dict = incoming_msgdata['device']['comms']['snmpv3_passwords']
                logging.debug(f'PASSWORDS DICT: {passwords_dict}')
                if 'read_authentication_password' in passwords_dict:
                    ProxyBackend._proxycfg.set_read_auth_pass(passwords_dict['read_authentication_password'])
                if 'read_privacy_password' in passwords_dict:
                    ProxyBackend._proxycfg.set_read_priv_pass(passwords_dict['read_privacy_password'])
                if 'write_authentication_password' in passwords_dict:
                    ProxyBackend._proxycfg.set_write_auth_pass(passwords_dict['write_authentication_password'])
                if 'write_privacy_password' in passwords_dict:
                    ProxyBackend._proxycfg.set_write_priv_pass(passwords_dict['write_privacy_password'])
                logging.debug(f'READ AUTH: {ProxyBackend._proxycfg.get_read_auth_pass()} READ PRIV: {ProxyBackend._proxycfg.get_read_priv_pass()}')
            else:
                current_settings = CSI.get_settings(CSI.service_name)

                if ProxyBackend.set_communication_parameters() is True:
                    # update response fields as success
                    current_settings, csi_message_type = ProxyBackend.create_response('success', current_settings, incoming_msgdata)
                    merge(current_settings["device"]["comms"], incoming_msgdata['device']['comms'])
                else:
                    # update response fields as failure
                    current_settings, csi_message_type = ProxyBackend.create_response('failure', current_settings, incoming_msgdata)

                CSI.update_settings(current_settings)
                
                CSI.pub(service=CSI.service_name,
                        msgtype=csi_message_type,
                        msgdata=incoming_msgdata)
        elif 'heartbeat' in incoming_msgdata and 'update_interval_msec' in incoming_msgdata['heartbeat']:
            if incoming_msgdata['heartbeat']['update_interval_msec'].isdigit() and int(incoming_msgdata['heartbeat']['update_interval_msec']) > 0:
                logging.info("Restarting heartbeat...")
                schedule.cancel_job(ProxyBackend.__heartbeat_job)
                ProxyBackend.__heartbeat_job = schedule.every(int(incoming_msgdata['heartbeat']['update_interval_msec'])/1000).seconds.do(ProxyBackend.__print_heartbeat)
                CSI.update_settings({'heartbeat': {'update_interval_msec': incoming_msgdata['heartbeat']['update_interval_msec']}})
                current_settings, csi_message_type = ProxyBackend.create_response('success', current_settings, incoming_msgdata)
                _HEARTBEAT_PERIOD_SECONDS = incoming_msgdata['heartbeat']['update_interval_msec']
            else:
                # update response fields as failure
                current_settings, csi_message_type = ProxyBackend.create_response('failure', current_settings, incoming_msgdata)
            
            CSI.update_settings(current_settings)
            
            CSI.pub(service=CSI.service_name,
                    msgtype=csi_message_type,
                    msgdata=incoming_msgdata)
        elif 'debug_mode' in incoming_msgdata:
            if ProxyBackend.__DEBUG == incoming_msgdata['debug_mode']:
                #no change in mode
                return
            elif not set(incoming_msgdata['debug_mode']).issubset(["OFF", "REFLECTOR", "DEBUG", "VERBOSE"]):
                #invalid mode
                return
            else:
                #disable previous modes if needed
                if "REFLECTOR" in ProxyBackend.__DEBUG:
                    #re-enable normal device communications
                    schedule.cancel_job(ProxyBackend.__poll_job)
                    restart_snmp_poller(ProxyBackend._proxycfg)
                    poll_interval = CSI.get_property_by_name('poll_interval')
                    ProxyBackend.__poll_job = schedule.every(poll_interval).seconds.do(restart_snmp_poller, ProxyBackend._proxycfg)
                if "DEBUG" in ProxyBackend.__DEBUG:
                    #no function for proxy
                    pass
                if "VERBOSE" in ProxyBackend.__DEBUG:
                    #no function for proxy
                    pass
            if "OFF" in incoming_msgdata['debug_mode']:
                 #already disabled previous mode, force it to be the only command
                 ProxyBackend.__DEBUG = ["OFF"]
                 incoming_msgdata['debug_mode'] = ["OFF"]
            if "REFLECTOR" in incoming_msgdata['debug_mode']:
                ProxyBackend.__DEBUG = ["REFLECTOR"]

                __mock_msgdata = QuintechRFMatrixSettings.initialize_reflector_settings(CSI)

                is_update_successful = CSI.update_settings(current_settings)

                if is_update_successful:
                    # run mocker
                    schedule.cancel_job(ProxyBackend.__poll_job)
                    QUINTECH_RF_MATRIX_TEST.mock_restart_snmp_poller()
                    poll_interval = CSI.get_property_by_name('poll_interval')
                    ProxyBackend.__poll_job = schedule.every(poll_interval).seconds.do(QUINTECH_RF_MATRIX_TEST.mock_restart_snmp_poller)

                    current_settings['parameters']['ready'] = "READY"
                    CSI.pub(service=CSI.service_name,
                            msgtype=CSI.STATE_CHANGE_SUCCESS,
                            msgdata=__mock_msgdata)
                else:
                    logging.warning('unable to enable REFLECTOR mode')
                    CSI.pub(service=CSI.service_name,
                            msgtype=CSI.STATE_CHANGE_FAILURE,
                            msgdata=__mock_msgdata)
            if "DEBUG" in incoming_msgdata['debug_mode']:
                pass
            if "VERBOSE" in incoming_msgdata['debug_mode']:
                pass
        elif "REFLECTOR" in ProxyBackend.__DEBUG:
            # run mocker
            QUINTECH_RF_MATRIX_TEST.mock_perform_snmp_set(incoming_msgdata)
        else:
            perform_snmp_set(incoming_msgdata, ProxyBackend._proxycfg)
        return

    @staticmethod
    def set_communication_parameters():
        """
        Sets the communication parameters (ip, read/write comms, and snmp ver).

        Returns:
        --------
        boolean - True, False
        """
        # result of this is that CSI.ip, CSI.read_community,
        # CSI_write_community, and CSI.snmp_version are all set

        global CSI
        current_settings = CSI.get_settings()
        if 'device' in current_settings:
            pc = current_settings['device']
            if 'comms' in pc:
                comms = pc['comms']
                if 'ip' in comms:
                    CSI.ip = comms['ip']
                else:
                    return False
                if 'read_community' in comms:
                    CSI.read_community = comms['read_community']
                else:
                    return False
                if 'write_community' in comms:
                    CSI.write_community = comms['write_community']
                else:
                    return False
                if 'snmp_version' in comms:
                    CSI.snmp_version = comms['snmp_version']
                else:
                    return False
            else:
                return False

            # if at this point, all fields have been found in DoF
            return True
        else:
            return False
