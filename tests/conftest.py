import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../cgi-bin"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../lib"))

os.environ.setdefault("PYTHONPATH", os.path.join(os.path.dirname(__file__), "../lib"))


@pytest.fixture
def mock_app_config():
    """Base app configuration for testing."""
    return {
        "default_log_level": 10,  # DEBUG
        "logger": MagicMock(),
        "pihole_control_enabled": True,
        "ubiquiti_control_enabled": True,
        "mqtt_announce_enabled": False,
        "remote_pi_list": ["192.168.1.100"],
        "remote_pi_password": "test_password",
        "block_domains": {
            "youtube": ["youtube.com", "googlevideo.com"],
            "netflix": ["netflix.com"],
        },
        "allow_domains": {
            "school": ["edu.example.com"],
        },
        "ubiquiti_device": "192.168.1.1",
        "ubiquiti_api_key": "test_api_key",
        "ubiquiti_targets": {
            "kids_devices": ["AA:BB:CC:DD:EE:FF"],
        },
        "ubiquiti_rules": {
            "Block_Gaming": {},
            "Block_Social": {},
        },
    }


@pytest.fixture
def mock_pihole_client():
    """Mock PiHole6Client for unit tests."""
    client = MagicMock()
    client.domain_management.get_domain.return_value = {
        "domains": [{"domain": "youtube.com", "enabled": True}]
    }
    client.domain_management.add_domain.return_value = {
        "domains": [{"domain": "youtube.com", "enabled": True}]
    }
    client.domain_management.delete_domain.return_value = {
        "domains": [{"domain": "youtube.com", "enabled": False}]
    }
    client.dns_control.get_blocking_status.return_value = {
        "blocking": "enabled",
        "timer": None,
    }
    client.dns_control.set_blocking_status.return_value = {"status": "ok"}
    client.close_session.return_value = None
    return client


@pytest.fixture
def mock_ubiquiti_session():
    """Mock requests.Session for Ubiquiti API."""
    session = MagicMock()
    
    firewall_rules_response = MagicMock()
    firewall_rules_response.status_code = 200
    firewall_rules_response.json.return_value = [
        {"_id": "rule1", "name": "Block_Gaming", "enabled": True},
        {"_id": "rule2", "name": "Block_Social", "enabled": False},
    ]
    
    change_rule_response = MagicMock()
    change_rule_response.status_code = 200
    change_rule_response.json.return_value = {"meta": {"rc": "ok"}}
    
    device_response = MagicMock()
    device_response.status_code = 200
    device_response.json.return_value = {"meta": {"rc": "ok"}}
    
    session.get.return_value = firewall_rules_response
    session.put.return_value = change_rule_response
    session.post.return_value = device_response
    
    return session
