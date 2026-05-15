#!/usr/bin/env python3
# (c) 2023 The MITRE Corporation, All Rights Reserved
"""! @brief Common routines between RESTful server and Proxy """
##
# @mainpage Common Software Interface PDK
#
# @section description_main Description
# initialize_database() needs to be written for each proxy
# Proxies are responsible for keeping the following up to date in the DB:
# settings, discover, and landing_page
#

import logging
from csi_properties import CSI_Properties
from pydantic import BaseModel, Field
from enum import Enum
from typing import List
from typing import Dict
from mergedeep import merge
import uuid

class ProprietaryInputPort(BaseModel):
    list_id: str = Field(
        None,
        description='User-friendly label assigned to the input port',
        title='Input port name',
        readOnly=False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    rf_level_dBm: float | None = Field(
        None,
        description='Measured RF level at the input port in dBm',
        title='Input RF Level (dBm)',
        readOnly=True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    
class ProprietaryOutputPort(BaseModel):
    agc_enable: str | None = Field(
          None,
          description="Quintech output AGC mode",
          enum=["DISABLED", "ENABLED"],
          readOnly=False,
    )
    gain_db: float | None = Field(
          None,
          description="Quintech output gain",
          readOnly=False,
      )

class ProprietaryFields(BaseModel):
      output_ports: Dict[str, ProprietaryOutputPort] = Field(default_factory=dict)
      input_ports: Dict[str, ProprietaryInputPort] = Field(default_factory=dict)

class ParamInputPorts(BaseModel):
    """
    Field definitions for the Parameter Input Ports Schema
    """
    list_id: str = Field(
        None,
        description='User-friendly label assigned to the input port',
        title='Input port name',
        readOnly=False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    gain_db: float = Field(
        None,
        description='Amount of gain applied to an input in the gain stage',
        title='Gain',
        min=-14.5,
        max=17.0,
        readOnly=False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ", "WRITE"]
        },
    )
    connected_outputs: List[str] = Field(
        default_factory=list,
        description='List of output ports to which this input is connected',
        title='Connected Outputs',
        readOnly=False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ", "WRITE"]
        },
    )

class ParamOutputPorts(BaseModel):
    """
        Field definitions for the Parameter Output Ports Schema.
    """
    list_id: str = Field(
        None,
        description='User-friendly label assigned to the output port',
        title='Output port name',
        readOnly=False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )

class SensorOutputPorts(BaseModel):
    """    
        Field definitions for the Sensor Output Ports Schema.
    """
    list_id: str = Field(
        None,
        description='User-friendly label assigned to the output port',
        title='Output port name',
        readOnly=True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    output_power_dBm: str = Field(
        None,
        description='Measured power on the output port',
        title='Output Power (dBm)',
        readOnly=True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )

class Parameters(BaseModel):
    # description of Parameters
    """
    Field definitions for the Parameters Schema
    """
    ready: str = Field(
        None,
        description= 'This object describes the state of readiness for the container',
        title= 'Ready State',
        enum= ['INITIALIZING: No current or previous state information is available as the container has not communicated with the C2 node', 
               'HARDWARE_UNRESPONSIVE: The container is unable to communciate with external support hardware',
               'HARDWARE_BUSY: The hardware is executing a command that has not yet completed and the container is waiting for the process to complete',
               'READY: The container is fully initialized'],
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    matrix_type: str = Field(
        default='FAN_IN',
        description='Indicates the RF Matrix type',
        title='Matrix Type',
        enum=['FAN_OUT', 'FAN_IN', 'BIDIRECTIONAL'],
        readOnly=True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    input_ports: Dict[str, ParamInputPorts] = Field(default_factory=dict)
    output_ports: Dict[str, ParamOutputPorts] = Field(default_factory=dict)

class Sensors(BaseModel):
    # description of Sensors
    """
    Field definitions for the Sensors Schema
    """
    temperature_C: str = Field(
        None,
        description='Module temperature in Celsius',
        title='Temperature (C)',
        readOnly=True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    min_input_gain_dB: float = Field(
        default=-14.5,
        description='This object displays the minimum input gain of a module',
        title='Minimum Input Gain',
        readOnly=True,
    )
    max_input_gain_dB: float = Field(
        default=17.0,
        description='This object displays the maximum input gain of a module',
        title='Maximum Input Gain',
        readOnly=True,
    )
    min_output_gain_dB: float = Field(
        default=-18.5,
        description='This object displays the minimum output gain of a module',
        title='Minimum Output Gain',
        readOnly=True,
    )
    max_output_gain_dB: float = Field(
        default=13.0,
        description='This object displays the maximum output gain of a module',
        title='Maximum Output Gain',
        readOnly=True,
    )
    output_ports: Dict[str, SensorOutputPorts] = Field(default_factory=dict)

class FaultEntries(BaseModel):
    # description of Entries
    """
    Field definitions for the Entries Schema
    """
    index: int = Field(
        None,
        description= 'This object is used to index the fault events',
        title= 'Fault Index',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    clear: str = Field(
        None,
        description= 'This object is used to clear the fault entry. The fault entry ID must be specified with the clear command.',
        title= 'Clear Fault Entry',
        enum= ['CLEAR: Clears fault entry'],
        readOnly= False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ", "WRITE"]
        },
    )
    id: str = Field(
        None,
        description= 'This object is used as a global ID for each fault',
        title= 'Global Unique ID',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    timestamp: str = Field(
        None,
        description= 'This object is used as a timestamp for the fault event',
        title= 'Timestamp of Fault',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    description: str = Field(
        None,
        description= 'This object is used to describe the fault event',
        title= 'Fault Description',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )

class Faults(BaseModel):
    # description of Faults
    """
    Field definitions for the Faults Schema
    """
    clear_all: str = Field(
        None,
        description= 'This object is used to clear all faults',
        title= 'Clear Faults',
        enum= ['CLEAR: Clears all faults'],
        readOnly= False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ", "WRITE"]
        },
    )
    entries: Dict[str, FaultEntries] = Field(default_factory=dict)

class LogEntries(BaseModel):
    # description of Log Entries
    '''Field definitions for the Log Entries'''
    index: int = Field(
        None,
        description= 'This object is used to index the log entries',
        title= 'Log Index',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    id: str = Field(
        None,
        description= 'This object contains the global unique identifier for each log entry',
        title= 'Global Unique ID',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    timestamp: str = Field(
        None,
        description= 'This object is used as a timestamp for the fault event',
        title= 'Timestamp of Fault',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    level: str = Field(
        None,
        description= 'This object is used to identify the highest level of criticality of the entry',
        title= 'Entry Level',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    description: str = Field(
        None,
        description= 'This object is used to describe the fault event',
        title= 'Fault Description',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )

class Logs(BaseModel):
    # description of Logs
    '''
    Field definitions for the Container Log Schema
    '''
    escalation_levels: str = Field(
        default= 'INFO',
        description= 'This object sets the level at which a log event should be sent to the system-level log manager',
        title= 'Escalation Levels',
        enum= ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
        readOnly= False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    state: str = Field(
        None,
        description= 'This object describes the log state',
        title= 'Log State',
        enum= ['UNKNOWN', 'NO_ENTRIES', 'HAS_ENTRIES', 'CLEARING_ENTRIES'],
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    clear_all_entries: str = Field(
        None,
        description= 'This object clears the logs for the container and attached hardware',
        title= 'Clear All Entries',
        enum= ['CLEAR_ENTRIES'],
        writeOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ", "WRITE"]
        },
    )
    entries: Dict[str, LogEntries] = Field(default_factory=dict)

class Heartbeat(BaseModel):
    # description of service Heartbeat
    '''
    Field definitions for the Heartbeat Schema
    '''
    update_interval_msec: int = Field(
        None,
        description= 'Sets the interval at which the container sends a heartbeat to the system manager',
        title= 'Update Interval Milliseconds',
        readOnly= False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    last_sent: str = Field(
        None,
        description= 'Timestamp of the last heartbeat sent to the system manager',
        title= 'Last Sent',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )

class Comms(BaseModel):
    ip: str = Field(
        None,
        #alias='ipaddr',
        description='Ip Address',
        title='IP Address',
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    read_community: str = Field(
        None,
        #alias='read_comm',
        description='Read community',
        title='Read community string',
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    write_community: str = Field(
        None,
        #alias='write_comm',
        description='Write community',
        title='Write community string',
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    snmp_version: str = Field(
        None,
        #alias='snmp_ver',
        description='SNMP Version',
        title='SNMP Version',
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )

class Device(BaseModel):
    # description of Device
    """
    Field definitions for the Device Schema
    """
    make: str = Field(
        None,
        description= 'Identifies the make of the connected hardware module.',
        title= 'Make',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    model: str = Field(
        None,
        description= 'Identifies the model of the connected hardware module.',
        title= 'Model',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    serial_number: str = Field(
        None,
        description= 'Identifies the serial number of the connected hardware module.',
        title= 'Serial Number',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    firmware_version: str = Field(
        None,
        description= 'Identifies the firmware version of the connected hardware module.',
        title= 'Firmware Version',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    label: str = Field(
        None,
        description= 'Allows operators to assign descriptors such as \'the one with the blue tape on it.\'',
        title= 'Label',
        readOnly= False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    comms: Comms = Field(default_factory=Comms)

class DebugEnum(str, Enum):
    off = 'OFF'
    reflector = 'REFLECTOR'
    debug = 'DEBUG'
    verbose = 'VERBOSE'

class QuintechRFMatrixSettings(BaseModel):
    field_version_common: str = Field(
        default= 'common-2022.10.07',
        description= 'This object is the version that specifies the schema for the common fields.',
        title= 'Field Version',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    field_version_function: str = Field(
          default='rf_matrix-2023.08.06',
          description='This object specifies the RF Matrix function field version.',
          title='RF Matrix Field Version',
          readOnly=True,
          json_schema_extra={
              "ADMINISTRATOR": ["READ"],
              "SYSTEMOPERATOR": ["READ"]
          },
      )
    description: str = Field(
        default= '',
        description= 'Description of the microservice.',
        title= 'Description',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    service_id: str = Field(
        default= '',
        description= 'Global identifier unique to the service.',
        title= 'Service ID',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    service_name: str = Field(
        default= '',
        description= 'Human-readable identifier that is unique within the endpoint but not unique across all services on all endpoints.',
        title= 'Service Name',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    landing_page: str = Field(
        default= '',
        description= 'The url to the landing page that can be used to C2 non-compliant capabilities.',
        title= 'Landing Page',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    code_version: str = Field(
        default= '',
        description= 'Version for the hardware proxy/software µservice code.',
        title= 'Code Version',
        readOnly= True,
        json_schema_extra={
            "ADMINISTRATOR": ["READ"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    debug_mode: List[DebugEnum] = Field(
        default= [DebugEnum.off],
        description= 'Engineering options used to troubleshoot, debug, simulate, etc. the behavior of a proxy.',
        title= 'Debug Mode',
        readOnly= False,
        json_schema_extra={
            "ADMINISTRATOR": ["READ", "WRITE"],
            "SYSTEMOPERATOR": ["READ"]
        },
    )
    device: Device = Field(default_factory=Device)
    heartbeat: Heartbeat = Field(default_factory=Heartbeat)
    log: Logs = Field(default_factory=Logs)
    fault_log: Faults = Field(default_factory=Faults)
    parameters: Parameters = Field(default_factory=Parameters)
    sensors: Sensors = Field(default_factory=Sensors)
    proprietary_fields: ProprietaryFields = Field(default_factory=ProprietaryFields)

    @staticmethod
    def initialize_database():
        """
        Initializes the database

        Returns:
        --------
        dict - example {'device': {'comms': {...}}...}
        """
        CSI = CSI_Properties("csi_properties.yml")
        return QuintechRFMatrixSettings.initialize_settings(CSI)

    @staticmethod
    def initialize_settings(CSI):
        """
        Retrieves the previous settings if exists and initializes the default settings

        Parameters:
        -----------
        CSI - the csi object

        Returns:
        --------
        dict - example {'device': {'comms': {...}}...}
        """
        logging.info(f"Updating {CSI.settings_key} in database...")
        existing_settings = CSI.get_settings(CSI.service_name)
        current_settings = QuintechRFMatrixSettings().dict()

        logging.info(f'settings are {current_settings}')

        # create default settings
        default_settings = QuintechRFMatrixSettings().dict()
        logging.info(f"default_settings are {default_settings}")

        #keep certain entries if available
        if existing_settings is None:
            logging.info("No settings found in DB, initializing...")
            current_settings['parameters'].update({"ready":"INITIALIZING"})
        else:
            logging.info("Found existing settings, keeping device configuration if possible...")
            merge(current_settings, existing_settings)

            if (not 'service_id' in current_settings) or (not current_settings['service_id']):
                current_settings['service_id'] = f"{uuid.uuid4()}"

            if 'log' in current_settings and 'entries' in current_settings['log'] and len(current_settings['log']['entries']) > 0:
                current_settings['log']['state'] = "HAS_ENTRIES"
            else:
                current_settings['log'].update({"state": "NO_ENTRIES"})

        try:
            # Read default property values from CSI configuration and update return value
            current_settings['device']['comms'].update({"ip": CSI.get_property_by_name('default_ip_address')})
            current_settings['device']['comms'].update({"snmp_version": CSI.get_property_by_name('default_snmp_version')})
            current_settings['device']['comms'].update({"read_community": CSI.get_property_by_name('default_read_community')})
            current_settings['device']['comms'].update({"write_community": CSI.get_property_by_name('default_write_community')})

        except Exception as e: 
            logging.info(f"Could not initialize comms data...{e}")

        logging.debug("initialized comms")

        #set up discover and landing page
        QuintechRFMatrixSettings.initialize_discover(CSI)

        landing_settings = {"landing_page": f"http://{CSI.get_property_by_name('default_ip_address')}"}
        current_settings["landing_page"] = landing_settings["landing_page"]
        CSI.db.put(CSI.landing_page_key, landing_settings)

        logging.debug("initialized discover and landing page")

        #misc csi properties to be ingested
        current_settings["code_version"] = CSI.get_property_by_name('code_version')
        current_settings["description"] = CSI.get_property_by_name('service_description')
        current_settings["debug_mode"] = CSI.get_property_by_name('debug_mode')
        current_settings["service_name"] = CSI.get_property_by_name('service_name')
        current_settings['heartbeat']["update_interval_msec"] = int(CSI.get_property_by_name('heartbeat_interval_msecs'))

        #done, set service to READY
        current_settings['parameters'].update({"ready": "READY"})

        logging.info("finished initializing default fields")

        validated_settings = QuintechRFMatrixSettings(**current_settings).dict()

        merge(default_settings, validated_settings)

        logging.info(f"settings_key is {CSI.settings_key}")
        logging.info(f"default_settings is {default_settings}")
        (CSI.db).put(CSI.settings_key, default_settings)
        return default_settings
    
    @staticmethod
    def initialize_discover(CSI):
        discover_settings = QuintechRFMatrixSettings().schema()

        discover_settings['properties']['debug_mode']['items'] = discover_settings['definitions'].get('DebugEnum')
        discover_settings['properties']['device'] = discover_settings['definitions'].get('Device')
        discover_settings['properties']['device']['properties']['comms'] = discover_settings['definitions'].get('Comms')
        discover_settings['properties']['heartbeat'] = discover_settings['definitions'].get('Heartbeat')
        discover_settings['properties']['log'] = discover_settings['definitions'].get('Logs')
        discover_settings['properties']['log']['properties']['entries'] = discover_settings['definitions'].get('LogEntries')
        discover_settings['properties']['fault_log'] = discover_settings['definitions'].get('Faults')
        discover_settings['properties']['fault_log']['properties']['entries'] = discover_settings['definitions'].get('FaultEntries')
        discover_settings['properties']['parameters'] = discover_settings['definitions'].get('Parameters')
        discover_settings['properties']['sensors'] = discover_settings['definitions'].get('Sensors')
        discover_settings['properties']['parameters'] = discover_settings['definitions'].get('Parameters')
        discover_settings['properties']['parameters']['properties']['input_ports'] = discover_settings['definitions'].get('ParamInputPorts')               
        discover_settings['properties']['parameters']['properties']['output_ports'] = discover_settings['definitions'].get('ParamOutputPorts')
        discover_settings['properties']['sensors']['properties']['output_ports'] = discover_settings['definitions'].get('SensorOutputPorts')
        discover_settings['properties']['proprietary_fields'] = discover_settings['definitions'].get('ProprietaryFields')
        discover_settings['properties']['proprietary_fields']['properties']['input_ports'] = discover_settings['definitions'].get('ProprietaryInputPort')
        discover_settings['properties']['proprietary_fields']['properties']['output_ports'] = discover_settings['definitions'].get('ProprietaryOutputPort')
        
        del discover_settings['definitions']

        CSI.update_discovery_and_notify(discover_settings)
    

    @staticmethod
    def initialize_reflector_settings(CSI):
        """
        Initializes sample values for reflector mode.
        Meant to be used after initialize_database if in reflector mode

        Parameters:
        -----------
        CSI - the csi object

        Returns:
        --------
        dict - example {'device': {'comms': {...}}...}
        """
        mock_msgdata = {
                "device": {"make": "Quintech",
                        "model": "QF1",
                        "label": "Device Label",
                        "firmware_version": "2.56.13:4233M",
                        "serial_number": "00:01:c0:33:ce:75"},
                "parameters": {},
                "sensors": {}
            }

        current_settings = CSI.get_settings(CSI.service_name)
        merge(current_settings, mock_msgdata)

        return current_settings

    # def toJSON(self):
    #     return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
