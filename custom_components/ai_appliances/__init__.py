"""The AI Appliances integration.

Connects a Home Assistant instance to the AI Appliances voice backend so the
speaker can control exposed entities by voice. See ADR-0006 in the
ai-appliances meta-repo for the architecture: an outbound channel from this
component terminates at voice-backend, which owns the tool contract and the
entity resolver (the server owns meaning, the hub executes).
"""

from __future__ import annotations

import logging

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)

from .channel import ChannelClient
from .const import CONF_BACKEND_URL, CONF_DEV_TOKEN, DEFAULT_BACKEND_URL, DOMAIN
from .oauth import OAuthChannelAuth, StaticChannelAuth, async_register_implementation

_LOGGER = logging.getLogger(__name__)

# No entity platforms: the component exposes nothing of its own, it only
# carries the channel (ADR-0007).
PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AI Appliances from a config entry: start the channel."""
    url = entry.options.get(CONF_BACKEND_URL) or entry.data.get(CONF_BACKEND_URL) or DEFAULT_BACKEND_URL
    if "token" in entry.data:
        async_register_implementation(hass)
        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(hass, entry)
        session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
        try:
            await session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise ConfigEntryAuthFailed("The AI Appliances account link was revoked") from err
        except (OAuth2TokenRequestError, ClientError) as err:
            raise ConfigEntryNotReady("AI Appliances is unreachable") from err
        auth: OAuthChannelAuth | StaticChannelAuth = OAuthChannelAuth(hass, entry, session)
    else:
        # A Phase 1 entry linked by a developer token: keep it working, and
        # ask the user to link the account properly (reauth runs the OAuth flow).
        entry.async_start_reauth(hass)
        auth = StaticChannelAuth(entry.data[CONF_DEV_TOKEN])
    client = ChannelClient(hass, url, auth)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    # Cancelled by HA when the entry unloads, which also ends the channel.
    entry.async_create_background_task(hass, client.run(), f"{DOMAIN}_channel")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
