#!/usr/bin/python3

# Reflector functionality

import logging
from mergedeep import merge
import unittest
import unittest.mock as mocker
import snmp_poller
import snmp_setter

from snmp_config import SNMPConfig
from snmp_setter import SnmpSetter
from snmp_poller import SnmpPoller
from csi_properties import CSI_Properties

CSI = CSI_Properties('csi_properties.yml')

def debug_logger(func):
    """
    Escalates the log level to debug, can be used as a decorator to the mock methods

    Parameters:
    -----------
    self - current instance of class
    args - nonkeyword list of arguments
    kwargs - keyword list of arguments
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug('**** LOG LEVEL ESCALATED ****')
        ret_val = func(self, *args, **kwargs)
        return ret_val
    return wrapper

class QUINTECH_RF_MATRIX_TEST(unittest.TestCase):

    test_settings = None
    mock_setter = None
    mock_poller = None

    @classmethod
    def mock_restart_snmp_poller(self):
        """
        Mock start the snmp poller
        Raises an exception if communication parameters (device.comms field) is not valid. 

        Parameters:
        -----------
        self - current instance of class
        """
        # update default info before polling
        if SnmpPoller.polling_in_progress is True:
            # bail out with log message
            logging.info('Skipped poll due to polling in progress...')
            return

        mock_config = SNMPConfig(CSI)
        # check if comms is valid
        if mock_config.is_valid():
            ip = mock_config.get_ip()
            readcomm = mock_config.get_read_community()
            version = mock_config.get_snmp_version()
            read_auth_pass = mock_config.get_read_auth_pass()
            read_priv_pass = mock_config.get_read_priv_pass()
            self.mock_poller = SnmpPoller(hostname=ip, community=readcomm, version=version, proxycfg= mock_config,
                                          read_auth_pass=read_auth_pass, read_priv_pass=read_priv_pass)

            # for all instances of perform_poll(), replace with mock method
            with mocker.patch.object(SnmpPoller, 'perform_poll', new=QUINTECH_RF_MATRIX_TEST.mock_poll):
                # for all instances of restart_snmp_poller(), replace with mock method
                with mocker.patch.object(snmp_poller, 'restart_snmp_poller', new=QUINTECH_RF_MATRIX_TEST.mock_restart_snmp_poller):
                    self.mock_poller.run()
        else:
            logging.info("Not kicking off a new SNMP poll, communication parameters are not valid")

    @classmethod
    def mock_poll(self, session):
        logging.info("MOCK PERFORM POLL")

    @classmethod
    def mock_perform_snmp_set(self, incoming_msgdata):
        """
        Mock start the snmp setter 

        Parameters:
        -----------
        self - current instance of class
        incoming_msgdata - command in json/as a dict (ex. {"fault_log": {"clear_all": "CLEAR"}})
        """
        logging.info("MOCK PERFORMING SNMP SET")
        mock_config = SNMPConfig(CSI)
        # check if comms is valid
        if mock_config.is_valid():
            ip = mock_config.get_ip()
            writecomm = mock_config.get_write_community()
            version = mock_config.get_snmp_version()
            write_auth_pass = mock_config.get_write_auth_pass()
            write_priv_pass = mock_config.get_write_priv_pass()
            self.mock_setter = SnmpSetter(hostname=ip, community=writecomm, version=version, msgdata=incoming_msgdata,
                                          proxycfg=mock_config, write_auth_pass=write_auth_pass, write_priv_pass=write_priv_pass)

            # for all instances of session.set(), replace with mock method
            with mocker.patch.object(snmp_setter.Session, 'set', new=QUINTECH_RF_MATRIX_TEST.mock_session_set):
                # for all instances of restart_snmp_poller(), replace with mock method
                with mocker.patch.object(snmp_setter, 'restart_snmp_poller', new=QUINTECH_RF_MATRIX_TEST.mock_restart_snmp_poller):
                    self.mock_setter.run()

            #push updated field to the database
            del incoming_msgdata["request_roles"]
            del incoming_msgdata["result"]
            current_settings = CSI.get_settings(CSI.service_name)
            merge(current_settings, incoming_msgdata)
            
            CSI.update_settings(current_settings)

            logging.info("Successfully kicked off SNMP Set")
        else:
            error_text = "SNMP Set failure: Invalid communication parameters"
            logging.info(f"{error_text}")
            incoming_msgdata['result'] = error_text
            CSI.pub(service=CSI.service_name,
                    msgtype=CSI.STATE_CHANGE_FAILURE,
                    msgdata=incoming_msgdata)

    @classmethod
    def mock_session_set(self, oid, dofval):
        """
        Mock a snmp set. To properly mock a session set, use if statements 
        to check if the oid has a valid dofval. Otherwise, raise an exception.
        All valid values for each oid is listed in the MIBS and in settings. 

        Parameters:
        -----------
        self - current instance of class
        oid - oid that's listed in command 
        dofval - new value of the oid

        Returns:
        --------
        boolean - True (else raise an exception)
        """
        logging.info("mocking session set.....")
        port_cmd = [1,2,3] #valid values for the set
        oid_cmd = oid.split('.') #get index if exists

        # check if oid and dofval is valid to set
        if 'exampleMIB' in oid and dofval in port_cmd and int(oid_cmd[1]) < 9:
            return True
        else:
            raise Exception("Invalid command passed")

if __name__ == '__main__':
    unittest.main()