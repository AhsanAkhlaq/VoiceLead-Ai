# VoiceLead AI 🎙️

> Real-time voice-based lead qualification for Pakistani real estate — powered by Deepgram, Groq, and Supabase.

---

<!-- 📸 IMAGE SUGGESTION #1: Place your system architecture diagram here (the 3-tier diagram showing User Interface → FastAPI Server → External Services). Export it as a PNG from the interactive diagram above. -->
![Uploading voicelead_system_architecture.svg…]()

---

## What It Does

VoiceLead AI answers inbound real estate calls, holds a natural conversation in Pakistani English, and automatically extracts structured lead data (name, budget, location, timeline) the moment the call ends. Sales agents get a scored, summarized lead in their dashboard — no manual data entry.

**Two calling channels:**
- **Browser-based**: Web UI for testing and demos (`index.html`)
- **Phone via Twilio**: Real phone calls routed through a US Twilio number

**Two-brain processing:**
- **Brain 1 (fast)**: Conversational AI running live during the call — responds in under 1 second
- **Brain 2 (deep)**: Post-call analyst that extracts structured JSON data from the full transcript

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Backend | FastAPI (Python async) | WebSocket support, non-blocking I/O |
| Speech-to-Text | Deepgram Nova-2 | Lowest latency streaming STT |
| Text-to-Speech | Deepgram Aura | Natural voice, Pakistani accent-friendly |
| LLM | Groq — LLaMA 3.3 70B | 500+ tokens/min, <1 s response |
| Database | Supabase (PostgreSQL + JSONB) | Real-time updates, easy scaling |
| Phone | Twilio | Programmable phone calls |

---

## Architecture

<!-- 📸 IMAGE SUGGESTION #2: Place the conversation flow diagram here (the 7-step sequential flowchart: Connection → Listen Loop → Process → Generate → Stream Audio → End or Continue → Post-call Analysis). -->
![Conversation Flow](./images/flow.png)

### Real-Time Conversation Flow

Every call moves through 7 stages:

1. **Connection** — Engine resets, lead record created in Supabase, greeting spoken
2. **Listen loop** — Browser/phone audio buffered and streamed to Deepgram STT
3. **Process transcript** — Current AI audio interrupted, user text forwarded to frontend
4. **Generate response** — Groq LLaMA produces reply in <1 second; `[CALL_END]` marker checked
5. **Stream audio back** — Deepgram TTS chunks buffered (16 KB first, 8 KB thereafter) and sent
6. **End or continue** — Loop repeats until `[CALL_END]` detected
7. **Post-call analysis** — Brain 2 extracts structured JSON and saves to Supabase asynchronously

### Two-Brain Architecture

<!-- 📸 IMAGE SUGGESTION #3: Place the two-brain architecture diagram here (Brain 1 left / Brain 2 right, both fed by Deepgram STT, outputting to TTS and Supabase respectively). -->
![Two-Brain Architecture](./images/two-brain.png)

**Brain 1 — Fast Conversationalist**

Lisa, a friendly Pakistani real estate agent. Runs live during the call. Temperature 0.7, max 250 tokens. Asks one question at a time. Hides scoring from the user. Ends the call when it has name, property type, location, budget, and timeline.

**Brain 2 — Deep Analyst**

Runs after the call disconnects, asynchronously. Temperature 0.1, JSON mode. Extracts 12 structured fields including `score_confidence` (0–100 buyer readiness), `sentiment`, and a 2–3 sentence professional `summary`.

---

## Performance

| Metric | Target | Achieved |
|---|---|---|
| STT latency | <1 s | ~0.5–0.8 s |
| LLM response | <2 s | ~0.5–1.0 s |
| TTS start | <1 s | ~0.3–0.5 s |
| Full turn time | <5 s | ~2–3 s |
| Call duration | Unlimited | ✅ Works |

---

## File Structure

```
voicelead-ai/
├── main.py          # FastAPI server + WebSocket handlers (360 lines)
├── engine.py        # CoreEngine: Brain 1 + Brain 2 (135 lines)
├── services.py      # STT, TTS, Supabase integrations (160 lines)
├── static/
│   ├── index.html   # Browser call UI
│   ├── dashboard.html # Leads dashboard
│   └── script.js    # Browser WebSocket client
└── .env             # API keys (not committed)
```

---

## Setup

### Prerequisites

- Python 3.10+
- A Deepgram account (API key)
- A Groq account (API key)
- A Supabase project with the `leads` table (schema below)
- (Optional) A Twilio account with a US phone number

### Install

```bash
git clone https://github.com/yourname/voicelead-ai
cd voicelead-ai
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file:

```env
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```

### Database Schema

Run this in your Supabase SQL editor:

```sql
create table leads (
  id uuid primary key default gen_random_uuid(),
  phone text not null,
  pipeline_status text default 'new',
  name text,
  property_type text,
  city text,
  area_society text,
  size_requirement text,
  budget_range text,
  timeline text,
  purpose text,
  additional_requirements text,
  score_confidence float,
  sentiment text,
  summary text,
  transcript jsonb,
  call_duration_seconds int,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
```

### Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` for the browser call UI, or `http://localhost:8000/dashboard` for the leads dashboard.

---

## Twilio Setup

1. Buy a US Twilio number
2. Set your webhook to `https://your-domain/api/twilio/twiml`
3. Twilio calls your number → TwiML redirects to `/ws/twilio` WebSocket
4. For local testing: use the reverse-call hack — your Twilio number calls your phone

> **Note on free tier**: Twilio charges $1.50–$2 per minute on free tier and does not provide Pakistani local numbers. The browser-based UI is recommended for development.

---

## Key Design Decisions

**Why Deepgram over ElevenLabs?** ElevenLabs encountered IP restrictions during development. Deepgram provides both STT and TTS with lower latency for streaming use cases.

**Why Groq over OpenAI?** Groq runs LLaMA 3.3 70B at 500+ tokens per minute — essential for <1 second real-time responses.

**Why WebSocket, not REST?** Persistent connections enable full-duplex audio streaming and interruption handling. REST cannot stream bidirectionally.

**Why two separate brains?** Brain 1 must be snappy (short responses, high temperature). Brain 2 must be precise (JSON extraction, low temperature). Conflicting requirements → separate prompts and calls.

---

## Dashboard

The dashboard at `/dashboard` shows all leads sorted by `score_confidence` (hottest first). Click any lead to view the full conversation transcript.

<!-- 📸 IMAGE SUGGESTION #4 (optional): Screenshot of the dashboard.html showing the leads table with score badges. -->

---

## License

MIT
