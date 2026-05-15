#!/usr/bin/python3
# (c) 2023 The MITRE Corporation, All Rights Reserved
"""! @brief # Unit tests supporting the generic SNMP Poller Class """
##
# @mainpage Common Software Interface PDK
#
# @section description_main Description
# Unit tests supporting the generic SNMP Poller Class

import logging

#testing libraries
import unittest
import unittest.mock as mocker

#import SNMP libraries to easily mock them
from easysnmp import Session
import easysnmp

#other imports to mock
import uuid
import time

import sys

#tell it where to find csi_properties
sys.path.append("src/commonlib/csi_properties")
from csi_properties import CSI_Properties

#tell it where to find the code
sys.path.append("src/csi_make_model")
from snmp_poller import SnmpPoller


class TEST_SNMP_POLLER(unittest.TestCase):
    
    @classmethod
    @mocker.patch('builtins.open', mocker.mock_open(read_data=''))
    def setUpClass(self):
        self.mock_csi = mocker.create_autospec(CSI_Properties, return_value=[])
        
        self.test_obj = SnmpPoller()

        #some variables should be set up before the poller is called
        self.test_obj.settable_dof_vars = {}
        self.test_obj.settable_dof_vars['properties'] = {}

        self.test_obj.tracked_snmp_vars = {}
        self.test_obj.tracked_snmp_vars['properties'] = {}
        self.test_obj.tracked_snmp_vars['polled_oids'] = ['example']
 
    @classmethod
    def tearDownCClass(self):
        del self.test_obj

    def test_dof_update_no_instance(self):
        self.test_obj.current_settings = {}
        self.test_obj.dof_update('fault_log.clear_all', 'CLEAR_ALL', None)

        logging.debug(f"{self.test_obj.current_settings}")

        self.assertEqual(self.test_obj.current_settings, {'fault_log': {'clear_all': 'CLEAR_ALL'}})

    def test_dof_update_with_instance(self):
        self.test_obj.current_settings = {}
        self.test_obj.dof_update('parameters.outlets.state', 'POWER_OFF', 4)

        logging.debug(f"{self.test_obj.current_settings}")

        self.assertEqual(self.test_obj.current_settings, {'parameters': {'outlets': {4: {'state': 'POWER_OFF'}}}})

    def test_large_dof_update(self):
        self.test_obj.current_settings = {}
        self.test_obj.dof_update('fault_log.clear_all', 'CLEAR_ALL', None)
        self.test_obj.dof_update('parameters.outlets.state', 'POWER_OFF', 4)
        self.test_obj.dof_update('parameters.outlets.state', 'POWER_ON', 5)
        self.test_obj.dof_update('parameters.device.ip_address', '192.168.2.1', None)

        logging.debug(f"{self.test_obj.current_settings}")

        expected_result = {'parameters':
                                {'device': {'ip_address': '192.168.2.1'},
                                'outlets':
                                    {4: {'state': 'POWER_OFF'},
                                    5: {'state': 'POWER_ON'}}
                                },
                            'fault_log':
                                {'clear_all': 'CLEAR_ALL'}
                            }
        
        self.assertDictEqual(self.test_obj.current_settings, expected_result)

    def test_update_setting_if_tracking_no_instance(self):
        self.test_obj.current_settings = {}
        self.test_obj.tracked_snmp_vars['properties'] = {'tlpDeviceModel': {"dof_name": "device.model"}}
        self.test_obj.update_setting_if_tracking('tlpDeviceModel', 0, 1, 'PDUMH20')

        logging.debug(f"{self.test_obj.tracked_snmp_vars}")
        logging.debug(f"{self.test_obj.current_settings}")

        self.assertEqual(self.test_obj.current_settings, {'device' : {'model': 'PDUMH20'}})

    def test_update_setting_if_tracking_with_instance(self):
        self.test_obj.current_settings = {}
        self.test_obj.tracked_snmp_vars['properties'] = {'tlpPduOutletState': 
                                                            {"dof_name": "parameters.outlets.state",
                                                            "use_oid_index": True,
                                                            "settable": True}
                                                        }
        #tripplite snmp commands return '1.X' with X as the index
        self.test_obj.update_setting_if_tracking('tlpPduOutletState', '4', 1, "POWER_ON")

        logging.debug(f"{self.test_obj.current_settings}")

        self.assertEqual(self.test_obj.current_settings, {'parameters': {'outlets': {'4': {'state': 'POWER_ON'}}}})

    def test_large_update_setting_if_tracking(self):
        self.test_obj.current_settings = {}
        self.test_obj.tracked_snmp_vars['properties'] = {'tlpPduOutletState': 
                                                            {"dof_name": "parameters.outlets.state",
                                                            "use_oid_index": True,
                                                            "settable": True},
                                                        'tlpDeviceModel':
                                                            {"dof_name": "device.model"},
                                                        'tlpDeviceName':
                                                            {"dof_name": "device.label",
                                                            "settable": True}
                                                        }
        self.test_obj.update_setting_if_tracking('tlpDeviceModel', 0, 1, 'PDUMH20')
        self.test_obj.update_setting_if_tracking('tlpPduOutletState', '4', 1, 'POWER_OFF')
        self.test_obj.update_setting_if_tracking('tlpPduOutletState', '5', 1, 'POWER_ON')
        self.test_obj.update_setting_if_tracking('tlpDeviceName', 0, 1, 'ePDU')

        logging.debug(f"{self.test_obj.tracked_snmp_vars}")
        logging.debug(f"{self.test_obj.current_settings}")

        expected_result = {'parameters':
                                {'outlets':
                                    {'4': {'state': 'POWER_OFF'},
                                    '5': {'state': 'POWER_ON'}}
                                },
                            'device': 
                                    {'label': 'ePDU',
                                    'model': 'PDUMH20'}
                            }
        
        self.assertDictEqual(self.test_obj.current_settings, expected_result)

    def test_update_setting_if_not_tracking_not_in_mapping(self):
        self.test_obj.current_settings = {}
        self.test_obj.tracked_snmp_vars['properties'] = {}
        self.test_obj.update_setting_if_tracking('tlpNotAnOID', 1, 1, 'value')

        logging.debug(f"{self.test_obj.current_settings}")

        self.assertEqual(self.test_obj.current_settings, {})

    
    def test_perform_poll_no_instance(self):
        self.test_obj.current_settings = {}
        self.test_obj.tracked_snmp_vars['properties'] = {"tlpDeviceName": {"dof_name": "device.label", "settable": True}}

        item = easysnmp.SNMPVariable()
        item.value = 'test'
        item.oid = 'tlpDeviceName'
        item.oid_index = ''

        session = mocker.patch.object(Session, '__init__')
        session.walk = mocker.Mock(return_value=[item])

        self.test_obj.perform_poll(session)

        logging.debug(f"self.test_obj.current_settings")

        self.assertEqual(self.test_obj.current_settings, {'device': {'label': 'test'}})
        
    def test_perform_poll_with_instance(self):
        self.test_obj.current_settings = {}
        self.test_obj.tracked_snmp_vars['properties'] = {'tlpPduOutletName': 
                                                            {"dof_name": "parameters.outlets.list_id",
                                                            "use_oid_index": True,
                                                            "settable": True}
                                                        }
        
        item = easysnmp.SNMPVariable()
        item.oid = 'tlpPduOutletName'
        item.value = 'test'
        item.oid_index = '4'
        
        session = mocker.patch.object(Session, '__init__')
        session.walk = mocker.Mock(return_value=[item])

        self.test_obj.perform_poll(session)

        logging.debug(f"{self.test_obj.current_settings}")

        self.assertEqual(self.test_obj.current_settings, {"parameters": {"outlets": {"4": {"list_id": "test"}}}})

    def test_large_perform_poll(self):
        self.test_obj.current_settings = {}
        self.test_obj.tracked_snmp_vars['properties'] = {'tlpPduOutletName': 
                                                            {"dof_name": "parameters.outlets.list_id",
                                                            "use_oid_index": True,
                                                            "settable": True},
                                                        'tlpDeviceModel':
                                                            {"dof_name": "device.model"},
                                                        'tlpDeviceName':
                                                            {"dof_name": "device.label",
                                                            "settable": True}
                                                        }

        item1 = easysnmp.SNMPVariable()
        item1.oid = "tlpPduOutletName"
        item1.oid_index = "4"
        item1.value = "test1"

        item2 = easysnmp.SNMPVariable()
        item2.oid = "tlpDeviceModel"
        item2.oid_index = "5"
        item2.value = "model"

        item3 = easysnmp.SNMPVariable()
        item3.oid = "tlpPduOutletName"
        item3.oid_index = "5"
        item3.value = "test2"

        item4 = easysnmp.SNMPVariable()
        item4.oid = "tlpDeviceName"
        item4.oid_index = ""
        item4.value = "name"

        session = mocker.patch.object(Session, '__init__')
        session.walk = mocker.Mock(return_value=[item1, item2, item3, item4])

        self.test_obj.perform_poll(session)

        logging.debug(f"{self.test_obj.current_settings}")

        expected_result = {
            "parameters": {
                "outlets": {
                    "4": {
                        "list_id": "test1"
                    },
                    "5": {
                        "list_id": "test2"
                    }
                }
            },
            "device": {
                "model": "model",
                "label": "name"
            }
        }

        self.assertDictEqual(self.test_obj.current_settings, expected_result)

    def test_create_session(self):
        with mocker.patch.object(Session, "__init__") as session_mock:
            session_mock.return_value = None
            self.test_obj.create_session(hostname="192.168.1.2", community="public", version="1")
        
            session_mock.assert_called_once_with(hostname="192.168.1.2", community="public", version=1)

    def test_get_new_index_log_empty(self):
        self.test_obj.current_settings = {}
        i = self.test_obj.get_new_index("log")
        self.assertEqual(i, 1)

    def test_get_new_index_log(self):
        self.test_obj.current_settings = {
            "log": {
                "entries": {
                    "1": {},
                    "2": {},
                    "3": {}
                }
            }
        }

        i = self.test_obj.get_new_index("log")

        self.assertEqual(i, 4)

    def test_get_new_index_fault_log_empty(self):
        self.test_obj.current_settings = {
            "log": {
                "entries": {
                    "1": {},
                    "2": {},
                    "3": {}
                }
            }
        }
        i = self.test_obj.get_new_index("fault_log")
        self.assertEqual(i, 1)

    def test_get_new_index_fault_log(self):
        self.test_obj.current_settings = {
            "log": {
                "entries": {
                    "1": {},
                    "2": {},
                    "3": {}
                }
            },
            "fault_log": {
                "entries": {
                    "2": {}
                }
            }
        }
        i = self.test_obj.get_new_index("fault_log")
        self.assertEqual(i, 3)

    @mocker.patch.object(CSI_Properties, 'update_settings')
    @mocker.patch.object(uuid, 'uuid4', return_value='00213a43-05d8-464f-a280-9dab6091fa01')
    @mocker.patch.object(time, 'time', return_value=1738703987.5130992)
    def test_update_log_and_ready_state_down(self, CSI, mock_uuid, mock_time):
        self.test_obj.current_settings = {}
        self.test_obj.current_settings['parameters'] = {}
        self.test_obj.current_settings['parameters']['ready'] = "device active"
        self.test_obj.update_log_and_ready_state("DOWN", "UP")

        expected_settings = {
            'parameters': {'ready': 'HARDWARE_UNRESPONSIVE'},
            'log': {
                'entries': {
                    '1': {
                        'index': '1', 
                        'id': '00213a43-05d8-464f-a280-9dab6091fa01', 
                        'timestamp': '1738703987.5130992', 
                        'level': 'WARNING', 
                        'description': ' State of hardware is unresponsive.'
                    }
                }, 
                'state': 'HAS_ENTRIES'
            }
        }

        self.assertEqual(self.test_obj.current_settings['parameters']['ready'], 'HARDWARE_UNRESPONSIVE')
        assert CSI.called
        self.maxDiff = None
        self.assertDictEqual(self.test_obj.current_settings, expected_settings)

    @mocker.patch.object(CSI_Properties, 'update_settings')
    def test_update_log_and_ready_state_already_down(self, CSI):
        self.test_obj.current_settings = {}
        self.test_obj.current_settings['parameters'] = {}
        self.test_obj.current_settings['parameters']['ready'] = "device active"
        self.test_obj.update_log_and_ready_state("DOWN", "DOWN")

        self.assertNotEqual(self.test_obj.current_settings['parameters']['ready'], 'HARDWARE_UNRESPONSIVE')
        assert not CSI.called

    @mocker.patch.object(CSI_Properties, 'update_settings')
    def test_update_log_and_ready_state_up(self, CSI):
        self.test_obj.current_settings = {}
        self.test_obj.current_settings['parameters'] = {}
        self.test_obj.current_settings['parameters']['ready'] = "device active"
        self.test_obj.update_log_and_ready_state("UP", "UP")

        self.assertNotEqual(self.test_obj.current_settings['parameters']['ready'], 'HARDWARE_UNRESPONSIVE')
        assert not CSI.called


if __name__ == '__main__':
    unittest.main()