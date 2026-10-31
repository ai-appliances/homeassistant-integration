"""The AI Appliances integration.

Connects a Home Assistant instance to the AI Appliances voice backend so the
speaker can control exposed entities by voice. See ADR-0006 in the
ai-appliances meta-repo for the architecture: an outbound channel from this
component terminates at voice-backend, which owns the tool contract and the
entity resolver (the server owns meaning, the hub executes).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .channel import ChannelClient
from .const import CONF_BACKEND_URL, CONF_DEV_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

# No entity platforms: the component exposes nothing of its own, it only
# carries the channel (ADR-0007).
PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AI Appliances from a config entry: start the channel."""
    client = ChannelClient(hass, entry.data[CONF_BACKEND_URL], entry.data[CONF_DEV_TOKEN])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    # Cancelled by HA when the entry unloads, which also ends the channel.
    entry.async_create_background_task(hass, client.run(), f"{DOMAIN}_channel")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
