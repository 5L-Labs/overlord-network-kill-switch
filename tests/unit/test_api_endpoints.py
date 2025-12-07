"""
Unit tests for API endpoints.

Note: Full endpoint integration is tested via integration tests.
These tests focus on the route handlers in isolation.
"""

import pytest
from unittest.mock import patch

pytestmark = pytest.mark.unit

PIHOLE_CLIENT_PATCH = "pihole.base.PiHole6Client"


class TestPiholeRouter:
    """Test Pi-hole router functions directly."""

    def test_pihole_router_init(self, mock_app_config):
        """Test pihole_router.init creates instances."""
        with patch(PIHOLE_CLIENT_PATCH):
            from pihole import pihole_router

            pihole_router.init(mock_app_config)

            assert pihole_router.pihole is not None
            assert pihole_router.all_dns is not None

    @patch(PIHOLE_CLIENT_PATCH)
    def test_pihole_get_status(self, mock_client_class, mock_app_config, mock_pihole_client):
        """Test pihole.get returns correct status."""
        mock_client_class.return_value = mock_pihole_client
        mock_pihole_client.domain_management.get_domain.return_value = {
            "domains": [{"domain": "youtube.com", "enabled": True}]
        }

        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)
        result = overlord.get("youtube")

        assert result == {"status": "true"}

    @patch(PIHOLE_CLIENT_PATCH)
    def test_pihole_post_enable(self, mock_client_class, mock_app_config, mock_pihole_client):
        """Test pihole.post with enable direction."""
        mock_client_class.return_value = mock_pihole_client

        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)
        result = overlord.post("enable", "youtube")

        assert result == {"status": "ok"}

    @patch(PIHOLE_CLIENT_PATCH)
    def test_pihole_post_disable(self, mock_client_class, mock_app_config, mock_pihole_client):
        """Test pihole.post with disable direction."""
        mock_client_class.return_value = mock_pihole_client

        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)
        result = overlord.post("disable", "youtube")

        assert result == {"status": "ok"}


class TestAlldnsRouter:
    """Test all_dns router functions directly."""

    @patch(PIHOLE_CLIENT_PATCH)
    def test_alldns_get(self, mock_client_class, mock_app_config, mock_pihole_client):
        """Test all_dns.get returns status."""
        mock_client_class.return_value = mock_pihole_client
        mock_pihole_client.dns_control.get_blocking_status.return_value = {
            "blocking": "enabled",
            "timer": None,
        }

        from pihole.alldns import MasterEnabler

        enabler = MasterEnabler(app_config=mock_app_config)
        result = enabler.get()

        assert result == {"status": "true"}

    @patch(PIHOLE_CLIENT_PATCH)
    def test_alldns_enable(self, mock_client_class, mock_app_config, mock_pihole_client):
        """Test enabling DNS blocking."""
        mock_client_class.return_value = mock_pihole_client
        mock_pihole_client.dns_control.get_blocking_status.return_value = {
            "blocking": "enabled",
            "timer": None,
        }

        from pihole.alldns import MasterEnabler

        enabler = MasterEnabler(app_config=mock_app_config)
        result = enabler.enable_dns_blocking()

        assert result == {"status": "true"}

    @patch(PIHOLE_CLIENT_PATCH)
    def test_alldns_disable(self, mock_client_class, mock_app_config, mock_pihole_client):
        """Test disabling DNS blocking."""
        mock_client_class.return_value = mock_pihole_client
        mock_pihole_client.dns_control.get_blocking_status.return_value = {
            "blocking": "disabled",
            "timer": 60,
        }

        from pihole.alldns import MasterEnabler

        enabler = MasterEnabler(app_config=mock_app_config)
        result = enabler.disable_dns_blocking(timer=60)

        assert result == {"status": "false"}


class TestUbiquitiRouter:
    """Test Ubiquiti router functions directly."""

    @patch("ubiquity.ubiquity.requests.session")
    def test_ubiquiti_init(self, mock_session, mock_app_config):
        """Test ubiquity.init creates UDM instance."""
        from ubiquity import ubiquity

        ubiquity.init(mock_app_config)

        assert ubiquity.udm is not None
        assert ubiquity.udm.controller == "192.168.1.1"

    @patch("ubiquity.ubiquity.requests.session")
    def test_ubiquiti_status_rule(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test getting rule status."""
        mock_session_class.return_value = mock_ubiquiti_session

        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()
        overlord.parse_firewall_rules()

        result = overlord.status_rule("Block_Gaming")

        assert result == {"status": True}

    @patch("ubiquity.ubiquity.requests.session")
    def test_ubiquiti_change_rule(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test changing rule status."""
        mock_session_class.return_value = mock_ubiquiti_session

        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()
        overlord.parse_firewall_rules()

        result = overlord.change_rule("enabled", "Block_Gaming")

        assert "status" in result

    @patch("ubiquity.ubiquity.requests.session")
    def test_ubiquiti_change_device(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test blocking/unblocking device."""
        mock_session_class.return_value = mock_ubiquiti_session

        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()

        result = overlord.change_device("offline", "kids_devices")

        assert result == {"status": "offline"}
