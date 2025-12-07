# Overlord Network Kill Switch

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
