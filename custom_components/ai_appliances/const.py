"""Constants for the AI Appliances integration."""

DOMAIN = "ai_appliances"

# Config entry keys.
CONF_BACKEND_URL = "backend_url"
CONF_DEV_TOKEN = "dev_token"

# Phase-0 scaffolding default. The OAuth2 flow (Phase 2, see ADR-0006) replaces
# the dev token with a real hub link; until then this lets the thin vertical
# slice ("voice -> HA -> lamp") be exercised without account linking.
DEFAULT_BACKEND_URL = "wss://voice.example.com/ha-channel"

# v1 scope (ADR-0006): what the speaker may switch, and what it may only read.
CONTROL_DOMAINS = {"light", "switch", "fan"}
READ_DOMAINS = {"sensor", "binary_sensor"}
# Never sent to the backend and never executed, even when exposed.
SECURITY_DOMAINS = {"lock", "alarm_control_panel", "cover"}
