# grafana-screenshot

Tiny HTTP server that periodically screenshots a public Grafana dashboard with Playwright and serves the latest PNG. Used to feed a low-power kiosk display.

Image: `ghcr.io/liamniou/grafana-screenshot:latest`

## Env

- `GRAFANA_URL` — full dashboard URL (typically with `&kiosk`)
- `SCREENSHOT_INTERVAL` — seconds between captures
- `WIDTH`, `HEIGHT` — viewport size
- `HTTP_PORT` — listen port (default `8080`)
