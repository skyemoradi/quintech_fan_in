#!/usr/bin/python3
# (c) 2023 The MITRE Corporation, All Rights Reserved
"""! @brief # Unit tests supporting the generic SNMP Poller Class """
##
# @mainpage Common Software Interface PDK
#
# @section description_main Description
# Unit tests supporting the generic SNMP Setter Class

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
from snmp_setter import SnmpSetter


class SNMP_SETTER_UNIT_TEST(unittest.TestCase):
    
    @classmethod
    @mocker.patch('builtins.open', mocker.mock_open(read_data=''))
    def setUpClass(self):
        self.mock_csi = mocker.create_autospec(CSI_Properties, return_value=[])

        self.test_obj = SnmpSetter()

        self.test_obj.settable_dof_vars = {}
        self.test_obj.settable_dof_vars['properties'] = {}

        self.test_obj.tracked_snmp_vars = {}
        self.test_obj.tracked_snmp_vars['properties'] = {}
        self.test_obj.tracked_snmp_vars['polled_oids'] = ['example']

    def tearDownCClass(self):
        del self.test_obj

    @mocker.patch.object(CSI_Properties, 'update_settings')
    @mocker.patch.object(uuid, 'uuid4', return_value='00213a43-05d8-464f-a280-9dab6091fa01')
    @mocker.patch.object(time, 'time', return_value=1738703987.5130992)
    def test_update_successful_set_info(self, CSI, uuid_obj, time_obj):
        self.test_obj.current_settings = {
            'parameters': {},
            'log': {
                'entries': {}
            }
        }

        self.test_obj.update_sucessful_set_info(1, '', "{'fault_log': {'clear_all': 'CLEAR'}}")

        expected_result = {
            'parameters': {
                'ready': 'READY'
            },
            'log': {
                'state': 'HAS_ENTRIES',
                'entries': {
                    '1': {
                        'index': '1',
                        'id': '00213a43-05d8-464f-a280-9dab6091fa01',
                        'timestamp': '1738703987.5130992',
                        'level': 'INFO',
                        'description': "SNMP Set Success with {'fault_log': {'clear_all': 'CLEAR'}}."
                    }
                }
            }
        }
        
        self.assertDictEqual(self.test_obj.current_settings, expected_result)

    @mocker.patch.object(CSI_Properties, 'update_settings')
    @mocker.patch.object(uuid, 'uuid4', return_value='00213a43-05d8-464f-a280-9dab6091fa01')
    @mocker.patch.object(time, 'time', return_value=1738703987.5130992)
    def test_update_fail_set_info(self, CSI, uuid_obj, time_obj):
        self.test_obj.current_settings = {
            'parameters': {},
            'log': {
                'entries': {}
            }
        }

        self.test_obj.update_fail_set_info(1, "{'fault_log': {'clear_all': 'FAIL'}}")

        expected_result = {
            'parameters': {
                'ready': 'READY'
            },
            'log': {
                'state': 'HAS_ENTRIES',
                'entries': {
                    '1': {
                        'index': '1',
                        'id': '00213a43-05d8-464f-a280-9dab6091fa01',
                        'timestamp': '1738703987.5130992',
                        'level': 'ERROR',
                        'description': "SNMP Set Failure. Invalid command passed: {'fault_log': {'clear_all': 'FAIL'}}."
                    }
                }
            }
        }

        self.assertDictEqual(self.test_obj.current_settings, expected_result)

    def test_update_log_entry_index_empty(self):
        self.test_obj.current_settings = {}
        i = self.test_obj.update_log_entry_index()

        self.assertEqual(i, 1)

    def test_update_log_entry_index(self):
        self.test_obj.current_settings = {
            "log": {
                "entries": {
                    "1": {},
                    "2": {},
                    "3": {}
                }
            }
        }

        i = self.test_obj.update_log_entry_index()

        self.assertEqual(i, 4)

    #TODO: only checks first position - OK?
    #if csi will handle more than one field, this should be checked differently
    def test_has_nested_dictionary_true(self):
        settings = {
            'device': {}
        }

        result = self.test_obj.has_nested_dictionary(settings)

        self.assertTrue(result)

    def test_has_nested_dictionary_false(self):
        settings = {
            'label': 'name',
        }

        result = self.test_obj.has_nested_dictionary(settings)

        self.assertFalse(result)

    def test_convert_to_dotted_notation_no_instance(self):
        json_no_instance = {'fault_log': {'clear_all': 'CLEAR'}}
        dot_string, value, instance = self.test_obj.convert_to_dotted_notation(json_no_instance)

        logging.debug(f"dot_string: {dot_string}, value: {value}, instance: {instance}")

        self.assertEqual(dot_string, 'fault_log.clear_all')
        self.assertEqual(value, 'CLEAR')
        self.assertEqual(instance, '')

    def test_convert_to_dotted_notation_with_instance(self):
        json_with_instance = {'parameters': {'outlets': {'4': {'state': 'POWER_OFF'}}}}
        dot_string, value, instance = self.test_obj.convert_to_dotted_notation(json_with_instance, True)

        logging.debug(f"dot_string: {dot_string}, value: {value}, instance: {instance}")

        self.assertEqual(dot_string, 'parameters.outlets.state')
        self.assertEqual(value, 'POWER_OFF')
        self.assertEqual(instance, '4')

    def test_lookup_oid_no_instance(self):
        json_no_instance = {'device': {'label': 'device name'}}
        self.test_obj.settable_dof_vars['properties'] = {
            'tlpDeviceName': {
                'dof_name': 'device.label',
                'settable': True
            }
        }

        oid, dofkey, dofval = self.test_obj.lookup_oid(json_no_instance)

        self.assertEqual(oid, 'tlpDeviceName')
        self.assertEqual(dofkey, 'device.label')
        self.assertEqual(dofval, 'device name')

    def test_lookup_oid_with_instance(self):
        #making outlet name settable for this test example
        json_with_instance = {'parameters': {'outlets': {'2': {'list_id': 'outlet name'}}}}
        self.test_obj.settable_dof_vars['properties'] = {
            'tlpPduOutletName': {
                'use_oid_index': True,
                'dof_name': 'parameters.outlets.list_id',
                'settable': True
            }
        }
        self.test_obj.current_settings = {'parameters': {}}

        oid, dofkey, dofval = self.test_obj.lookup_oid(json_with_instance, with_instance=True)

        self.assertEqual(oid, 'tlpPduOutletName.2')
        self.assertEqual(dofkey, 'parameters.outlets.list_id')
        self.assertEqual(dofval, 'outlet name')


if __name__ == '__main__':
    unittest.main()