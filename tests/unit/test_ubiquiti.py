import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

pytestmark = pytest.mark.unit


class TestUbiquitiOverlord:
    """Unit tests for UbiquitiOverlord class."""

    @patch("ubiquity.ubiquity.requests.session")
    def test_init(self, mock_session, mock_app_config):
        """Test UbiquitiOverlord initialization."""
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)

        assert overlord.controller == "192.168.1.1"
        assert overlord.ubiquiti_api_key == "test_api_key"
        assert "kids_devices" in overlord.macs
        assert overlord.logged_in is False

    @patch("ubiquity.ubiquity.requests.session")
    def test_first_connect_with_api_key(self, mock_session_class, mock_app_config):
        """Test first_connect sets up session with API key."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()

        assert overlord.logged_in is True
        mock_session.headers.update.assert_called_with(
            {"X-API-KEY": "test_api_key"}
        )

    @patch("ubiquity.ubiquity.requests.session")
    def test_first_connect_without_api_key(self, mock_session, mock_app_config):
        """Test first_connect raises error without API key."""
        mock_app_config["ubiquiti_api_key"] = None
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)

        with pytest.raises(HTTPException) as exc_info:
            overlord.first_connect()
        assert exc_info.value.status_code == 401

    @patch("ubiquity.ubiquity.requests.session")
    def test_parse_firewall_rules(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test parsing firewall rules from controller."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()
        overlord.parse_firewall_rules()

        assert overlord.firewall_rules["Block_Gaming"]["_id"] == "rule1"
        assert overlord.firewall_rules["Block_Gaming"]["enabled"] is True
        assert overlord.last_rules_check is not None

    @patch("ubiquity.ubiquity.requests.session")
    def test_status_rule(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test getting firewall rule status."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()
        overlord.parse_firewall_rules()

        result = overlord.status_rule("Block_Gaming")

        assert result == {"status": True}

    @patch("ubiquity.ubiquity.requests.session")
    def test_change_rule_enable(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test enabling a firewall rule."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()
        overlord.parse_firewall_rules()

        result = overlord.change_rule("enabled", "Block_Gaming")

        assert result["status"] is True
        mock_ubiquiti_session.put.assert_called_once()

    @patch("ubiquity.ubiquity.requests.session")
    def test_change_rule_disable(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test disabling a firewall rule."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()
        overlord.parse_firewall_rules()

        overlord.change_rule("disabled", "Block_Social")

        mock_ubiquiti_session.put.assert_called_once()
        call_args = mock_ubiquiti_session.put.call_args
        payload = call_args[1]["json"]
        assert payload[0]["enabled"] is False

    @patch("ubiquity.ubiquity.requests.session")
    def test_change_rule_invalid_status(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test changing rule with invalid status raises error."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()

        with pytest.raises(HTTPException) as exc_info:
            overlord.change_rule("invalid", "Block_Gaming")
        assert exc_info.value.status_code == 400

    @patch("ubiquity.ubiquity.requests.session")
    def test_change_rule_invalid_rule(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test changing non-existent rule raises error."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()

        with pytest.raises(HTTPException) as exc_info:
            overlord.change_rule("enabled", "Nonexistent_Rule")
        assert exc_info.value.status_code == 400

    @patch("ubiquity.ubiquity.requests.session")
    def test_change_device_block(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test blocking a device."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()

        result = overlord.change_device("offline", "kids_devices")

        assert result == {"status": "offline"}
        mock_ubiquiti_session.post.assert_called_once()
        call_args = mock_ubiquiti_session.post.call_args
        payload = call_args[1]["json"]
        assert payload["cmd"] == "block-sta"
        assert payload["mac"] == "aa:bb:cc:dd:ee:ff"

    @patch("ubiquity.ubiquity.requests.session")
    def test_change_device_unblock(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test unblocking a device."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()

        result = overlord.change_device("online", "kids_devices")

        assert result == {"status": "online"}
        call_args = mock_ubiquiti_session.post.call_args
        payload = call_args[1]["json"]
        assert payload["cmd"] == "unblock-sta"

    @patch("ubiquity.ubiquity.requests.session")
    def test_change_device_not_found(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test changing non-existent device raises error."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()

        with pytest.raises(HTTPException) as exc_info:
            overlord.change_device("offline", "nonexistent_device")
        assert exc_info.value.status_code == 404

    @patch("ubiquity.ubiquity.requests.session")
    def test_shutdown(self, mock_session_class, mock_app_config, mock_ubiquiti_session):
        """Test shutdown closes session."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()
        overlord.shutdown()

        assert overlord.logged_in is False
        mock_ubiquiti_session.close.assert_called_once()

    @patch("ubiquity.ubiquity.requests.session")
    def test_rules_cache_freshness(
        self, mock_session_class, mock_app_config, mock_ubiquiti_session
    ):
        """Test that rules are refreshed when stale."""
        mock_session_class.return_value = mock_ubiquiti_session
        from ubiquity.ubiquity import UbiquitiOverlord
        from datetime import datetime, timedelta

        overlord = UbiquitiOverlord(app_config=mock_app_config)
        overlord.first_connect()
        overlord.parse_firewall_rules()

        overlord.last_rules_check = datetime.now() - timedelta(seconds=120)
        overlord.check_rules_freshness()

        assert mock_ubiquiti_session.get.call_count == 2
