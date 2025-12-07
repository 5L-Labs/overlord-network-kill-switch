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
    with httpx.Client(base_url=OVERLORD_URL, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="module")
def pihole_client():
    """HTTP client for direct Pi-hole access."""
    with httpx.Client(base_url=PIHOLE_URL, timeout=30.0) as c:
        yield c


class TestHealthCheck:
    """Test service health."""

    def test_overlord_root(self, client):
        """Test Overlord root endpoint responds."""
        response = client.get("/")
        print(f"Overlord response: {response.status_code} - {response.text}")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_pihole_reachable(self, pihole_client):
        """Test Pi-hole is reachable."""
        response = pihole_client.get("/admin/")
        print(f"Pi-hole response: {response.status_code}")
        assert response.status_code == 200


class TestGlobalDNSControl:
    """Test global DNS blocking control."""

    def test_get_dns_status(self, client):
        """Test getting global DNS blocking status."""
        response = client.get("/alldns/")
        print(f"GET /alldns/: {response.status_code} - {response.text}")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["true", "false", "unknown"]
