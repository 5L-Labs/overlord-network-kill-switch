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
from contextlib import asynccontextmanager

import aiomqtt  # noqa: F401

### For Data Sharing of Login Sessions
from multiprocessing import Manager

# Disable warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))

# pihole.init()
from pihole import pihole, pihole_router  # noqa: E402
from ubiquity import ubiquity  # noqa: E402

default_log_level = logging.INFO

logger = logging.getLogger()
logging.basicConfig(
    level=default_log_level,
    format="[%(asctime)s] - [%(name)s] - [%(funcName)s:%(lineno)d] - [%(levelname)s] - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)

app_config: dict | None = None

description = """
FastAPI to manage multiple Pi-holes DNS filtering and Ubiquiti network access controls. 🚀

## Key Features

### Pi-hole Management
*   **Domain-level Blocking/Allowing**: Dynamically enable or disable specific domain groups (e.g., regex blacklists or whitelists) on configured Pi-hole instances.
*   **Global DNS Control**: Enable or disable DNS blocking entirely across all connected Pi-hole devices, with an optional timer for temporary disabling.

### Ubiquiti Network Management
*   **Client Device Control**: Block or unblock individual client devices by their MAC address on the Ubiquiti Gateway.
*   **Firewall Rule Management**: Enable or disable custom firewall rules on the Ubiquiti Gateway to control network traffic.

## Compatibility Note

This API is designed for compatibility with Pi-hole v6 (utilizing `pihole6api`) and Ubiquiti Network devices (such as UniFi Dream Machine) through their respective APIs.
"""


def init_config(app, config_location: str = "../etc/config.ini"):
    global logger
    global app_config
    app_config = dict()
    app_config["default_log_level"] = logging.DEBUG
    config = configparser.ConfigParser()
    try:
        config.read(config_location)
        # Load DNS blocks into
        logger.info(pformat(config.sections()))
        for key in [
            "ubiquiti_control_enabled",
            "pihole_control_enabled",
            "mqtt_announce_enabled",
        ]:
            temp = config.get("general", key, fallback=False)
            if temp.lower() in ["yes", "true", "1"]:
                app_config[key] = True
            elif temp.lower() in ["no", "false", "0"]:
                app_config[key] = False
            else:
                logger.warning(
                    f"Unknown boolean value for {key}: {temp}, defaulting to False"
                )
                app_config[key] = False
        if app_config["pihole_control_enabled"]:
            for area in ["allow_domains", "block_domains"]:
                app_config[area] = dict()
                for provider in config.options(area):
                    app_config[area][provider] = config.get(area, provider).splitlines()
            #            print(provider)
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
            # app_config["remote_pi_token"] = config.get(
            #     "general",
            #     "remote_pi_token",
            #     fallback=os.environ.get("REMOTE_PI_TOKEN"),
            # )
        if app_config["ubiquiti_control_enabled"]:
            for i in ["DEVICE", "API_KEY"]:
                key = "ubiquiti_%s" % (i.lower())
                app_config[key] = config.get(
                    "ubiquiti",
                    f"remote_{key}",
                    fallback=os.environ.get(f"REMOTE_UBIQUITI_{i}"),
                )
            app_config["ubiquiti_targets"] = dict()
            for provider in config.options("ubiquiti_targets"):
                app_config["ubiquiti_targets"][provider] = config.get(
                    "ubiquiti_targets", provider
                ).splitlines()
                print(provider)

            app_config["ubiquiti_rules"] = dict()
            for provider in config.options("ubiquiti_rules"):
                for x in config.get("ubiquiti_rules", provider).splitlines():
                    app_config["ubiquiti_rules"][x] = {}
                    logger.debug(f"Enabled{app_config['ubiquiti_rules'][x]} for {x}")
        if app_config["mqtt_announce_enabled"] and "mqtt" in config.sections():
            app_config["mqtt"] = dict()
            app_config["mqtt"]["broker"] = config.get(
                "mqtt",
                "broker",
                fallback=os.environ.get("MQTT_BROKER", "localhost"),
            )
            app_config["mqtt"]["port"] = int(
                config.get(
                    "mqtt",
                    "port",
                    fallback=os.environ.get("MQTT_PORT", "1883"),
                )
            )
            app_config["mqtt"].setdefault("lwt_topics", [])
            for topic in config.get("mqtt", "lwt_topics").splitlines():
                if topic:
                    app_config["mqtt"]["lwt_topics"].append(topic)
                    logger.debug(
                        f"Enabled{app_config['mqtt']['lwt_topics']} for {topic}"
                    )
            logger.debug(f"MQTT Config: {pformat(app_config['mqtt'])}")
        app_config["logger"] = logger
    except configparser.Error as a:
        logger.error("Couldn't read configs from: %s %s" % (config_location, a))
    # logger.debug(app_config)
    return app_config

    # query status of each one and make the call
    # check ipv6 prefix - alert if diff?


async def publish_to_mqtt(mqtt_config: dict, status: str):
    broker = mqtt_config.get("broker", "localhost")
    lwt_topics = mqtt_config.get("lwt_topics", [])
    port = mqtt_config.get("port", 1883)

    try:
        async with aiomqtt.Client(broker, port) as client:
            for topic in lwt_topics:
                logger.debug(f"Publishing LWT of '{status}' to '{topic}'...")
                await client.publish(topic, status, retain=True)
                logger.info(f"Published LWT of '{status}' to '{topic}'...")
    except aiomqtt.MqttError as e:
        logger.warning(f"MQTT publish failed (non-fatal): {e} for {lwt_topics}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_file = os.path.join(os.path.dirname(__file__), "../etc/", "config.ini")

    app_config = init_config(app, config_file)

    # ~njl/dev/src/overlord/dns_admin/venv/bin/python3

    # FIXME: Move to GUNICORN Logging object

    #    sharedMemManager = Manager()
    #    app_config["shmem_store"] = sharedMemManager.dict()
    #    app_config["shmem_mgr"] = sharedMemManager

    # ENHANCEME: Only start if using
    if app_config["pihole_control_enabled"]:
        pihole_router.init(app_config)
        app.include_router(pihole_router.main_router)
        app.include_router(pihole_router.alldns_router)
    if app_config["ubiquiti_control_enabled"]:
        ubiquity.init(app_config)
        app.include_router(ubiquity.router)
    if app_config["mqtt_announce_enabled"]:
        await publish_to_mqtt(app_config["mqtt"], "true")
    logger.info("Adding Endpoints...")
    yield
    # Clean up the ML models and release the resources
    if app_config["pihole_control_enabled"]:
        pihole_router.pihole.shutdown()
    if app_config["ubiquiti_control_enabled"]:
        ubiquity.udm.shutdown()
    if app_config["mqtt_announce_enabled"]:
        await publish_to_mqtt(app_config["mqtt"], "false")


app = FastAPI(
    title="Overlord Network Kill Switch API",
    version="v2.5",
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
    lifespan=lifespan,
)


logger.info("starting the app...")


@app.get("/")
async def root():
    return {"status": "alive"}
