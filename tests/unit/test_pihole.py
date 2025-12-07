import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit

PIHOLE_CLIENT_PATCH = "pihole.base.PiHole6Client"


class TestPiHoleOverlord:
    """Unit tests for PiHoleOverlord class."""

    @patch(PIHOLE_CLIENT_PATCH)
    def test_init(self, mock_client_class, mock_app_config):
        """Test PiHoleOverlord initialization."""
        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)

        assert overlord.piList == ["192.168.1.100"]
        assert "youtube" in overlord.block_domains
        assert "school" in overlord.allow_domains
        assert overlord.logged_in is False

    @patch(PIHOLE_CLIENT_PATCH)
    def test_first_connect(self, mock_client_class, mock_app_config, mock_pihole_client):
        """Test first_connect establishes sessions."""
        mock_client_class.return_value = mock_pihole_client
        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)
        overlord.first_connect()

        assert overlord.logged_in is True
        assert "192.168.1.100" in overlord.sessions
        mock_client_class.assert_called_once_with(
            "http://192.168.1.100", "test_password"
        )

    @patch(PIHOLE_CLIENT_PATCH)
    def test_get_domain_block_status_enabled(
        self, mock_client_class, mock_app_config, mock_pihole_client
    ):
        """Test getting status of an enabled domain block."""
        mock_client_class.return_value = mock_pihole_client
        mock_pihole_client.domain_management.get_domain.return_value = {
            "domains": [{"domain": "youtube.com", "enabled": True}]
        }
        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)
        result = overlord.get("youtube")

        assert result == {"status": "true"}

    @patch(PIHOLE_CLIENT_PATCH)
    def test_get_domain_block_status_disabled(
        self, mock_client_class, mock_app_config, mock_pihole_client
    ):
        """Test getting status of a disabled domain block."""
        mock_client_class.return_value = mock_pihole_client
        mock_pihole_client.domain_management.get_domain.return_value = {
            "domains": [{"domain": "youtube.com", "enabled": False}]
        }
        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)
        result = overlord.get("youtube")

        assert result == {"status": "false"}

    @patch(PIHOLE_CLIENT_PATCH)
    def test_get_unknown_domain_block(self, mock_client_class, mock_app_config):
        """Test getting status of non-existent domain block."""
        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)
        result = overlord.get("nonexistent")

        assert result == {"status": "Unknown"}

    @patch(PIHOLE_CLIENT_PATCH)
    def test_post_enable_domain_block(
        self, mock_client_class, mock_app_config, mock_pihole_client
    ):
        """Test enabling a domain block."""
        mock_client_class.return_value = mock_pihole_client
        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)
        result = overlord.post("enable", "youtube")

        assert result == {"status": "ok"}
        assert mock_pihole_client.domain_management.add_domain.call_count == 2

    @patch(PIHOLE_CLIENT_PATCH)
    def test_post_disable_domain_block(
        self, mock_client_class, mock_app_config, mock_pihole_client
    ):
        """Test disabling a domain block."""
        mock_client_class.return_value = mock_pihole_client
        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)
        result = overlord.post("disable", "youtube")

        assert result == {"status": "ok"}
        assert mock_pihole_client.domain_management.delete_domain.call_count == 2

    @patch(PIHOLE_CLIENT_PATCH)
    def test_shutdown(self, mock_client_class, mock_app_config, mock_pihole_client):
        """Test shutdown closes sessions."""
        mock_client_class.return_value = mock_pihole_client
        from pihole.pihole import PiHoleOverlord

        overlord = PiHoleOverlord(app_config=mock_app_config)
        overlord.first_connect()
        overlord.shutdown()

        assert overlord.logged_in is False
        mock_pihole_client.close_session.assert_called_once()


class TestMasterEnabler:
    """Unit tests for MasterEnabler (global DNS control)."""

    @patch(PIHOLE_CLIENT_PATCH)
    def test_get_blocking_enabled(
        self, mock_client_class, mock_app_config, mock_pihole_client
    ):
        """Test getting DNS blocking status when enabled."""
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
    def test_get_blocking_disabled(
        self, mock_client_class, mock_app_config, mock_pihole_client
    ):
        """Test getting DNS blocking status when disabled."""
        mock_client_class.return_value = mock_pihole_client
        mock_pihole_client.dns_control.get_blocking_status.return_value = {
            "blocking": "disabled",
            "timer": 60,
        }
        from pihole.alldns import MasterEnabler

        enabler = MasterEnabler(app_config=mock_app_config)
        result = enabler.get()

        assert result == {"status": "false"}

    @patch(PIHOLE_CLIENT_PATCH)
    def test_disable_dns_blocking(
        self, mock_client_class, mock_app_config, mock_pihole_client
    ):
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
        mock_pihole_client.dns_control.set_blocking_status.assert_called_once_with(
            False, 60
        )

    @patch(PIHOLE_CLIENT_PATCH)
    def test_enable_dns_blocking(
        self, mock_client_class, mock_app_config, mock_pihole_client
    ):
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
        mock_pihole_client.dns_control.set_blocking_status.assert_called_once()
