#!/usr/bin/env python3
"""
State Drift Checker for Overlord Network Kill Switch

Compares the current MQTT state (what HomeKit sees) against the actual
state from the Pi-hole/Ubiquiti APIs to detect drift.

Usage:
    python scripts/state_drift_check.py [--config path/to/config.ini]

Environment variables:
    OVERLORD_URL - Base URL for Overlord API (default: http://localhost:19000)
    MQTT_BROKER - MQTT broker address (default: localhost)
    MQTT_PORT - MQTT broker port (default: 1883)
"""

import argparse
import asyncio
import configparser
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

import httpx
import paho.mqtt.client as mqtt


@dataclass
class StateComparison:
    name: str
    mqtt_topic: str
    api_endpoint: str
    mqtt_value: Optional[str] = None
    api_value: Optional[str] = None
    mqtt_error: Optional[str] = None
    api_error: Optional[str] = None

    @property
    def matches(self) -> bool:
        if self.mqtt_error or self.api_error:
            return False
        return self.normalize(self.mqtt_value) == self.normalize(self.api_value)

    @staticmethod
    def normalize(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        v = str(value).lower().strip()
        if v in ("true", "on", "1", "enabled"):
            return "true"
        if v in ("false", "off", "0", "disabled"):
            return "false"
        return v

    def status_icon(self) -> str:
        if self.mqtt_error or self.api_error:
            return "❌"
        return "✓" if self.matches else "⚠️"


class StateDriftChecker:
    def __init__(
        self,
        overlord_url: str,
        mqtt_broker: str,
        mqtt_port: int,
        config_path: Optional[str] = None,
    ):
        self.overlord_url = overlord_url.rstrip("/")
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.config_path = config_path
        self.checks: list[StateComparison] = []

    def load_config(self) -> configparser.ConfigParser:
        config = configparser.ConfigParser()
        if self.config_path and os.path.exists(self.config_path):
            config.read(self.config_path)
        return config

    def build_checks(self, config: configparser.ConfigParser) -> list[StateComparison]:
        checks = []

        # Global DNS status
        checks.append(
            StateComparison(
                name="DNS Master",
                mqtt_topic="stat/dns_controller/master/status",
                api_endpoint="/alldns/",
            )
        )

        # Pi-hole domain blocks
        if config.has_section("block_domains"):
            for domain_block in config.options("block_domains"):
                checks.append(
                    StateComparison(
                        name=f"Block: {domain_block}",
                        mqtt_topic=f"stat/dns_controller/media/{domain_block}/status",
                        api_endpoint=f"/pihole/status/{domain_block}",
                    )
                )

        if config.has_section("allow_domains"):
            for domain_block in config.options("allow_domains"):
                checks.append(
                    StateComparison(
                        name=f"Allow: {domain_block}",
                        mqtt_topic=f"stat/dns_controller/media/{domain_block}/status",
                        api_endpoint=f"/pihole/status/{domain_block}",
                    )
                )

        # Ubiquiti firewall rules
        if config.has_section("ubiquiti_rules"):
            rules_str = config.get("ubiquiti_rules", "rules", fallback="")
            for rule in rules_str.splitlines():
                rule = rule.strip()
                if rule:
                    checks.append(
                        StateComparison(
                            name=f"Rule: {rule}",
                            mqtt_topic=f"stat/router_controller/status/{rule}",
                            api_endpoint=f"/ubiquiti/status_rule/{rule}",
                        )
                    )

        return checks

    async def fetch_api_status(self, check: StateComparison) -> None:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.overlord_url}{check.api_endpoint}")
                response.raise_for_status()
                data = response.json()
                check.api_value = str(data.get("status", "unknown"))
        except httpx.HTTPStatusError as e:
            check.api_error = f"HTTP {e.response.status_code}"
        except httpx.RequestError as e:
            check.api_error = f"Request failed: {e}"
        except Exception as e:
            check.api_error = str(e)

    def fetch_mqtt_values(self, topics: list[str], timeout: float = 5.0) -> dict[str, str]:
        values: dict[str, str] = {}
        received = set()
        disconnected = False

        def on_connect(client, userdata, flags, reason_code, properties=None):
            if reason_code == 0:
                for topic in topics:
                    client.subscribe(topic)
            else:
                print(f"MQTT connection failed with code {reason_code}")

        def on_message(client, userdata, msg):
            nonlocal disconnected
            topic = msg.topic
            payload = msg.payload.decode("utf-8", errors="replace")
            values[topic] = payload
            received.add(topic)
            if received == set(topics) and not disconnected:
                disconnected = True
                client.disconnect()

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect
        client.on_message = on_message

        try:
            client.connect(self.mqtt_broker, self.mqtt_port, 60)
            client.loop_start()

            start = time.time()
            while time.time() - start < timeout:
                if received == set(topics):
                    break
                time.sleep(0.1)

            client.loop_stop()
            if not disconnected:
                client.disconnect()
        except Exception as e:
            print(f"MQTT error: {e}")

        return values

    async def run_checks(self) -> list[StateComparison]:
        config = self.load_config()
        self.checks = self.build_checks(config)

        if not self.checks:
            print("No checks configured. Make sure config.ini has block_domains, allow_domains, or ubiquiti_rules.")
            return []

        print(f"Running {len(self.checks)} state checks...")
        print(f"  Overlord API: {self.overlord_url}")
        print(f"  MQTT Broker:  {self.mqtt_broker}:{self.mqtt_port}")
        print()

        # Fetch MQTT values (with retained messages)
        topics = [c.mqtt_topic for c in self.checks]
        print("Fetching MQTT values (waiting for retained messages)...")
        mqtt_values = self.fetch_mqtt_values(topics, timeout=5.0)

        for check in self.checks:
            if check.mqtt_topic in mqtt_values:
                check.mqtt_value = mqtt_values[check.mqtt_topic]
            else:
                check.mqtt_error = "No retained message"

        # Fetch API values concurrently
        print("Fetching API values...")
        await asyncio.gather(*[self.fetch_api_status(c) for c in self.checks])

        return self.checks

    def print_results(self) -> int:
        print()
        print("=" * 70)
        print("STATE DRIFT REPORT")
        print("=" * 70)
        print()

        drifts = 0
        errors = 0

        for check in self.checks:
            icon = check.status_icon()
            mqtt_display = check.mqtt_value if not check.mqtt_error else f"ERROR: {check.mqtt_error}"
            api_display = check.api_value if not check.api_error else f"ERROR: {check.api_error}"

            print(f"{icon} {check.name}")
            print(f"    MQTT:  {mqtt_display}")
            print(f"    API:   {api_display}")

            if check.mqtt_error or check.api_error:
                errors += 1
            elif not check.matches:
                drifts += 1
                norm_mqtt = check.normalize(check.mqtt_value)
                norm_api = check.normalize(check.api_value)
                print(f"    ⚠️  DRIFT DETECTED: MQTT={norm_mqtt} vs API={norm_api}")
            print()

        print("=" * 70)
        print(f"Total checks: {len(self.checks)}")
        print(f"  Matching:   {len(self.checks) - drifts - errors}")
        print(f"  Drifts:     {drifts}")
        print(f"  Errors:     {errors}")
        print("=" * 70)

        return 1 if drifts > 0 or errors > 0 else 0


def main():
    parser = argparse.ArgumentParser(
        description="Check for state drift between MQTT and Overlord API"
    )
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(__file__), "../etc/config.ini"),
        help="Path to config.ini file",
    )
    parser.add_argument(
        "--overlord-url",
        default=os.environ.get("OVERLORD_URL", "http://localhost:19000"),
        help="Overlord API base URL",
    )
    parser.add_argument(
        "--mqtt-broker",
        default=os.environ.get("MQTT_BROKER", "localhost"),
        help="MQTT broker address",
    )
    mqtt_port_env = os.environ.get("MQTT_PORT", "1883")
    parser.add_argument(
        "--mqtt-port",
        type=int,
        default=int(mqtt_port_env) if mqtt_port_env.isdigit() else 1883,
        help="MQTT broker port",
    )
    args = parser.parse_args()

    checker = StateDriftChecker(
        overlord_url=args.overlord_url,
        mqtt_broker=args.mqtt_broker,
        mqtt_port=args.mqtt_port,
        config_path=args.config,
    )

    asyncio.run(checker.run_checks())
    exit_code = checker.print_results()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
