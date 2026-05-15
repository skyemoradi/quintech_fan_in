# CSI PDK Common Libraries (commonlib)

## Contents

csi_properties: Python-based proxy library which provides message-passing and persistence APIs.
src/pdkapi-edge: Soon to be deprecated old version of csi_properties

### Building csi_properties

'make build' or 'make clean build' builds a docker container to provide a consistent build environent.  Results of the build can be found in the dist directory:

```bash
commonlib/csi_properties$ ls dist
csi_properties-0.1.1-py3-none-any.whl  csi_properties-0.1.1.tar.gz
```

### src/pdkapi Documentation (deprecated)

The Common Library (aka commonlib) includes files that are common across
proxies, including the CSI PDK

## Changes needed to proxies in order to move to commonlib.

## Changes added in pdkapi-4.3.0 (the initial version)

Now uses pub/sub rather than publish/subscribe
Check your imports:
from openapi_server.controllers.common import initialize_database
from openapi_server.pdkapi.csi_properties import CSI_Properties

## Changes added in pkdapi-4.4.0

Messages now officially have a 'msgdata' portion
The signature for pub() moves from 'payload' to 'msgdata'

A function which is a 'sub' callback has 3 arguments: channel, pattern, payload

payload looked like the settings:
{ "common": {...}, "simplesdr":  {...} } 

Now a message has better defined fields, in particular "payload" now 
looks like this: 

    { "src": message-source, "dest": message-dest, 
      "msgtype": message-type, 
      "msgdata": "the changed settings"
    }

channel and pattern are unchanged, channel is the actual channel that the message
was published to, and pattern is the channel-name pattern that was subscribed to.

Example message callback:

def state_change_handler(channel, pattern, payload):

channel would be /service/simplesdr/state-change-request
pattern in this case would be the same as the channel (no wildcards involved)
payload would be:
    { "src": "maestro", "dest": "simplesdr", 
      "msgtype": "/state-change-request", 
      "msgdata": { "receive_frequency_mhz": 900 }
    }

#
