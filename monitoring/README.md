# Observability & Health Monitoring

## Container Health Check

The Containerfile includes a built-in health check that Podman uses to monitor service health:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:19000/ || exit 1
```

### Podman Auto-Restart on Failure

Run the container with `--restart=on-failure` to automatically restart when unhealthy:

```bash
podman run -d --replace --name=overlord-dns \
  -p 19000:19000 \
  --restart=on-failure:5 \
  --env-file=./etc/envfile \
  ghcr.io/nickjlange/overlord-network-kill-switch:latest
```

Check container health status:
```bash
podman inspect --format='{{.State.Health.Status}}' overlord-dns
podman healthcheck run overlord-dns
```

## Datadog Monitoring

### Setup (on monitoring node)

1. **Install Datadog Agent** on your monitoring node

2. **Configure HTTP Check** - Copy to `/etc/datadog-agent/conf.d/http_check.d/conf.yaml`:
   ```yaml
   init_config:
   instances:
     - name: overlord_network_kill_switch
       url: http://<OVERLORD_HOST>:19000/
       method: GET
       timeout: 10
       http_response_status_code: 200
       collect_response_time: true
       tags:
         - service:overlord-network-kill-switch
         - env:production
   ```

3. **Restart Datadog Agent**:
   ```bash
   sudo systemctl restart datadog-agent
   ```

4. **Create Monitors** - Use the definitions in `datadog-monitor.yaml` via:
   - Datadog UI (Monitors → New Monitor)
   - Datadog API
   - Terraform `datadog_monitor` resource

### Monitors Included

| Monitor | Type | Description |
|---------|------|-------------|
| Service Down | Service Check | Alerts after 3 consecutive health check failures |
| Slow Response | Metric Alert | Alerts when response time exceeds 5 seconds |

### Customization

Update `datadog-monitor.yaml` to:
- Change `<OVERLORD_HOST>` to your container host IP/hostname
- Modify notification channels (`@slack-homelab-alerts`)
- Adjust thresholds for your environment
