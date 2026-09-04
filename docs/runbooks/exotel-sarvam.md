# Exotel + Sarvam Path A

Clinic OS never streams audio. Sarvam hosts STT/LLM/TTS. Exotel owns the phone number.

## Accounts
1. Exotel India (`api.in.exotel.com`), KYC, one ExoPhone, recording on.
2. Sarvam Voice Agents (indus / apps.sarvam.ai). Create agent **Receptionist**. Languages: Gujarati, Hindi, English.

Put vendor secrets in `api/.env` only (`SARVAM_API_KEY`, `EXOTEL_API_KEY`, `EXOTEL_API_TOKEN`, `EXOTEL_ACCOUNT_SID`). Never commit them. Verify with `python scripts/check_vendors.py`.

The Sarvam **model** key (`sk_…`) authenticates `api.sarvam.ai`. Voice Agents telephony (Exotel connector, inbound deploy) is configured in the Indus dashboard: Deploy → Phone Numbers → Add Connection → Exotel.

Still required from Exotel Settings → API: **Account SID** (not the API key). Paste it as `EXOTEL_ACCOUNT_SID`.

Credential check (`python scripts/check_vendors.py`):

- Sarvam **model** API (`sk_…` → `api.sarvam.ai`) works.
- These Exotel key/token values authenticate on **Singapore** `api.exotel.com`, not Mumbai `api.in.exotel.com`. If this is meant to be an India clinic line, confirm the account region in the Exotel dashboard.
- Voice Agents (Indus) still need a dashboard agent + Exotel connection; the model key cannot list orgs by itself. Copy `org_id` and `workspace_id` from the Indus URL.

**Rotate these keys.** They were pasted into chat. Generate a new Sarvam key and new Exotel API token after wiring.

## Sarvam
1. Paste `voice/receptionist/prompt.md` into the agent instructions.
2. Add HTTPS tools from `voice/receptionist/tools/*.json`. Auth: API key header `X-Tool-Key` = `TOOL_API_KEY`.
3. `on_start` → `POST /webhooks/sarvam/on-start` with caller `From` / `call_sid`. Map `name`, `language`, `patient_id`, `route` into agent variables.
4. `on_end` → `POST /webhooks/sarvam/on-end`.
5. Deploy → Phone Numbers → Add Connection → Exotel: Account SID, API Key, API Token, Base URL `api.in.exotel.com`.
6. Import ExoPhone. Inbound deployment → Receptionist agent.
7. Tunnel for local: `cloudflared tunnel` or ngrok to `http://127.0.0.1:8000`.

Voicebot applet URL:

```
https://apps.sarvam.ai/api/app-runtime/channels/exotel
```

Docs: https://docs.sarvam.ai/conversations/deploy/telephony/exotel

## Exotel App Bazaar (bot-first)
Call Start
→ Greeting / consent DTMF (1 continue, 0 reception)
→ Voicebot (Sarvam URL above), record MP3 single channel
→ Connect hunt group (reception)
→ Hangup

Status callback: `POST https://YOUR_HOST/webhooks/exotel/status` (optional header `X-Exotel-Token`).

After hours: play hours + “emergency hoy to 108 / nearest hospital”. No clinical advice.

## Kill-switch
- Console: Settings → **Humans only** (`voice_mode=human`). `on_start` returns `route=human`; agent must transfer immediately.
- If Sarvam is down: assign the ExoPhone to a second App that is Connect-only (humans). Do not wait on the bot.

## Consent (DPDP)
Spoken + stored: recording, appointment purpose, 90-day retention.
Flags: `care`, `reminders`, `marketing`. Outbound campaigns (later) require reminders consent.
Do not train models on identifiable clinical audio.

## Live test
1. `uvicorn` on 8000, Next.js on 3000, public HTTPS to API.
2. Call ExoPhone. Score against `voice/receptionist/eval/dialogues.json` (booking accuracy, not “sounds nice”).
3. Reception UI → Calls should show SID, outcome, transcript; Today should show any booked slot.
