"""Config flow for the AI Appliances integration.

Phase 0: a manual form collecting a dev token and the voice-backend channel
URL. This is scaffolding — it will be replaced by an OAuth2 flow (ADR-0006)
once the backend gains its authorization endpoints, so the hub link is bound to
a real account instead of a copied token.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_BACKEND_URL, CONF_DEV_TOKEN, DEFAULT_BACKEND_URL, DOMAIN


class AiAppliancesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AI Appliances."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # One config entry per backend channel URL.
            await self.async_set_unique_id(user_input[CONF_BACKEND_URL])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="AI Appliances", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_BACKEND_URL, default=DEFAULT_BACKEND_URL): str,
                vol.Required(CONF_DEV_TOKEN): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
