# Overlord Network Kill Switch

## Engineering Preferences

These preferences shape all work on this project. Apply them before any other consideration.

- **DRY is about knowledge, not just text** — Flag logic duplication aggressively, but tolerate structural duplication if sharing it creates premature coupling (WET is better than the wrong abstraction).
- **Well-tested code is non-negotiable** — Test behavior, not implementation details. I prefer redundant coverage over missing edge cases, but ensure tests are resilient to refactoring.
- **Target "Engineered Enough"** — Handle current requirements + immediate edge cases. **Apply YAGNI**: do not build for hypothetical future use cases. Abstract only when you see the pattern for the third time (Rule of Three).
- **Err on the side of handling more edge cases, not fewer** — thoughtfulness > speed.
- **Bias toward explicit over clever.**

---

## Review Process (Plan Mode)

Before starting a review, you **MUST** ask:

> **BIG CHANGE or SMALL CHANGE?**
> 1. **BIG CHANGE**: Work through this interactively, one section at a time (Architecture → Code Quality → Tests → Performance) with at most 4 top issues in each section.
> 2. **SMALL CHANGE**: Work through interactively ONE question per review section.

### Review Sections

Walk through these four sections **in order**, presenting one section at a time. Wait for user feedback before proceeding to the next.

1. **Architecture review** — overall system design, component boundaries, dependency graph, coupling, data flow, scaling, security.
2. **Code quality review** — organization, module structure, DRY violations, error handling patterns, missing edge cases, tech debt hotspots, and over/under-engineering relative to preferences.
3. **Test review** — coverage gaps (unit, integration, e2e), test quality, assertion strength, missing edge cases, untested failure modes, and error paths.
4. **Performance review** — N+1 queries, database access patterns, memory-usage concerns, caching opportunities, slow or high-complexity code paths.

### Issue Format

For every specific issue (bug, smell, design concern, or risk):

- Describe the problem concretely, with file and line references.
- Present 2-3 options, including "do nothing" where reasonable.
- For each option, specify: implementation effort, risk, impact on other code, and **maintenance burden**.
- Give an opinionated recommendation and why, mapped to the engineering preferences.
- Explicitly ask whether the user agrees or wants a different direction before proceeding.

**Formatting Rules**:
- **NUMBER issues** (1, 2, 3...) and then give **LETTERS for options** (A, B, C...).
- The recommended option must always be the 1st option (Option A).
- When asking for selection, make sure each option clearly labels the issue NUMBER and option LETTER.

---

## Project Overview

A HomeKit-integrated network control system for parental controls and focus time management. Controls Pi-hole DNS filtering and Ubiquiti firewall rules via a FastAPI server.

## Architecture

```
HomeKit → Homebridge (MQTT Thing) → MQTT Broker → Node-RED → FastAPI Server → Pi-hole / Ubiquiti
```

## Tech Stack

- **Language**: Python 3.12
- **Framework**: FastAPI with Gunicorn/Uvicorn
- **Libraries**: pihole6api, requests, aiomqtt, pydantic
- **Container**: Podman/Docker

## Project Structure

```
├── cgi-bin/                    # FastAPI application
│   ├── controller.py           # Main app, config init, lifespan
│   ├── wsgi.py                 # WSGI entry point
│   └── gunicorn_config.py      # Gunicorn settings
├── lib/
│   ├── pihole/                 # Pi-hole integration
│   │   ├── base.py             # BaseHTTPHandler base class
│   │   ├── pihole.py           # PiHoleOverlord - domain blocking
│   │   ├── pihole_router.py    # FastAPI routes for /pihole
│   │   └── alldns.py           # MasterEnabler - global DNS toggle
│   └── ubiquity/               # Ubiquiti integration
│       └── ubiquity.py         # UbiquitiOverlord - firewall/device control
├── etc/
│   ├── config.ini.sample       # Configuration template
│   ├── envfile.sample          # Environment variables template
│   └── webserver_requirements.txt  # Python dependencies
├── node_red_flows/             # Node-RED flow examples
├── pihole/                     # Pi-hole config examples
├── Containerfile               # Container build file
├── Makefile                    # Build/deploy automation
└── pyproject.toml              # Python project config
```

## API Endpoints

### Pi-hole Control (`/pihole`)
- `GET /pihole/status/{domain_block}` - Check if domain block is enabled
- `POST /pihole/enable/{domain_block}` - Enable domain blocking
- `POST /pihole/disable/{domain_block}` - Disable domain blocking

### Global DNS Control (`/alldns`)
- `GET /alldns/` - Get DNS blocking status
- `POST /alldns/` - Disable DNS blocking (optional timer param)
- `DELETE /alldns/` - Enable DNS blocking

### Ubiquiti Control (`/ubiquiti`)
- `GET /ubiquiti/status_rule/{target}` - Get firewall rule status
- `GET /ubiquiti/enable_rule/{target}` - Enable firewall rule
- `GET /ubiquiti/disable_rule/{target}` - Disable firewall rule
- `GET /ubiquiti/status_device/{target}` - Get device status
- `GET /ubiquiti/enable_device/{target}` - Unblock device
- `GET /ubiquiti/disable_device/{target}` - Block device
- `GET /ubiquiti/refresh` - Force refresh firewall rules cache

## Configuration

### Environment Variables
- `DNS_SERVERS` - Comma-separated DNS server IPs
- `REMOTE_PI_PASSWORD` - Pi-hole admin password
- `REMOTE_PI_LIST` - Space-separated Pi-hole IPs
- `MQTT_BROKER` - MQTT broker address
- `MQTT_PORT` - MQTT broker port
- `REMOTE_UBIQUITI_DEVICE` - UniFi controller IP
- `REMOTE_UBIQUITI_API_KEY` - UniFi API key

### config.ini Sections
- `[general]` - Enable/disable subsystems
- `[mqtt]` - MQTT broker settings, LWT topics
- `[ubiquiti]` - Controller settings
- `[ubiquiti_targets]` - MAC address groups
- `[ubiquiti_rules]` - Firewall rule names
- `[block_domains]` - Domain regex groups to block
- `[allow_domains]` - Domain regex groups to allow

## Common Commands

```bash
# Build container
make full

# Run locally
make test-local

# Push to registry
make push

# Deploy to remote
target=user@host make push-local

# Run unit tests (mocked, fast)
make test-unit

# Run integration tests (requires Docker, spins up Pi-hole)
make test-integration

# Cleanup integration test containers
make test-integration-down
```

## Key Classes

- `PiHoleOverlord` (lib/pihole/pihole.py) - Manages per-domain blocking via pihole6api
- `MasterEnabler` (lib/pihole/alldns.py) - Global DNS blocking toggle
- `UbiquitiOverlord` (lib/ubiquity/ubiquity.py) - UniFi firewall rules and device blocking
- `BaseHTTPHandler` (lib/pihole/base.py) - Base class for Pi-hole handlers

## Dependencies

See `etc/webserver_requirements.txt` for full list. Key packages:
- fastapi, gunicorn, uvicorn
- pihole6api (Pi-hole v6 support)
- requests (Ubiquiti API)
- aiomqtt (MQTT publishing)
- pydantic (data validation)

## Recent Changes

- **Pi-hole v6 API Integration:** Uses `pihole6api` library for Pi-hole v6 API
- **Ubiquiti Control 9.4.19 Support:** Updated for latest Ubiquiti controller
- **Ubiquiti Session Caching:** Session data cached for performance
- **MQTT LWT Publishing:** Announces service status via MQTT
- **MQTT Bug Fix:** Fixed `topic_list` -> `lwt_topics` NameError in controller.py
- **Container Health Check:** Added HEALTHCHECK to Containerfile
- **Test Infrastructure:** Added pytest with unit tests (37 tests passing)

## Work In Progress (Branch: feature/observability-health-checks)

**Completed:**
- Container HEALTHCHECK in Containerfile (curl to localhost:19000 every 30s)
- Datadog monitoring config in `monitoring/` directory
- Unit tests: 37 tests passing (mocked Pi-hole + Ubiquiti)
- GitHub Actions workflow: Unit tests + Container Build Test passing
- MQTT error handling made non-fatal (warning instead of crash)

**In Progress:**
- Integration tests with real Pi-hole container
- Issue: Containers start (Pi-hole + Overlord) but pytest fails
- Debug needed: Check CI logs with GitHub auth OR run `make test-integration` locally

**Files added/modified on this branch:**
- `.github/workflows/test.yaml` - CI workflow
- `tests/` - Test directory with unit + integration tests
- `tests/docker-compose.test.yaml` - Pi-hole + Overlord for integration tests
- `monitoring/` - Datadog monitor configs
- `etc/test_requirements.txt` - pytest dependencies
- `Containerfile` - Added HEALTHCHECK
- `Makefile` - Added test-unit, test-integration targets
