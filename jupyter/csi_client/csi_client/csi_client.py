# (c) 2022 The MITRE Corporation, All Rights Reserved
"""! @brief CSI_Client class """
##
# @mainpage Common Software Interface PDK
#
# @section description_main Description
# HTTP library intended to be used by CSI clients
#
# Support HTTP GET, POST, and optional async connection to 
# maestro's websocket

# import requests, ast, logging, json
import requests
import logging
# logging.basicConfig(level=logging.INFO)
#logging.warning('csi_client lib logging set to DEBUG')

import json
import websocket
# import http.client as http_client
import threading

from .maestrowebsocket import MaestroWebsocket
# import maestrowebsocket
# websocket_msg_handler = None
# from csi_client_common import websocket_msg_handler

class CSI_Client:
    # static variable to hold remote_event_handler function ptr
#    websocket_msg_handler = None

    def __init__(self, remote_event_handler=None, hostname='localhost', port='8090', streams='/streams', use_https=False):
     
        self.properties = {}
        print("CSI_Client initialization")
        logging.warning('CSI_Client initializing')
        self.properties['endpoint_ipaddr'] = hostname
        self.properties['endpoint_port'] = port
        self.properties['streams'] = streams
        self.properties['verify'] = use_https
        self.socket_msg_handler = remote_event_handler
        if use_https is False:
            scheme = 'http://'
        else:
            scheme = 'https://'
        self.wsurl = scheme + hostname + ':' + port + streams
        self.session_cookie = None
        self.establish_connection()

    def http_get(self, service=None):
        if service == None:
            logging.info('http_get skipped - no target service specified')
            return        

        url = self.get_endpoint_url() + service
        session = self.current_session
        r = session.get(url, headers=self.get_headers(), verify=self.properties['verify'])

    def get_headers(self):
        headers = {'X-API-Key-CSI-Maestro-Administrator': 'Administrator-1',
                   'X-API-Key-CSI-Maestro-Hub': 'Hub-1',
                   'Accept': 'application/json' }
        return headers

    def http_post(self, service=None, suffix=None, msgdata=None):
        if service == None:
            logging.info('http_post skipped - no target service specified')
            return
        if suffix == None:
            suffix = (self.CSI).SETTINGS_SUFFIX
        url = self.get_endpoint_url() + service
        session = self.current_session
        payload = { 'payload': json.dumps(msgdata) }
        logging.info(f'payload is: {payload}, type is {type(payload)}')
        payload = json.dumps(payload)
        logging.info(f'url is {url}')
        logging.info(f'headers are {self.get_headers()}')
        logging.info(f'payload is: {payload}, type is {type(payload)}')
        r = requests.post(url, headers=self.get_headers(), data=payload, verify=self.properties['verify'])
        logging.info(f'Result of post is {r.status_code} | {r.headers} | {r.cookies}')

    def get_endpoint_url(self):
        if self.properties['verify'] is False:
            scheme = 'http://'
        else:
            scheme = 'https://'
        url = scheme + self.properties['endpoint_ipaddr'] + ':' + \
              str(self.properties['endpoint_port']) + (self.CSI).MSGKEY_PREFIX

        return url
 
    def status(self):
        return 'Up and running'

    def display(self):
        for item, val in self.properties.items():
            logging.info(item + ": " + str(val))

    def establish_connection(self):
        # will set self.current_session if successful
        # requests will automatically provide the session cookie for further calls

        ipaddr = self.properties['endpoint_ipaddr']
        port = self.properties['endpoint_port']
        logging.info(f'Establishing link to {ipaddr}:{port}')

        data = { "values": [ "StateChangeEvents", "FileTransferEvents" ] }
        json_data = json.dumps(data)
        headers = {'X-API-Key-CSI-Maestro-Administrator': 'Administrator-1',
                   'X-API-Key-CSI-Maestro-Hub': 'Hub-1'}
        #url = 'http://' + self.properties['endpoint_ipaddr'] + ':' + \
        #      str(self.properties['endpoint_port']) + '/streams'

        url = self.wsurl

        self.current_session = requests.Session()    # remember the session cookie

        session = self.current_session
        logging.info(f'url is {url}, headers are {headers}')
        logging.info(f'data is {json_data}')
        r = session.post(url, headers=headers, data=json_data, verify=self.properties['verify'])

        logging.info(f'Result of post is {r.status_code} | {r.headers} | {r.cookies}')
        self.cookies = r.cookies

        logging.info(f'Now creating websocket with cookies')

        # websocket client stuff
        self.mws = MaestroWebsocket(self.socket_msg_handler,
                                    self.properties['endpoint_ipaddr'], 
                                    self.properties['endpoint_port'], 
                                    cookie=self.cookies)
        logging.info(f'Created mws object')
        self.mws.start()
