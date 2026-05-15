#!/usr/bin/env python3
# (c) 2022 The MITRE Corporation, All Rights Reserved
"""! @brief # snmp_setter.py  """
##
# @mainpage Common Software Interface PDK
#
# @section description_main Description
# Issues SNMP sets against an SNMP-based device

import threading
import logging
import re
import time
import yaml
import uuid
from csi_properties import CSI_Properties
from snmp_config import SNMPConfig
from snmp_poller import restart_snmp_poller

from easysnmp import Session

CSI = CSI_Properties("csi_properties.yml")

class InvalidStateChange(Exception):
    pass

def perform_snmp_set(msgdata, proxycfg: SNMPConfig):
    """
    Starts the snmp setter
    Publishes a fail message to csi if error

    Parameters:
    -----------
    msgdata - refers to the json command (ex. {'fault_log': {'clear_all': 'CLEAR'}})
    """
    logging.info("PERFORMING SNMP SET")
    proxycfg.update_config(CSI)
    if proxycfg.is_valid():
        ip = proxycfg.get_ip()
        writecomm = proxycfg.get_write_community()
        version = proxycfg.get_snmp_version()
        write_auth_pass = proxycfg.get_write_auth_pass()
        write_priv_pass = proxycfg.get_write_priv_pass()
        snmp_setter = SnmpSetter(hostname=ip, community=writecomm, version=version, proxycfg=proxycfg,
                                 write_auth_pass=write_auth_pass, write_priv_pass=write_priv_pass, msgdata=msgdata)
        snmp_setter.start()
        logging.info("Successfully kicked off SNMP Set")
    else:
        error_text = "SNMP Set failure: Invalid communication parameters"
        logging.info(f"{error_text}")
        msgdata['result'] = error_text
        CSI.pub(service=CSI.service_name,
                msgtype=CSI.STATE_CHANGE_FAILURE,
                msgdata=msgdata)

class SnmpSetter(threading.Thread):

    def __init__(self, hostname=None, community='private', version='1', proxycfg = None, write_auth_pass='', write_priv_pass='', msgdata=''):
        super(SnmpSetter, self).__init__()
        logging.info(f'SnmpSetter:__init__ -  parms are {hostname}|{community}|{version}')
        self.hostname = hostname
        self.community = community
        self.version = version
        self.proxycfg = proxycfg
        self.write_auth_pass = write_auth_pass
        self.write_priv_pass = write_priv_pass
        self.msgdata = msgdata
        self.current_settings = None
        self.settable_dof_vars = None
        self.result = 'undiagnosed failure'
        # self.successful refers to whether or not the SNMP Set was successful
        self.successful = False
        self.validation_warnings = []

        SNMP_to_DoF_MAPPING_FILE = CSI.get_property_by_name('snmp_to_dof_mapping_file')
        
        with open(SNMP_to_DoF_MAPPING_FILE) as file:
            self.settable_dof_vars = yaml.safe_load(file)
            logging.debug("Settable DOF variables loaded:")
            logging.debug(self.settable_dof_vars)


    def __del__(self):
        logging.debug("*** DESTRUCTING SNMPSETTER OBJECT ***")

    def run(self):
        """
        Sets up the snmp set on the device, updates the settings, and publishes the result of the snmp set to csi

        Parameters:
        -----------
        self - current instance of class
        """
        global CSI
        session = self.create_session(self.hostname, self.community, self.version, self.write_auth_pass, self.write_priv_pass)

        if session:
            self.result = self.update_settings_on_device(session, self.msgdata)
        else:
            errmsg = 'Could not create session to perform SNMP Set'
            logging.debug(errmsg)
            self.result = errmsg

        self.msgdata['result'] = self.result

        if self.successful:
            logging.info(f'Snmp SET successful, sending STATE_CHANGE_SUCCESS to {CSI.service_name} with {self.msgdata}')
            CSI.pub(service=CSI.service_name,
                    msgtype=CSI.STATE_CHANGE_SUCCESS,
                    msgdata=self.msgdata)
        else:
            logging.info(f'Snmp SET FAILURE, sending STATE_CHANGE_FAILURE to {CSI.service_name} with {self.msgdata}')
            CSI.pub(service=CSI.service_name,
                    msgtype=CSI.STATE_CHANGE_FAILURE,
                    msgdata=self.msgdata)

    def create_session(self, hostname, community, version, write_auth_pass, write_priv_pass):
        """
        Creates a session object for snmp set

        Parameters:
        -----------
        self - current instance of class
        hostname - ip address
        community - private
        version - 1

        Returns:
        --------
        session - session object
        """
        logging.info(f'create_session -  parms are {hostname}|{community}|{version}')
        logging.info(f'type of version is {type(version)}')
        try:
            if int(version) == 1 or int(version) == 2:
                session = Session(hostname=hostname, community=community, version=int(version))
            elif int(version) == 3:
                logging.debug(f"READ AUTH PASS: {write_auth_pass}, READ PRIV PASS: {write_priv_pass}")
                session = Session(hostname=hostname, version=int(version), security_level='auth_with_privacy',\
                                    security_username=community, privacy_protocol="AES", privacy_password=write_priv_pass, \
                                    auth_protocol="SHA", auth_password=write_auth_pass, timeout=2, retries=1)
            else:
                logging.info("Could not create SNMP session: Invalid version number")
                return None
        except Exception as e:
            logging.info("Could not create SNMP session: Missing hostname, community, version, or a password if using v3")
            return None

        logging.debug(f'Created SNMP session with {hostname}, {community}, and {version}')
        return session

    def get_indexed_section(self, *path):
        node = self.current_settings
        for key in path:
            if not isinstance(node, dict):
                return {}
            node = node.get(key, {})
        return node if isinstance(node, dict) else {}

    def get_port_count(self, *path):
        section = self.get_indexed_section(*path)
        numeric_keys = []
        for key in section.keys():
            try:
                numeric_keys.append(int(key))
            except (TypeError, ValueError):
                continue
        return max(numeric_keys) if numeric_keys else 0

    def validate_input_index(self, instance):
        try:
            input_index = int(instance)
        except (TypeError, ValueError):
            raise InvalidStateChange(f"Invalid input port index '{instance}'")

        max_input = self.get_port_count('parameters', 'input_ports')
        if max_input and (input_index < 1 or input_index > max_input):
            raise InvalidStateChange(f"Input port index {input_index} is outside available range 1-{max_input}")

        return input_index

    def validate_output_index(self, instance):
        try:
            output_index = int(instance)
        except (TypeError, ValueError):
            raise InvalidStateChange(f"Invalid output port index '{instance}'")

        max_output = self.get_port_count('parameters', 'output_ports')
        if max_output and (output_index < 1 or output_index > max_output):
            raise InvalidStateChange(f"Output port index {output_index} is outside available range 1-{max_output}")

        return output_index

    def parse_connected_outputs_for_snmp(self, dofval, instance):
        input_index = self.validate_input_index(instance)

        if isinstance(dofval, list):
            requested_outputs = dofval
        else:
            requested_outputs = [dofval]

        warnings = []
        if len(requested_outputs) == 0:
            return 0, warnings

        first_output = requested_outputs[0]
        first_output_text = "" if first_output is None else str(first_output).strip().lower()

        if len(requested_outputs) > 1:
            warnings.append(
                f"Input {input_index} requested multiple connected_outputs {requested_outputs}; using first value '{first_output}'"
            )

        if first_output_text in ("", "0"):
            return 0, warnings

        match = re.fullmatch(r"out([1-9][0-9]*)", first_output_text)
        if not match:
            raise InvalidStateChange(
                f"Invalid connected_outputs value '{first_output}' for input {input_index}; expected labels like 'out5'"
            )

        output_index = int(match.group(1))
        self.validate_output_index(output_index)
        return output_index, warnings

    def get_numeric_setting(self, default_value, *path):
        node = self.current_settings
        for key in path:
            if not isinstance(node, dict):
                return default_value
            node = node.get(key)
        try:
            return float(node)
        except (TypeError, ValueError):
            return default_value

    def get_output_agc_state(self, instance):
        output_ports = self.get_indexed_section('proprietary_fields', 'output_ports')
        output_port = output_ports.get(str(instance), {})
        if not isinstance(output_port, dict):
            return "UNKNOWN"
        agc_state = output_port.get('agc_enable')
        if agc_state is None:
            return "UNKNOWN"
        return str(agc_state).upper()

    def validate_gain_for_snmp(self, oid, dofval, instance):
        try:
            gain = float(dofval)
        except (TypeError, ValueError):
            raise InvalidStateChange(f"Invalid gain value '{dofval}' for {oid}.{instance}")

        if oid == 'inputAllGain':
            self.validate_input_index(instance)
            minimum = self.get_numeric_setting(-14.5, 'sensors', 'min_input_gain_dB')
            maximum = self.get_numeric_setting(17.0, 'sensors', 'max_input_gain_dB')
            port_label = f"input {instance}"
        elif oid == 'outputAllGain':
            self.validate_output_index(instance)
            minimum = self.get_numeric_setting(-18.5, 'sensors', 'min_output_gain_dB')
            maximum = self.get_numeric_setting(13.0, 'sensors', 'max_output_gain_dB')
            port_label = f"output {instance}"

            agc_state = self.get_output_agc_state(instance)
            if agc_state == 'ENABLED':
                raise InvalidStateChange(
                    f"Cannot set manual gain for output {instance} while output AGC is ENABLED"
                )
            if agc_state == 'UNKNOWN':
                raise InvalidStateChange(
                    f"Cannot set manual gain for output {instance} because output AGC state is unknown"
                )
        else:
            return dofval

        if gain < minimum or gain > maximum:
            raise InvalidStateChange(
                f"Gain {gain} dB for {port_label} is outside hardware range {minimum} to {maximum} dB"
            )

        return gain

    def convert_agc_mode_for_snmp(self, dofval, instance):
        self.validate_output_index(instance)
        value = str(dofval).upper()

        if value == "DISABLED":
            return 0
        if value == "ENABLED":
            return 1

        raise InvalidStateChange(
            f"Invalid output AGC mode '{dofval}' for output {instance}; expected ENABLED or DISABLED"
        )


    def lookup_oid(self, incoming_msgdata, with_instance=False):
        """
        Maps the dof_name to the oid with or without an instance. 
        Converts the str value of oid to an snmp acceptable value if needed

        Parameters:
        -----------
        self - current instance of class
        incoming_msgdata - the command in json/as a dict (ex. {'fault_log': {'clear_all': 'CLEAR'}})
        with_instance - either True or False, always False on the first iteration

        Returns:
        --------
        oid - the oid that's mapped to the dofkey, can be any of the fields in snmp_to_dof_mapping.yml
        dofkey - the dof_name that's listed in the incoming_msgdata
        dofval - the value of the dof_name listed in incoming_msgdata
        """
        dofkey, dofval, instance = self.convert_to_dotted_notation(incoming_msgdata, with_instance)
        oid = self.lookup_hardcoded_field(dofkey, dofval, instance, incoming_msgdata)

        x = self.settable_dof_vars['properties']
        logging.debug(f"LOOKUP_OID: x is {x}")
    
        # if oid maps to hardcoded field, skip for loop
        if oid == None:
            for p in self.settable_dof_vars['properties'].keys():
                logging.debug(f"LOOKUP_OID p is {p}")
                logging.debug(f"LOOKUP_OID....{self.settable_dof_vars['properties'][p]}")
                candidate = self.settable_dof_vars['properties'][p]
                if candidate['dof_name'] == dofkey:
                    if 'settable' in candidate and candidate['settable'] == True:
                        #check that field is settable
                        oid = p
                        # Convert Dof values to snmp and validate hardware constraits
                        try:
                            if oid == 'outputAllAGCMode':
                                dofval = self.convert_agc_mode_for_snmp(dofval, instance)
                            elif oid == 'outputAllInChNr':
                                dofval, warnings = self.parse_connected_outputs_for_snmp(dofval, instance)
                                for warning in warnings:
                                    logging.warning(warning)
                                    self.validation_warnings.append(warning)
                            elif oid == 'inputAllGain' or oid == 'outputAllGain':
                                dofval = self.validate_gain_for_snmp(oid, dofval, instance)
                        except InvalidStateChange as e:
                            self.result = str(e)
                            logging.warning(self.result)
                            return None, dofkey, dofval
                        # Converting string to int for the matrix
                        # if oid == 'outputAllAGCMode':
                        #     if dofval == "DISABLED":
                        #         dofval = 0
                        #     elif dofval == "ENABLED":
                        #         dofval = 1
                        # elif oid == 'inputAllGain' or oid == 'outputAllGain':
                        #     #enforcing the hardware bounds for gain (-14.5, +17.0)
                        #     try:
                        #         gain_float = float(dofval)
                        #         if gain_float < -14.5 or gain_float > 17.0:
                        #             raise Exception(f'FAIL: Gain {gain_float} exceeds hardware limitations of [-14.5, +17.0]')
                        #         #dofval = f"{gain_float:+.1f}"
                        #     except ValueError:
                        #         raise Exception(f'Gain {dofval} is not a valid entry.')

                        #     if oid == 'outputAllGain':
                        #         output_fields = self.current_settings.get('proprietary_fields', {}).get('output_ports', {})
                        #         port_data = output_fields.get(f'{instance}', {})
                        #         agc_state = port_data.get('agc_mode', 'DISABLED')
                                
                        #         if str(agc_state).upper() == "ENABLED":
                        #             raise Exception("Invalid command. Gain cannot be manually set when AGC Mode is enabled.")

                        if with_instance == True:
                            oid = oid + '.' + instance
                        logging.info(f"LOOKUP_OID: Found oid {oid}")
                        break

        if oid == None and with_instance == False:
            return self.lookup_oid(incoming_msgdata, with_instance=True)

        return oid, dofkey, dofval
    
    def lookup_hardcoded_field(self, dofkey, dofval, instance, incoming_msgdata):
        """
        Look up hardcoded field that maps to dof_name and changes the current setting if found

        Parameters:
        -----------
        self - current instance of class
        dofkey - dof_name
        dofval - value of dof_name
        instance - dof_name index
        incoming_msgdata - command in json/as a dict (ex. {'fault_log': {'clear_all': 'CLEAR'}})

        Returns:
        --------
        oid - the hardcoded field that dof_name maps to, empty if hardcoded field is not found or command is invalid
        """
        oid = None

        #list of hardcoded fields
        hardcoded = ["fault_log.entries.clear", 
                    "fault_log.clear_all", 
                    "log.escalation_levels", 
                    "log.clear_all_entries"]

        # change low threshold
        # clear fault entry 
        if dofkey == hardcoded[0]:
            if 'fault_log' in self.current_settings and 'entries' in self.current_settings['fault_log']:
                if instance in self.current_settings['fault_log']['entries'] and dofval == "CLEAR":
                    try:
                        if self.current_settings['fault_log']['entries'][f"{instance}"]['id'] == incoming_msgdata['fault_log']['entries'][f"{instance}"].get('id'):
                            #only passes to here if all above fields exist
                            oid = "HardCodeClearFaultEntry"
                            del self.current_settings['fault_log']['entries'][f"{instance}"]
                            self.successful = True
                    except:
                        #one of the above fields didn't exist
                        logging.info("unable to clear log from fault_log")
        # clear all fault entries
        elif dofkey == hardcoded[1]: 
            if dofval == "CLEAR" and 'fault_log' in self.current_settings:
                oid = "HardCodeClearFault"
                self.current_settings['fault_log'].update({"entries": {}})
                self.successful = True
        # change logging level
        elif dofkey == hardcoded[2]:
            # dict that maps text to logging level
            ecs_lvl = {'CRITICAL': logging.CRITICAL,
                    'ERROR': logging.ERROR,
                    'WARNING': logging.WARNING,
                    'DEBUG': logging.DEBUG,
                    'INFO': logging.INFO}
            dofval = dofval.upper()
            # update current settings and logger with new logging level
            if dofval in ecs_lvl.keys():
                oid = "HardCodeEscalateLog"
                if not 'log' in self.current_settings:
                    self.current_settings['log'] = {}
                self.current_settings['log']['escalation_levels'] = dofval
                logging.getLogger().setLevel(ecs_lvl[dofval])
                self.successful = True
        # clear all log entries
        elif dofkey == hardcoded[3]:
            dofval = dofval.upper()
            if dofval == "CLEAR_ENTRIES":
                oid = "HardCodeClearLogs"
                if not 'log' in self.current_settings:
                    self.current_settings['log'] = {}
                #clear logs
                self.current_settings['log']['entries'] = {}
                self.current_settings['log']['state'] = "NO_ENTRIES"
                self.successful = True
        if dofkey in hardcoded:
            if oid != None:
                logging.info(f"LOOKUP_HARDCODED_FIELD: Found oid {oid}")
                CSI.update_settings(self.current_settings)
            else:
                logging.info("Invalid command passed")
                raise Exception('Invalid command passed')

        return oid

    def update_settings_on_device(self, session, incoming_msgdata):
        """
        Performs an snmp set for the device and updates the current settings before restarting the poller

        Parameters:
        -----------
        self - current instance of class
        session - session object
        incoming_msgdata - command in json/as a dict (ex. {'fault_log': {'clear_all': 'CLEAR'}})
        """
        logging.info("update_settings_on_device starting...")

        #list hardcoded fields to handle internally
        hardcoded = ["HardCodeClearFaultEntry", 
                    "HardCodeClearFault", 
                    "HardCodeEscalateLog", 
                    "HardCodeClearLogs"]

        try_to_set_flag = False

        if session:
            self.current_settings = CSI.get_settings(CSI.service_name)

            # set log entry index
            i = self.update_log_entry_index()

            # Find the oid
            oid, dofkey, dofval = self.lookup_oid(incoming_msgdata)

            if oid is not None:
                logging.info(f"update_settings_on_device: dofkey is {dofkey}")
                logging.info(f"SNMP setting oid {oid} to value {dofval}")

                self.update_sucessful_set_info(i, oid, incoming_msgdata)

                try:
                    # skip session.set if oid maps to a hardcoded field
                    if oid not in hardcoded:
                        self.successful = session.set(oid, dofval)
                    else:
                        self.successful = True

                    if not self.successful:
                        self.update_fail_set_info(i, incoming_msgdata)
                        logging.info("snmpset failed")
                        self.result = "snmpset failed"

                    if self.successful:
                        self.result = "SNMP Set successful"
                        # self.successful = True
                        logging.info("Reinitiate Poll")
                        CSI.update_settings(self.current_settings)

                    restart_snmp_poller(self.proxycfg)

                except Exception as e:
                    self.update_fail_set_info(i, incoming_msgdata)
                    self.result = "SNMP Set Failure"
                    logging.info(f"SNMP Set failed: {e}")

                logging.info(f"result of set is {self.result}")
            else:
                self.update_fail_set_info(i, incoming_msgdata)
                logging.info(f"dofkey {dofkey} NOT FOUND in list of settable DoF variables or is INVALID")
                self.result = "dofkey " + dofkey + " NOT FOUND in list of settable DoF variables or is INVALID"

    def convert_to_dotted_notation(self, msg, with_instance=False):
        """
        Converts dict to dotted notation, or to a dof_name

        Parameters:
        -----------
        self - current instance of class
        msg - command in json/as a dict (ex. {'fault_log': {'clear_all': 'CLEAR'}})
        with_instance - either True or False, always False on first iteration

        Returns:
        --------
        s - dof_name, dotted string
        val - value of s
        instance - index of s
        """
        logging.debug(f"Starting convert_to_dotted_notation with msg {msg}")
        s=""
        instance=""
        found_instance = False

        while type(msg) is dict:
            for k,v in msg.items():
                logging.debug(f'msg is {msg}, len of msg is {len(msg.keys())}')

                # do not add to search string s if at second-last level
                # if v looks like {state: 2}, then k has the instance
                if with_instance:
                    if not found_instance:
                        if not self.has_nested_dictionary(v):
                            logging.debug("has_nested_dictionary is False")
                            found_instance = True
                            instance = k
                            msg = msg[k]
                            break

                val = v
                if s == "":
                    s = k
                else:
                    s = s + "." + k
                msg = msg[k]
                logging.debug(f"k is {k}, v is {v}, s is {s}, instance is {instance}")

                break

        # return dotted string ("common.device.location") and val ("Manchester, NH")
        return s, val, instance

    def has_nested_dictionary(self, d):
        """
        Checks if current level of the dict has a nested dictionary

        Parameters:
        -----------
        d - refers to the current level of the dict

        Returns:
        --------
        boolean - either True or False
        """
        # returns whether there is a nested dictionary
        try:
            logging.debug(f"has_nested_dictionary d is {d}")
            logging.debug(f"first value is {list(d.values())[0]}")
            return (type(list(d.values())[0]) is dict)
        except:
            return False
        
    def update_log_entry_index(self):
        """
        Sets the index for a new log entry

        Parameters:
        -----------
        self - current instance of class

        Returns:
        --------
        i - int
        """
        # get log entry index
        i = 1

        if not 'log' in self.current_settings:
            self.current_settings['log'] = {}
        if not 'entries' in self.current_settings['log']:
            self.current_settings['log']['entries'] = {}

        if len(self.current_settings['log']['entries']) > 0:
            i = int(list(self.current_settings['log']['entries'])[-1])+1
        return i

    def update_sucessful_set_info(self, i, oid, incoming_msgdata):
        """
        Updates the settings with a session response and new log entry

        Parameters:
        -----------
        self - current instance of class
        i - index of new log entry
        oid - oid thats mapped to the dof_name listed in incoming_msgdata
        incoming_msgdata - command in json/as a dict
        """
        self.current_settings['parameters']['ready'] = "READY"

        # dict that maps logging level to text
        log_tbl = {logging.CRITICAL: 'CRITICAL',
                logging.ERROR: 'ERROR',
                logging.WARNING: 'WARNING',
                logging.DEBUG: 'DEBUG',
                logging.INFO: 'INFO'}
                
        # get current logging level in text
        log_state = log_tbl[logging.getLogger().getEffectiveLevel()]

        #update log entry 
        if oid != 'HardCodeClearLogs':
            self.current_settings['log']['state'] = "HAS_ENTRIES"
            # Clear previous logs
            self.current_settings['log']['entries'] = {}
            self.current_settings['log']['entries'][f"{i}"] = {"index": f"{i}", "id": f"{uuid.uuid4()}", "timestamp": f"{time.time()}", "level": f"{log_state}", "description": f"SNMP Set Success with {incoming_msgdata}."}

    def update_fail_set_info(self, i, incoming_msgdata):
        """
        Updates the settings with a session reject and new log entry

        Parameters:
        -----------
        self - current instance of class
        i - index of new log entry
        incoming_msgdata - command in json/as a dict
        """
        self.current_settings['parameters']['ready'] = "READY"

        # update log entry
        self.current_settings['log']['state'] = "HAS_ENTRIES"
        self.current_settings['log']['entries'] = {}  # Clear previous logs accumulation
        self.current_settings['log']['entries'][f"{i}"] = {"index": f"{i}", "id": f"{uuid.uuid4()}", "timestamp": f"{time.time()}", "level": "ERROR", "description": f"SNMP Set Failure. Invalid command passed: {incoming_msgdata}."}
        CSI.update_settings(self.current_settings)
