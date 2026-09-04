# Clinic OS (Voice MVP, Path A)

Clinic management software with a phone-first front door. **FastAPI + SQLite + Next.js**. Telephony is **Exotel → Sarvam Voice Agents**. This repo does not stream PCM.

## Layout

| Path | Role |
|---|---|
| `api/` | Patients, slots, appointments, staff JWT, Sarvam tools, Exotel/Sarvam webhooks |
| `web/` | Reception console |
| `voice/receptionist/` | Prompt, lexicon, HTTPS tool specs, eval dialogues |
| `docs/runbooks/exotel-sarvam.md` | Dashboard wiring + kill-switch |

## Run

```powershell
cd api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

```powershell
cd web
npm install
npm run dev
```

Sign in: `reception@adajan.clinic` / `changeme`

Seed: Adajan Family Clinic, Surat; Dr. Meera Shah (GP), Dr. Rohan Patel (dental).

Tests: `cd api; pytest -q`

## Tools

Auth header `X-Tool-Key`. Book only `slot_id` from `get_availability` (max 3). Times are speakable (`shaame na paanch vaagy`), not `17:00`.
