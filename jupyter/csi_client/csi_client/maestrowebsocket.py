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
import json
import websocket
# import http.client as http_client
import threading
# logging.basicConfig(level=logging.INFO)
# logging.warning('maestrowebsocket lib logging set to DEBUG')


class MaestroWebsocket:

    def __init__(self, socket_msg_handler, ipaddr, port, cookie):
        logging.info("Creating MaestroWebsocket object")
        # self.url = 'ws://192.168.247.133:8090/ws'
        self.url = 'ws://' + ipaddr + ':' + str(port) + '/ws'
        self.conn = None
        self.cookie = cookie
        # self.loop = asyncio.get_event_loop()
        self.headers = self.calc_headers()
        self.ws = websocket.WebSocketApp(self.url, on_open=self.on_open, on_message=self.on_message,
                                         on_close=self.on_close, header=self.headers)
        self.socket_msg_handler = socket_msg_handler


    def start(self):
        t = threading.Thread(target=lambda: (self.ws).run_forever())
        t.daemon = True
        t.start()


    def calc_headers(self):
        # headers = {'X-API-Key-CSI-Maestro-Administrator': 'Administrator-1',
        #            'X-API-Key-CSI-Maestro-Hub': 'Hub-1',
        #            'Accept': 'application/json' }
        headers={}
        cookie_dict = self.cookie.get_dict()
        logging.info(f'cookie_dict is {cookie_dict}')
        cookie_name = 'csi-maestro-websocket-session-id'
        cookie_str = cookie_name + '=' + cookie_dict[cookie_name]
        cookie_str += '; Path=/; SameSite=lax'

        cookie_header = {'Cookie': cookie_str}
        headers.update(cookie_header)     
        return headers


    def on_open(self, ws):
        logging.info("Connection to Maestro async channel established")


    def on_message(self, ws, message):
        message = json.loads(message)
        logging.info(message)
        self.socket_msg_handler(message)


    def on_close(self, ws, status_code, close_msg):
        logging.info(f"closed connection due to code {status_code}: {close_msg}")
