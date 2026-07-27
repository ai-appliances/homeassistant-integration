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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# No entity platforms yet — Phase 0 only establishes the config entry. The
# outbound channel client (WebSocket to voice-backend, pushing the exposed
# registry and executing inbound commands) lands in Phase 1.
PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AI Appliances from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data
    _LOGGER.info(
        "AI Appliances entry loaded; channel client not implemented yet (Phase 1)"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
