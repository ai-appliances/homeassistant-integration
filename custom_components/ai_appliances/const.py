"""Constants for the AI Appliances integration."""

DOMAIN = "ai_appliances"

# Config entry keys.
CONF_BACKEND_URL = "backend_url"
CONF_DEV_TOKEN = "dev_token"

# Phase-0 scaffolding default. The OAuth2 flow (Phase 2, see ADR-0006) replaces
# the dev token with a real hub link; until then this lets the thin vertical
# slice ("voice -> HA -> lamp") be exercised without account linking.
DEFAULT_BACKEND_URL = "wss://voice.example.com/ha-channel"
