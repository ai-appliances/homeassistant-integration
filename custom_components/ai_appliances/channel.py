"""Outbound channel to the AI Appliances voice backend (ADR-0007).

One WebSocket per config entry, opened from this Home Assistant (no inbound
port needed). On connect and on every change the component sends the full
registry of exposed appliances; the backend sends
`{"commands": [{"id", "type": "call_service", "domain", "service",
"entity_id", "data"}]}` and gets `{"type": "results", "results": [{"id",
"ok", "error"}]}` back with the same ids. A `get_state` command (exposed
sensors only) answers with the entity's current `state` and `unit`.

The backend resolves what the user meant; this side only executes, and only
for entities that are still exposed to voice assistants and not in a security
domain — the first line of defence of ADR-0006.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.components.homeassistant.exposed_entities import (
    async_listen_entity_updates,
    async_should_expose,
)
from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_UNIT_OF_MEASUREMENT, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2TokenRequestError
from homeassistant.helpers.start import async_at_started

from .const import CONTROL_DOMAINS, READ_DOMAINS, SECURITY_DOMAINS
from .oauth import ChannelAuthRevoked, OAuthChannelAuth, StaticChannelAuth

_LOGGER = logging.getLogger(__name__)

# The voice assistant whose "expose" setting decides what the speaker sees.
ASSISTANT = "conversation"
HEARTBEAT_SECONDS = 30
SERVICE_TIMEOUT_SECONDS = 4
RECONNECT_MAX_SECONDS = 60
# Light colour modes that take an rgb_color.
COLOR_MODES = {ColorMode.HS, ColorMode.XY, ColorMode.RGB, ColorMode.RGBW, ColorMode.RGBWW}
REGISTRY_DEBOUNCE_SECONDS = 1.0
# Close codes of the voice backend: the token is no longer valid (expired
# after its hour, or revoked) / the account unlinked this hub.
CLOSE_TOKEN_INVALID = 4401
CLOSE_UNLINKED = 4403


class ChannelClient:
    """Keeps the channel up and serves the backend's commands."""

    def __init__(self, hass: HomeAssistant, url: str, auth: OAuthChannelAuth | StaticChannelAuth) -> None:
        self.hass = hass
        self.url = url
        self.auth = auth
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._unsubs: list = []
        self._resend: asyncio.TimerHandle | None = None

    async def run(self) -> None:
        """Connect, serve, reconnect with backoff — until cancelled."""
        # The first snapshot waits for every integration to load: on a restart
        # the cloud ones (Tuya) add their entities late, and an early snapshot
        # would miss them until the next registry change.
        started = asyncio.Event()
        async_at_started(self.hass, lambda _: started.set())
        await started.wait()
        self._listen_for_changes()
        delay = 1
        session = async_get_clientsession(self.hass)
        try:
            while True:
                try:
                    token = await self.auth.access_token()
                    async with session.ws_connect(
                        self.url,
                        headers={"Authorization": f"Bearer {token}"},
                        heartbeat=HEARTBEAT_SECONDS,
                    ) as ws:
                        self._ws = ws
                        delay = 1
                        _LOGGER.info("Connected to the voice backend at %s", self.url)
                        await self._send_registry()
                        await self._serve(ws)
                        if ws.close_code in (CLOSE_TOKEN_INVALID, CLOSE_UNLINKED):
                            # Expired or revoked: reconnect at once with a
                            # refreshed token (a revoked link fails the refresh).
                            await self.auth.invalidate()
                            continue
                except ChannelAuthRevoked:
                    _LOGGER.warning("The AI Appliances account link was revoked; re-link the integration")
                    return
                except aiohttp.WSServerHandshakeError as err:
                    # A refusal before the socket opens carries no close code
                    # (the backend can't tell us "expired" from "down" here):
                    # refresh the token for the next attempt, with backoff.
                    _LOGGER.warning("Voice backend refused the channel (HTTP %s)", err.status)
                    await self.auth.invalidate()
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError, OAuth2TokenRequestError) as err:
                    _LOGGER.debug("Channel connection failed: %s", err)
                except Exception:  # noqa: BLE001 — a bug here must not end the channel for good
                    _LOGGER.exception("Channel failed; reconnecting")
                finally:
                    self._ws = None
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_MAX_SECONDS)
        finally:
            self._stop_listening()

    async def _serve(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        async for msg in ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                if msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break
                continue
            try:
                payload = msg.json()
            except ValueError:
                continue
            commands = payload.get("commands") if isinstance(payload, dict) else None
            if isinstance(commands, list):
                # Several commands of one turn (all lights in a room) run together.
                results = await asyncio.gather(*(self._execute(c) for c in commands))
                await ws.send_json({"type": "results", "results": list(results)})
        _LOGGER.info("Voice backend channel closed")

    async def _execute(self, command: Any) -> dict[str, Any]:
        command = command if isinstance(command, dict) else {}
        result: dict[str, Any] = {"id": command.get("id"), "ok": False}
        entity_id = str(command.get("entity_id") or "")
        domain = str(command.get("domain") or "")
        service = str(command.get("service") or "")
        if command.get("type") == "get_state":
            return self._read(command, result)
        if command.get("type") != "call_service":
            result["error"] = "unknown_command"
        elif entity_id.split(".")[0] != domain or domain not in CONTROL_DOMAINS:
            result["error"] = "domain_not_allowed"
        elif service not in ("turn_on", "turn_off"):
            result["error"] = "service_not_allowed"
        elif not async_should_expose(self.hass, ASSISTANT, entity_id):
            result["error"] = "not_exposed"
        elif (state := self.hass.states.get(entity_id)) is None or state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            # HA skips an unavailable entity silently and the call still
            # "succeeds" — the speaker must not confirm what did not happen.
            result["error"] = "unavailable"
        else:
            data = _light_data(command.get("data")) if domain == "light" else {}
            try:
                async with asyncio.timeout(SERVICE_TIMEOUT_SECONDS):
                    await self.hass.services.async_call(
                        domain, service, {"entity_id": entity_id, **data}, blocking=True
                    )
                result["ok"] = True
            except TimeoutError:
                result["error"] = "timeout"
            except Exception as err:  # noqa: BLE001 — any service failure is reported back
                _LOGGER.warning("Command %s.%s on %s failed: %s", domain, service, entity_id, err)
                result["error"] = "service_failed"
        return result

    def _read(self, command: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        """A sensor's current value — only what the user exposed."""
        entity_id = str(command.get("entity_id") or "")
        if entity_id.split(".")[0] not in READ_DOMAINS:
            result["error"] = "domain_not_allowed"
        elif not async_should_expose(self.hass, ASSISTANT, entity_id):
            result["error"] = "not_exposed"
        elif (state := self.hass.states.get(entity_id)) is None or state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            result["error"] = "unavailable"
        else:
            result.update(ok=True, state=state.state, unit=state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) or "")
        return result

    @callback
    def registry(self) -> list[dict[str, Any]]:
        """Exposed, user-facing appliances with their names, aliases, area and floor."""
        entities = er.async_get(self.hass)
        devices = dr.async_get(self.hass)
        areas = ar.async_get(self.hass)
        floors = fr.async_get(self.hass)
        appliances = []
        for state in self.hass.states.async_all():
            domain = state.domain
            if domain in SECURITY_DOMAINS or domain not in CONTROL_DOMAINS | READ_DOMAINS:
                continue
            if not async_should_expose(self.hass, ASSISTANT, state.entity_id):
                continue
            entry = entities.async_get(state.entity_id)
            if entry is not None and (entry.entity_category is not None or entry.hidden_by is not None):
                continue
            area_id = entry.area_id if entry else None
            if area_id is None and entry is not None and entry.device_id:
                device = devices.async_get(entry.device_id)
                area_id = device.area_id if device else None
            area = areas.async_get_area(area_id) if area_id else None
            floor = floors.async_get_floor(area.floor_id) if area and area.floor_id else None
            item = {
                "entity_id": state.entity_id,
                "name": state.name,
                # Aliases may hold a marker for "the entity's own name", not a string.
                "aliases": sorted(a for a in entry.aliases if isinstance(a, str)) if entry else [],
                "area": area.name if area else "",
                "floor": floor.name if floor else "",
                "state": state.state,
            }
            if domain == "light":
                modes = state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) or []
                item["color"] = any(mode in COLOR_MODES for mode in modes)
            elif domain in READ_DOMAINS:
                item["device_class"] = state.attributes.get(ATTR_DEVICE_CLASS) or ""
                item["unit"] = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) or ""
            appliances.append(item)
        return appliances

    async def _send_registry(self) -> None:
        if self._ws is None or self._ws.closed:
            return
        appliances = self.registry()
        await self._ws.send_json({"type": "registry", "appliances": appliances})
        _LOGGER.debug("Sent registry with %d appliances", len(appliances))

    @callback
    def _schedule_resend(self, *_: Any) -> None:
        """Changes come in bursts (renaming an area touches many entities)."""
        if self._resend is not None:
            self._resend.cancel()
        self._resend = self.hass.loop.call_later(
            REGISTRY_DEBOUNCE_SECONDS,
            lambda: self.hass.async_create_task(self._send_registry()),
        )

    @callback
    def _listen_for_changes(self) -> None:
        bus = self.hass.bus
        self._unsubs = [
            async_listen_entity_updates(self.hass, ASSISTANT, self._schedule_resend),
            bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._schedule_resend),
            bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, self._schedule_resend),
            bus.async_listen(ar.EVENT_AREA_REGISTRY_UPDATED, self._schedule_resend),
            bus.async_listen(fr.EVENT_FLOOR_REGISTRY_UPDATED, self._schedule_resend),
        ]

    @callback
    def _stop_listening(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []
        if self._resend is not None:
            self._resend.cancel()
            self._resend = None


def _light_data(raw: Any) -> dict[str, Any]:
    """The light.turn_on fields the backend may set: a brightness percent
    and an rgb colour, checked — anything else is dropped."""
    raw = raw if isinstance(raw, dict) else {}
    data: dict[str, Any] = {}
    pct = raw.get("brightness_pct")
    if isinstance(pct, int) and 0 <= pct <= 100:
        data["brightness_pct"] = pct
    rgb = raw.get("rgb_color")
    if isinstance(rgb, list) and len(rgb) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in rgb):
        data["rgb_color"] = rgb
    return data
