import configparser
import hashlib
import json
import logging
import multiprocessing
import os
import re
import sys
from collections import defaultdict
from pprint import pformat, pprint
from typing import List, Optional
from urllib import parse as urlparse

import requests
import urllib3
from urllib3.util.retry import Retry
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, BaseConfig, ConfigDict
from datetime import datetime
from pprint import pprint, pformat

# import ubiquity
import http.client as http_client

# import ubiquity

http_client.HTTPConnection.debuglevel = 0

## required ? for shared Mem Store
from multiprocessing.managers import SyncManager, DictProxy

# You must initialize logging, otherwise you'll not see debug output.

# logger = logging.getLogger()
requests_log = logging.getLogger("requests.packages.urllib3")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

# https://192.168.100.1/--data-raw '{"username":"overlord","password":"0verlorD","token":"","rememberMe":false}' -X POST -H 'Referer: https://192.168.100.1/login?redirect=%2F' -H 'Content-Type: application/json'
#
logger = logging.getLogger(__name__)


class InboundPayload(BaseModel):
    state: str


class UbiquitiOverlord(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    app_config: dict
    username: str
    password: str
    controller: str
    macs: dict
    auth_token: str | None
    csrf_token: str | None
    base_api_url: str
    base_api_v2_url: str
    mac_block_url: str
    client_list_url: str
    firewall_rule_list_url: str
    firewall_rule_state_change_url: str
    firewall_rules: dict
    state: str = "offline"
    logged_in: bool | None
    login_expiry: int | None
    rule_cache_ttl: int
    session: requests.Session | None
    shmem_store: DictProxy | None
    shmem_mgr: SyncManager | None
    last_rules_check: datetime | None = None

    def __init__(self, app_config: dict) -> None:
        super().__init__(
            app_config=app_config,
            username=app_config["ubiquiti_username"],
            macs=app_config["ubiquiti_targets"],
            controller=app_config["ubiquiti_device"],
            password=app_config["ubiquiti_password"],
            session=None,
            base_api_url=f"https://{app_config['ubiquiti_device']}/proxy/network/api",
            base_api_v2_url=f"https://{app_config['ubiquiti_device']}/proxy/network/v2/api",
            mac_block_url="",
            client_list_url="",
            firewall_rule_list_url="",
            firewall_rule_state_change_url="",
            firewall_rules=app_config["ubiquiti_rules"],
            auth_token=None,
            csrf_token=None,
            login_expiry=0,
            rule_cache_ttl=60,
            logged_in=False,
            shmem_store=app_config["shmem_store"],
            shmem_mgr=app_config["shmem_mgr"],
        )
        self.mac_block_url = f"{self.base_api_url}/s/default/cmd/stamgr"
        self.client_list_url = f"{self.base_api_v2_url}/site/default/clients/active?includeTrafficUsage=false"
        self.firewall_rule_list_url = f"https://{app_config['ubiquiti_device']}/proxy/network/v2/api/site/default/firewall-rules/combined-traffic-firewall-rules?originType=traffic_rule"
        self.firewall_rule_state_change_url = (
            f"https://{app_config['ubiquiti_device']}/proxy/network/v2/api/site/default/trafficrules/"
        )
        logger.info("Initialized ubiquity module")

    def parse_firewall_rules(self):
        """
        Parses the firewall rules from the Ubiquiti controller - not sure how often ID changes.

        This method performs the following tasks:
        1. Sends a GET request to the firewall rule list URL.
        2. Checks the response status code.
        3. Parses the JSON response.
        4. Iterates over the rules.
        5. Checks if the rule name exists in the firewall rules dictionary.
        6. Updates the firewall rules dictionary with the origin ID.
        """
        if not self.logged_in:
            raise HTTPException(status_code=401, detail="Not logged in")

        response = self.session.get(self.firewall_rule_list_url, verify=True)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        rules = response.json()
        for rule in rules:
            if rule["name"] in self.firewall_rules:
                self.firewall_rules[rule["name"]] = rule
                ## We apparently need to package the whole json
                logger.info(f"Adding {rule['name']} with origin ID {rule['origin_id']} to state {rule['enabled']}")

        # Update the last checked timestamp
        self.last_rules_check = datetime.now()
        logger.debug(f"Updated firewall rules at {self.last_rules_check}")

    def first_connect(self):
        """
        Establishes initial connection to the Ubiquiti controller.

        This method performs the following tasks:
        1. Creates a new session.
        2. Sends a POST request to the login endpoint.
        3. Extracts and stores the CSRF token and authentication token from the response.
        4. Updates the app_config with the new session and tokens.
        5. Generates a second request to get all the firewall rules

        Raises:
            HTTPException: If the login request fails (status code != 200).

        Note:
            This method should be called before making any other API requests.
        """

        if self.logged_in:
            logger.debug("Already logged in. Skipping first_connect() method.")
            return
        if self.login_expiry > 0 and datetime.now() < self.login_expiry:
            logger.debug("Login has not expired. Skipping first_connect() method.")
            return
        if self.shmem_store.get("ubiquiti_session"):
            logger.debug("Not logged in, but found session in shared memory. Using that to connect.")
            self.session = self.shmem_store["ubiquiti_session"]
            self.logged_in = True
            return
        pArgs = {
            "username": self.username,
            "password": self.password,
            "rememberMe": False,
            "token": "",
        }
        url = "/api/auth/login"
        self.session = requests.session()
        furl = "https://" + str(self.controller) + url
        # pprint(furl)
        logger.debug(f"{furl} with {pArgs}")
        resp = self.session.post(furl, json=pArgs, verify=True)
        if not hasattr(resp, "cookies"):
            logger.error("No cookies found in response from controller")
            return
        self.auth_token = resp.cookies["TOKEN"] if "TOKEN" in resp.cookies else None
        self.login_expiry = None
        for cookie in resp.cookies:
            if cookie.name == "TOKEN":
                self.login_expiry = cookie.expires

        self.csrf_token = resp.headers["X-CSRF-Token"] if "X-CSRF-Token" in resp.headers else None
        if resp.status_code != 200:
            logger.error("Failed to login to Ubiquiti controller with status code %s", resp.status_code)
            self.logged_in = False
            return
        self.session.headers.update({"X-CSRF-Token": self.csrf_token})
        self.logged_in = True
        self.shmem_store["ubiquity_session"] = self.session
        self.parse_firewall_rules()

    #        if self.login_expiry:
    #            self.login_expiry = datetime.fromtimestamp(self.login_expiry)
    #            print(self.login_expiry)
    #        print(f'Which one is it? {datetime.now()} {datetime.utcnow()} {(self.login_expiry - datetime.now())} {(self.login_expiry - datetime.utcnow())}')
    #        pprint(self.auth_token)
    #        pprint(self.csrf_token)

    def cmd(self, url, data, qs=None, method="post"):
        self.check_logged_in()
        furl = url
        if qs is not None:
            qs = urlparse.urlencode(qs)
            furl = url + "?" + qs
        logger.debug(f"{furl} with {data}")
        if method == "get":
            return self.session.get(furl, timeout=(3.05, 5))
        elif method == "put":
            return self.session.put(furl, json=data, timeout=(3.05, 5))
        elif method == "delete":
            return self.session.delete(furl, json=data, timeout=(3.05, 5))
        return self.session.post(furl, json=data, timeout=(3.05, 5))

    def check_logged_in(self):
        """
        Checks if our session has expired
        """
        if not self.logged_in:
            logger.debug("Not logged in, logging in...")
            self.first_connect()
            return
        now = datetime.now()
        expiry_time = datetime.fromtimestamp(self.login_expiry) if self.login_expiry else None

        if expiry_time is None or now > expiry_time:
            logger.debug("Login expired, refreshing...")
            self.first_connect()
        else:
            logger.debug(f"Still logged in. Current time: {now}, valid until: {expiry_time}")

    def check_rules_freshness(self):
        """
        Checks if the firewall rules need to be refreshed.
        Rules are considered stale if they haven't been checked in the last 60 seconds.
        """
        now = datetime.now()
        if self.last_rules_check is None or (now - self.last_rules_check).total_seconds() > self.rule_cache_ttl:
            logger.debug("Firewall rules are stale. Refreshing...")
            self.parse_firewall_rules()
        else:
            logger.debug(f"Firewall rules still fresh. Last checked at {self.last_rules_check}")

    def status_rule(self, rule: str | None):
        """
        Changes the state of a firewall rule

        Args:
            target: The firewall rule ID

        Returns:
            dict: The status of the target rule
        """
        self.check_logged_in()
        # Check if rules need refreshing
        self.check_rules_freshness()

        temp = self.firewall_rules[rule]["enabled"]
        logger.debug(f"getting  status for {rule}  as {temp}")
        return {"status": temp}

    def status_device(self, target: str | None):
        """
        Changes the state of a target device.

        Args:
            target: The MAC address of the target device.

        Returns:
            dict: The status of the target device.

        Raises:
            HTTPException: If the target device is not found.
        """
        self.check_logged_in()
        logger.debug(f"getting  status for {target}  as {self.state}")
        return {"status": self.state}

    def change_rule(self, requested_status: str, rule: str | None):
        if requested_status not in ["enabled", "disabled"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        if rule is None or rule not in self.firewall_rules:
            raise HTTPException(status_code=400, detail="Invalid rule")
        trans = {"enabled": True, "disabled": False}
        self.check_logged_in()

        # Check if rules need refreshing
        self.check_rules_freshness()

        logger.debug(f"Changing status for {rule} to {requested_status} from {self.firewall_rules[rule]['enabled']}")
        id = self.firewall_rules[rule]["origin_id"]
        url = f"{self.firewall_rule_state_change_url}/{id}"
        logger.debug(f"{url} vs {self.firewall_rule_state_change_url}")
        logger.info(f"Changing status for {rule} to {requested_status}")
        request_object = self.firewall_rules[rule].copy()
        request_object["enabled"] = trans[requested_status]
        request_object["action"] = request_object["traffic_rule_action"]
        request_object["description"] = request_object["name"]
        ### FIXME: Need to understand when these are set
        for i in ["app_category_ids", "app_ids", "domains", "ip_addresses", "ip_ranges", "network_ids", "regions"]:
            request_object[i] = [] if i not in request_object or request_object[i] is None else request_object[i]
        request_object["_id"] = request_object["origin_id"]
        payload = request_object
        # action\
        resp_raw = self.cmd(url=url, data=payload, method="put", qs=None)
        # resp = resp_raw.json()
        # pprint(resp_raw)
        if resp_raw.status_code != 200:
            logger.error("Failed to update {rule } on Ubiquiti controller with status code %s", resp_raw.status_code)
            self.logged_in = False
            return {"status": "unknown"}
        self.parse_firewall_rules()
        state = self.firewall_rules[rule]["enabled"]
        logger.info(f"Changed status for {rule} to {state}")
        return {"status": state}

    def change_device(self, requested_status: str, target: str | None):
        """
        Changes the status of a target device.

        Args:
            target: The group of address of the target device.

        Returns:
            dict: The status of the target device.

        Raises:
            HTTPException: If the target device is not found.
        """
        self.check_logged_in()

        ### FIXME: What if someone changes things outside the system?
        logger.debug(f"Changing status for {target} to {requested_status} from {self.state}")
        if target not in self.macs:
            raise HTTPException(status_code=404, detail="Device not found")

        target_state = None
        url = self.mac_block_url
        #        logging.debug(f'{url} vs {self.mac_block_url}')
        for mac in self.macs[target]:
            logger.info(f"Changing status for {target}/{mac} to {requested_status}")
            if requested_status == "offline":
                cmd = "block-sta"
                target_state = "offline"
            elif requested_status == "online":
                target_state = "online"
                cmd = "unblock-sta"
            payload = {"mac": mac.lower(), "cmd": cmd}
            resp_raw = self.cmd(url=url, data=payload, method="post", qs=None)
            # resp = resp_raw.json()
            # pprint(resp_raw)
            if resp_raw.status_code != 200:
                logger.error(
                    "Failed to update {target } on Ubiquiti controller with status code %s", resp_raw.status_code
                )
                self.logged_in = False
                return {"status": "unknown"}
            resp = resp_raw.json()
            # pprint(resp.items())
            if "meta" not in resp or resp["meta"]["rc"] != "ok":
                logger.error(f"Failed to change status for {target}/{mac} to {requested_status}")
                return {"status": self.state}
        self.state = target_state
        logger.info(f"Changed status for {target} to {self.state}")
        return {"status": self.state}


udm = None


def init(app_config: dict):
    global udm
    udm = UbiquitiOverlord(app_config=app_config)


router = APIRouter(
    prefix="/ubiquiti",
    tags=["ubiquiti"],
    #    dependencies=[Depends(get_token_header)],
    responses={404: {"description": "Not found"}},
)


@router.get("/status_rule/{target}")
async def get_status_rule(target: str):
    return udm.status_rule(target)


@router.get("/status_device/{target}")
async def get_status_target(target: str):
    return udm.status_device(target)


@router.get("/enable_device/{target}")
async def set_enable_target(target: str | None):
    return udm.change_device("online", target)


@router.get("/disable_device/{target}")
async def set_disable_target(target: str | None):
    return udm.change_device("offline", target)


@router.get("/enable_rule/{target}")
async def set_enable_rule(target: str | None):
    return udm.change_rule("enabled", target)


@router.get("/disable_rule/{target}")
async def set_disable_rule(target: str | None):
    return udm.change_rule("disabled", target)


@router.get("/refresh")
async def refresh_rules():
    """Force refresh the firewall rules"""
    udm.parse_firewall_rules()
    return {"status": "refreshed", "timestamp": udm.last_rules_check}
