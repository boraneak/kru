# 🎓 Nova - AI Live Tutor (Backend)

> Real-time AI tutor backend powered by Gemini Live API

## Tech Stack

- **Backend**: Python, FastAPI, asyncio, WebSocket
- **AI**: Google Gemini Live API
- **Auth**: Supabase
- **Deployment**: Railway, Docker

## Quick Start

```bash
# 1. Clone
git clone https://github.com/boraneak/nova-live-tutor.git
cd nova-live-tutor

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env from example
cp .env.example .env

# 5. Edit .env and add your keys
nano .env
# Required: GEMINI_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY

# 6. Load environment variables
source .env

# 7. Run backend
python3 main.py