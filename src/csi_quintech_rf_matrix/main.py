from fastapi import FastAPI
from quintech_rf_matrix_settings import QuintechRFMatrixSettings
from proxy_backend import proxy_backend_start
from csi_properties import CSI_Properties

import logging

CSI = CSI_Properties("csi_properties.yml")

mock = CSI.get_property_by_name("debug_mode")
logging.info(f"DEBUG MODE: {mock}")

logging.info("Welcome to the Quintech RF Matrix CSI Proxy...")
logging.info("main.py starting")

proxy_backend_start()

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/service/quintech_rf_matrix/")
async def get_settings() -> QuintechRFMatrixSettings:
    logging.info(f'csi service name is {CSI.service_name}')
    settings = CSI.get_settings(CSI.service_name)
    logging.info(f"settings is: {settings}")
    return settings

@app.get("/service/quintech_rf_matrix/discover")
async def discover_msg():
    discover_settings = QuintechRFMatrixSettings().schema()
    CSI.update_discovery_and_notify(discover_settings)
    return discover_settings

@app.get("/service/quintech_rf_matrix/landing_page")
async def landing_page():
    settings = {"landing_page": QuintechRFMatrixSettings().landing_page}
    return settings

#In Progress: Standalone Proxy
#This code technically allows direct REST communications with the proxy,
#but it is missing logic such as checking the keys included in that message.
""" @app.get("/service/make_model/", response_model=MakeMODELSettings)
async def get_settings() -> MakeMODELSettings:
    # return CSI.get_settings()
    logging.info(f'csi service name is {CSI.service_name}')
    settings = CSI.get_settings(CSI.service_name)
#    return json.dumps(settings['parameters'])
    logging.info(f"settings is: {settings}")
    return settings

@app.get("/service/make_model/discover")
async def discover_msg():
    settings = MakeMODELSettings().schema()
    CSI.update_discovery_and_notify(settings)
    return settings

@app.get("/service/make_model/landing_page")
async def landing_page():
    settings = {"landing_page": MakeMODELSettings().landing_page}
    return settings
 """