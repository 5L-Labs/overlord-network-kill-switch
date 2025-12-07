"""
Integration tests for Pi-hole functionality.

These tests require a running Pi-hole instance. Use docker-compose.test.yaml
to start the test environment:

    cd tests && docker-compose -f docker-compose.test.yaml up -d
    pytest -m integration
    docker-compose -f docker-compose.test.yaml down -v
"""

import os
import pytest
import httpx

pytestmark = [pytest.mark.integration]

OVERLORD_URL = os.environ.get("OVERLORD_URL", "http://localhost:19000")
PIHOLE_URL = os.environ.get("PIHOLE_URL", "http://localhost:8080")


@pytest.fixture(scope="module")
def client():
    """HTTP client for testing."""
    with httpx.Client(base_url=OVERLORD_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="module")
def pihole_client():
    """HTTP client for direct Pi-hole access."""
    with httpx.Client(base_url=PIHOLE_URL, timeout=30.0) as client:
        yield client


class TestHealthCheck:
    """Test service health."""

    def test_overlord_root(self, client):
        """Test Overlord root endpoint responds."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_pihole_reachable(self, pihole_client):
        """Test Pi-hole is reachable."""
        response = pihole_client.get("/admin/")
        assert response.status_code == 200


class TestDomainBlocking:
    """Test domain blocking functionality through Overlord."""

    def test_get_domain_block_status(self, client):
        """Test getting domain block status."""
        response = client.get("/pihole/status/testblock")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_enable_domain_block(self, client):
        """Test enabling a domain block."""
        response = client.post("/pihole/enable/testblock")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        status_response = client.get("/pihole/status/testblock")
        assert status_response.json()["status"] == "true"

    def test_disable_domain_block(self, client):
        """Test disabling a domain block."""
        client.post("/pihole/enable/testblock")

        response = client.post("/pihole/disable/testblock")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        status_response = client.get("/pihole/status/testblock")
        assert status_response.json()["status"] == "false"

    def test_toggle_domain_block(self, client):
        """Test toggling domain block on and off."""
        client.post("/pihole/enable/testblock")
        status1 = client.get("/pihole/status/testblock")
        assert status1.json()["status"] == "true"

        client.post("/pihole/disable/testblock")
        status2 = client.get("/pihole/status/testblock")
        assert status2.json()["status"] == "false"

        client.post("/pihole/enable/testblock")
        status3 = client.get("/pihole/status/testblock")
        assert status3.json()["status"] == "true"


class TestGlobalDNSControl:
    """Test global DNS blocking control."""

    def test_get_dns_status(self, client):
        """Test getting global DNS blocking status."""
        response = client.get("/alldns/")
        assert response.status_code == 200
        assert "status" in response.json()
        assert response.json()["status"] in ["true", "false", "unknown"]

    def test_disable_dns_blocking(self, client):
        """Test disabling global DNS blocking."""
        client.delete("/alldns/")

        response = client.post("/alldns/")
        assert response.status_code == 200
        assert response.json()["status"] == "false"

    def test_enable_dns_blocking(self, client):
        """Test enabling global DNS blocking."""
        client.post("/alldns/")

        response = client.delete("/alldns/")
        assert response.status_code == 200
        assert response.json()["status"] == "true"

    def test_disable_with_timer(self, client):
        """Test disabling DNS blocking with a timer."""
        client.delete("/alldns/")

        response = client.post("/alldns/", params={"timer": 60})
        assert response.status_code == 200
        assert response.json()["status"] == "false"

        client.delete("/alldns/")


class TestErrorHandling:
    """Test error handling."""

    def test_unknown_domain_block(self, client):
        """Test requesting status of unknown domain block."""
        response = client.get("/pihole/status/nonexistent_block")
        assert response.status_code == 200
        assert response.json() == {"status": "Unknown"}

    def test_enable_unknown_domain_block(self, client):
        """Test enabling unknown domain block returns error."""
        response = client.post("/pihole/enable/nonexistent_block")
        assert response.status_code in [200, 404]
