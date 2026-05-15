# from ipywidgets import widgets
# from ipywidgets import Layout

# from IPython.display import display
import requests, json, time, logging
logging.basicConfig(level=logging.DEBUG)
logging.info(f'tester.py: Starting logger')

from csi_client import CSI_Client


# Location of maestro

maestro_ip = '10.0.0.64'
maestro_port = '8090'
maestro_url = 'http://' + maestro_ip + ':' + maestro_port


SERVICE_URL = maestro_url + '/service/csi_evertz_xrf1rtr'

logging.warning(f"Service URL is {SERVICE_URL}")

maestro_keys = {'X-API-Key-CSI-Maestro-SystemOperator': 'SystemOperator-1',
                'X-API-Key-CSI-Maestro-Hub': 'Hub-1'}

get_headers = { 'accept':'application/json',
                'Content-Type': 'application/json', 
                **maestro_keys }

def remote_event_handler(payload):
    # This function handles all remote messages coming over the websocket
    mws_banner = '[ Received message on websocket ]'
    logging.warning(mws_banner)
    logging.warning(payload)

# Create a CSI_Client, provide a function to handle websocket messages
try:
    logging.warning('Attempting connection to CSI_Client...')
    rmtconn = CSI_Client(remote_event_handler, maestro_ip, maestro_port)
    status = rmtconn.status()
    logging.warning(f'Maestro connection status is {status}')
except Exception as e:
    logging.error(f'Failed to connect to maestro: {e}')
    logging.warning('Could not connect to maestro')


# # Retrieve all DoF data from database
# response = requests.get(SERVICE_URL, headers=get_headers)
# print('Maestro response:')

# print(json.dumps(response.json(),indent=4))

# response_json = response.json()

payload_string = {"proxy_configuration": {"comms": {"ip": "192.168.10.234", "read_community": "public", "write_community": "private", "snmp_version": 1}}}

#_payload = json.dumps(json.loads(payload_string))
# _payload = payload_string
# print("Issuing HTTP POST with the following payload:")
# print(_payload)

# response = requests.post(SERVICE_URL, json={"payload": _payload}, headers=maestro_keys)
# print(f"response: {response}")

_payload = {"parameters": {"input_ports": {"2": {"description": "INPUT PORT 2"}}}}
response = requests.post(SERVICE_URL, json={"payload": _payload}, headers=maestro_keys)
print(f"response: {response}")

print("Sleeping for 30 seconds")
time.sleep(60)