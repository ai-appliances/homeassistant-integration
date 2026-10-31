"""Constants for the AI Appliances integration."""

DOMAIN = "ai_appliances"

# Config entry keys.
CONF_BACKEND_URL = "backend_url"
# Phase 1 entries linked by a developer token; kept working until the user
# re-links the account over OAuth (the integration asks for it).
CONF_DEV_TOKEN = "dev_token"

# The hub link (ADR-0006 Phase 2): authorization code + PKCE against the
# AI Appliances account. A public client — there is no secret to ship.
OAUTH_CLIENT_ID = "ai-appliances-home-assistant"
OAUTH_AUTHORIZE_URL = "https://app.ai-appliance.store/oauth/authorize"
OAUTH_TOKEN_URL = "https://app.ai-appliance.store/api/oauth/token"

# The channel on our own domain: the frontend's nginx proxies it to wherever
# voice-backend runs, so installed integrations never learn (or depend on)
# that address. The options let a self-hosted backend replace it.
DEFAULT_BACKEND_URL = "wss://app.ai-appliance.store/ha-channel"

# v1 scope (ADR-0006): what the speaker may switch, and what it may only read.
CONTROL_DOMAINS = {"light", "switch", "fan"}
READ_DOMAINS = {"sensor", "binary_sensor"}
# Never sent to the backend and never executed, even when exposed.
SECURITY_DOMAINS = {"lock", "alarm_control_panel", "cover"}
