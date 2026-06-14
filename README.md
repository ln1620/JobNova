# JobNova Take-Home Demo

Local demo for **LiveKit multi-agent mock interview** (self-intro → past experience).

Design inspired by [jobnova.ai](https://jobnova.ai/).

## Prerequisites

- Node.js 18+
- **Python 3.11+** for LiveKit agent
- Python 3.9+ for FastAPI

## 1. Configure secrets

```bash
cp .env.example .env
```

| Variable | Required for |
|----------|----------------|
| `LIVEKIT_*` | Voice interview |
| `DEEPGRAM_API_KEY` | Speech (STT + TTS) |
| `JWT_SECRET` | Login |

## 2. Install dependencies

```bash
cd services/api && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd agents/interview && python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd apps/web && npm install
```

## 3. Run

```bash
chmod +x run-all.sh
./run-all.sh
```

Open [http://localhost:3000](http://localhost:3000)

## Interview flow

1. **Take Interview** on the dashboard  
2. Listen to: *"Can you please introduce yourself?"*  
3. Press **Record** → speak → press **Done**  
4. Listen to: *"Explain about your past experiences."*  
5. Press **Record** → speak → press **Done**  
6. **End & view results**

## Project structure

```
JobNova/
├── run-all.sh
├── apps/web/
├── services/api/
└── agents/interview/
```
