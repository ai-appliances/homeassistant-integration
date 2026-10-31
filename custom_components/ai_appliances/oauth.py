"""The AI Appliances account link and the token the channel presents.

The backend is the OAuth authorization server (ADR-0006): the user approves
the link on the AI Appliances consent page, Home Assistant keeps the tokens
in the config entry and refreshes them. Access tokens live an hour; the
voice backend re-checks the token of an open channel and closes it once the
token is no longer valid, so the channel reconnects with a fresh one.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
    OAuth2Session,
    OAuth2TokenRequestReauthError,
)

from .const import DOMAIN, OAUTH_AUTHORIZE_URL, OAUTH_CLIENT_ID, OAUTH_TOKEN_URL

_REGISTERED = f"{DOMAIN}_oauth_registered"


class AiAppliancesImplementation(LocalOAuth2ImplementationWithPkce):
    """Our backend, PKCE S256, no client secret."""

    @property
    def name(self) -> str:
        return "AI Appliances"


@callback
def async_register_implementation(hass: HomeAssistant) -> None:
    """Register once: the PKCE verifier lives on the instance, so replacing
    it while a link is in progress would break that link."""
    if hass.data.get(_REGISTERED):
        return
    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        AiAppliancesImplementation(hass, DOMAIN, OAUTH_CLIENT_ID, OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL),
    )
    hass.data[_REGISTERED] = True


class ChannelAuthRevoked(Exception):
    """The account link is gone; reauth has been started."""


class StaticChannelAuth:
    """A Phase 1 developer token: nothing to refresh."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def access_token(self) -> str:
        return self._token

    async def invalidate(self) -> None:
        """A rejected dev token stays rejected; nothing to do."""


class OAuthChannelAuth:
    """The config entry's OAuth token, refreshed when needed."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, session: OAuth2Session) -> None:
        self._hass = hass
        self._entry = entry
        self._session = session
        self._force_refresh = False

    async def access_token(self) -> str:
        """A valid access token. Raises ChannelAuthRevoked when the backend
        refused the refresh (the link was revoked) — HA starts reauth itself."""
        if self._force_refresh:
            self._force_refresh = False
            # Mark the stored token expired so the session refreshes it.
            token = {**self._session.token, "expires_at": 0}
            self._hass.config_entries.async_update_entry(self._entry, data={**self._entry.data, "token": token})
        try:
            await self._session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise ChannelAuthRevoked from err
        return self._session.token["access_token"]

    async def invalidate(self) -> None:
        """The voice backend refused this token (expired or revoked): get a
        new one before the next connect."""
        self._force_refresh = True
