# AI Appliances — Home Assistant integration

Connects [Home Assistant](https://www.home-assistant.io/) to your **AI Appliances**
speaker so you can control your smart home by voice ("turn on the light in the
bathroom"). Home Assistant acts as the hub — whatever vendors you already have
behind it (LG ThinQ, Xiaomi, Tuya, …) become voice-controllable through this one
integration.

The speaker sends only the *intent* to the AI Appliances voice backend; the
backend resolves which entity you meant and this component executes the action
locally in your Home Assistant. Home Assistant's own **"expose to Assist"**
setting decides which entities the speaker can see and control.

> **Status: Phase 1 (developer preview).** The channel to the voice backend
> works: exposed lights, switches and fans can be turned on/off (and lights
> dimmed) by voice. Linking still uses a developer token — the OAuth account
> link comes in Phase 2. Not ready for general use.

## Requirements

- Home Assistant 2024.12 or newer.
- An AI Appliances speaker (see the [`ai-appliances`](https://github.com/ai-appliances)
  project).

## Installation (HACS custom repository)

1. In HACS → **Integrations** → ⋮ → **Custom repositories**.
2. Add `https://github.com/ai-appliances/homeassistant-integration` as an
   **Integration**.
3. Install **AI Appliances**, then restart Home Assistant.
4. **Settings → Devices & Services → Add Integration → AI Appliances**, and enter
   the voice-backend channel URL and your developer token.

Manual install also works: copy `custom_components/ai_appliances/` into your
Home Assistant `config/custom_components/` and restart.

## Exposing entities

Only entities you expose to voice assistants are visible to the speaker:
**Settings → Voice assistants → Expose**. Security domains (`lock`,
`alarm_control_panel`, garage `cover`) are always refused by the backend, even
if exposed — voice control of those is out of scope by design.

## Security

This component holds a link into your home. A dedicated **security audit is
planned** before an official HACS listing / any v1 release. Until then, treat
this as pre-release software. Please report anything concerning via the
[issue tracker](https://github.com/ai-appliances/homeassistant-integration/issues).

## Architecture

The full design (channel direction, tool contract, entity resolution, v1 scope)
lives in `docs/adr/0006-smart-home-via-home-assistant.md` in the private
`ai-appliances` meta-repo.

## License

[MIT](LICENSE).
