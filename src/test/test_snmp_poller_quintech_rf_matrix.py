#!/usr/bin/python3
# (c) 2023 The MITRE Corporation, All Rights Reserved
"""! @brief # Unit tests supporting the Make MODEL SNMP Poller Class """
##
# @mainpage Common Software Interface PDK
#
# @section description_main Description
# Unit tests supporting the Make MODEL SNMP Poller Class

import logging

#testing libraries
import unittest
import unittest.mock as mocker

#import SNMP libraries to easily mock them
from easysnmp import Session
import easysnmp

import sys

#tell it where to find csi_properties
sys.path.append("src/commonlib/csi_properties")
from csi_properties import CSI_Properties

#mocker.patch.object(CSI_Properties, '__init__', )

#tell it where to find the code
sys.path.append("src/csi_make_model")
from snmp_poller import SnmpPoller


class TEST_SNMP_POLLER_MAKE_MODEL(unittest.TestCase):
    
    @classmethod
    @mocker.patch('builtins.open', mocker.mock_open(read_data=''))
    def setUpClass(self):
        self.mock_csi = mocker.create_autospec(CSI_Properties, return_value=[])
            
        self.test_obj = SnmpPoller()

        self.test_obj.settable_dof_vars = {}
        self.test_obj.settable_dof_vars['properties'] = {}

        self.test_obj.tracked_snmp_vars = {}
        self.test_obj.tracked_snmp_vars['properties'] = {}
        self.test_obj.tracked_snmp_vars['polled_oids'] = ['example']

    @classmethod
    def tearDownCClass(self):
        del self.test_obj

if __name__ == '__main__':
    unittest.main()