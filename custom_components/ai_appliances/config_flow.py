"""Config flow for the AI Appliances integration.

Linking is OAuth (ADR-0006 Phase 2): Home Assistant sends the user to the AI
Appliances consent page, the backend issues the tokens for the hub link.
Reauth runs the same flow — after a revoked link, and to move a Phase 1
developer-token entry onto a real account link.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import CONF_BACKEND_URL, DEFAULT_BACKEND_URL, DOMAIN
from .oauth import async_register_implementation


class AiAppliancesConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Link Home Assistant to an AI Appliances account."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        async_register_implementation(self.hass)
        return await super().async_step_user(user_input)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        if self.source == SOURCE_REAUTH:
            # Replaces the data wholesale: neither a developer token nor a
            # Phase 1 channel url survives the move to the account link (a
            # self-hosted backend is set in the options).
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
        return self.async_create_entry(title="AI Appliances", data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AiAppliancesOptionsFlow:
        return AiAppliancesOptionsFlow()


class AiAppliancesOptionsFlow(OptionsFlowWithReload):
    """A self-hosted voice backend instead of the production one."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_BACKEND_URL) or DEFAULT_BACKEND_URL
        schema = vol.Schema({vol.Required(CONF_BACKEND_URL, default=current): str})
        return self.async_show_form(step_id="init", data_schema=schema)
