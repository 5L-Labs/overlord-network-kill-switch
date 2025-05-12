#!/usr/bin/env python3
# import pihole as ph

import requests
import hashlib
from urllib import parse as urlparse
import urllib3
import re
import sys
import os
import json
import logging
import configparser
from pprint import pprint, pformat
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, BaseConfig
from typing import Optional, List

# Disable warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

### For Data Sharing of Login Sessions
from multiprocessing import Manager

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))

# pihole.init()
from pihole import pihole_core  # noqa: E402
from ubiquity import ubiquity  # noqa: E402

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] - [%(name)s] - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger()
logger.debug("test")


description = """
API to manage pihole < 5 API devices and ubiquity API based devices. 🚀

## Key Ideas

* Disable DNS for certain domains.
* Disable MAC Addresses at the Ubiquity Gateway
* Disable/Enable traffic rules on the fly (which are more complex than blocking one device at time)

## Caveat Emptor

Will not work if the endpoint does not talk to the Ubiquity Gateway or the PiHole DNS server is version 6 (for now).
"""

app = FastAPI(
    title="Overlord API",
    version="v2.0",
    openapi_version="3.0.2",
    description=description,
    summary="Ubiquity Gateway and PiHole DNS server management",
    terms_of_service="http://5l-labs.com/",
    contact={
        "name": "5L-Labs",
        "url": "https://github.com/5L-Labs/dns_admin",
        "email": "inquiry@5l-labs.com",
    },
    license_info={
        "name": "Apache 2.0",
        "identifier": "Apache",
    },
)


def init_config(app, config_location: str = "../etc/config.ini"):
    global logger
    app_config = dict()
    config = configparser.ConfigParser()
    try:
        config.read(config_location)
        # Load DNS blocks into
        logger.info(pformat(config.sections()))
        app_config["domains"] = dict()
        for provider in config.options("domains"):
            app_config["domains"][provider] = config.get("domains", provider).splitlines()
            print(provider)
        app_config["remote_pi_list"] = config.get(
            "general",
            "remote_pi_list",
            fallback=os.environ.get("REMOTE_PI_LIST"),
        ).split(sep=" ")
        app_config["remote_pi_password"] = config.get(
            "general",
            "remote_pi_password",
            fallback=os.environ.get("REMOTE_PI_PASSWORD"),
        )
        app_config["remote_pi_token"] = config.get(
            "general",
            "remote_pi_token",
            fallback=os.environ.get("REMOTE_PI_TOKEN"),
        )
        for i in ["DEVICE", "USERNAME", "PASSWORD"]:
            key = "ubiquiti_%s" % (i.lower())
            app_config[key] = config.get(
                "ubiquiti",
                f"remote_{key}",
                fallback=os.environ.get(f"REMOTE_UBIQUITI_{i}"),
            )
        app_config["ubiquiti_targets"] = dict()
        for provider in config.options("ubiquiti_targets"):
            app_config["ubiquiti_targets"][provider] = config.get("ubiquiti_targets", provider).splitlines()
            print(provider)

        app_config["ubiquiti_rules"] = dict()
        for provider in config.options("ubiquiti_rules"):
            for x in config.get("ubiquiti_rules", provider).splitlines():
                app_config["ubiquiti_rules"][x] = {}
                logger.debug(f"Enabled{app_config['ubiquiti_rules'][x]}")

        app_config["logger"] = logger
    except configparser.Error as a:
        logger.error("Couldn't read configs from: %s %s" % (config_location, a))
    logger.info(app_config)
    return app_config

    # query status of each one and make the call
    # check ipv6 prefix - alert if diff?


config_file = os.path.join(os.path.dirname(__file__), "../etc/", "config.ini")

app_config = init_config(app, config_file)

# ~njl/dev/src/overlord/dns_admin/venv/bin/python3

# FIXME: Move to GUNICORN Logging object

sharedMemManager = Manager()
app_config["shmem_store"] = sharedMemManager.dict()
app_config["shmem_mgr"] = sharedMemManager

pihole_core.init(app_config)
ubiquity.init(app_config)

logger.info("Adding Endpoints...")

app.include_router(pihole_core.main_router)
app.include_router(pihole_core.alldns_router)
app.include_router(ubiquity.router)


logger.info("starting the app...")


@app.get("/")
async def root():
    return {"status": "alive"}
