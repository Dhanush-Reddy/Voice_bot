# Voice Bot Troubleshooting & Deployment Knowledge Base

This document serves as a comprehensive knowledge base detailing the various errors encountered during the deployment and configuration of the Voice Bot backend to Google Cloud Run, along with their respective causes and resolutions.

---

## 1. Cloud Run Deployment Failure: Port Mismatch
**Error:**
```
Container failed to start and listen on the port defined provided by the PORT=8080 environment variable within the allocated timeout.
```
**Cause:**
Google Cloud Run automatically sets a `PORT` environment variable (default `8080`) and expects the container to listen on it. The Dockerfile exposed port `8000`, and the application bindings were mismatched.
**Resolution:**
Updated the `uvicorn.run()` logic in `backend/api/server.py` to use `int(os.getenv("PORT", 8080))` instead of hardcoding the port.

---

## 2. Missing Python Dependencies (`ModuleNotFoundError`)
**Error:**
```
ModuleNotFoundError: No module named 'sqlalchemy'
```
**Cause:**
The application code used `sqlalchemy.ext.asyncio` and `aiosqlite` for its database models, but these packages weren't listed in the backend's `requirements.txt`.
**Resolution:**
Added `sqlalchemy[asyncio]>=2.0.0` and `aiosqlite>=0.20.0` to `backend/requirements.txt`.

---

## 3. GitHub Push Protection Block (Exposed Secrets)
**Error:**
```
remote: error: GH013: Repository rule violations found for refs/heads/main.
remote: - Google Service Account Credentials found in `service.yaml`
```
**Cause:**
Actual sensitive access tokens (LiveKit API key & Secret, Google Service Account JSON, Gemini API Key) were hardcoded inside the `env` section of `service.yaml`. GitHub's advanced secret scanning automatically blocks pushes containing potential security risks.
**Resolution:**
Scrubbed the real secrets from `service.yaml`, replacing them with placeholder strings (e.g., `"{}"` and `"API..."`). We then amended the git commit, allowing the code to be safely pushed. Moving forward, secrets should be injected via Cloud Run's Secrets Manager or Variables UI.

---

## 4. Uninitialized Database Config (`AttributeError`)
**Error:**
```
AttributeError: 'Settings' object has no attribute 'database_url'
```
**Cause:**
The application's dependency injection was trying to create a SQLAlchemy engine using `settings.database_url`, but the `database_url` attribute was never defined in the `__init__` method of the `Settings` class (`backend/core/config.py`).
**Resolution:**
Added the missing configuration line to `Settings`:
`self.database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./voice_bot.db")`

---

## 5. Missing Route Imports (`NameError`)
**Error:**
```
NameError: name 'ConfigOptionsResponse' is not defined
```
**Cause:**
The route handler in `backend/api/routes.py` utilized several objects—`ConfigOptionsResponse`, `VOICE_OPTIONS`, `MODEL_OPTIONS`, `LANGUAGE_OPTIONS`—that were not imported at the top of the file, causing a crash upon startup payload evaluation.
**Resolution:**
Imported the relevant references from `models/options.py` and `core/options.py` into `api/routes.py`.

---

## 6. Missing Core Library Import (`NameError: name 'asyncio'`)
**Error:**
```
NameError: name 'asyncio' is not defined. Did you forget to import 'asyncio'
```
**Cause:**
Inside the `lifespan` startup hook in `api/routes.py`, the system was attempting to schedule the agent pool using `asyncio.create_task()`, but the standard `asyncio` library wasn't imported.
**Resolution:**
Added `import asyncio` to `api/routes.py`.

---

## 7. Frontend Missing Assets and Extension Warnings
**Error:**
```
/favicon.ico:1 Failed to load resource: the server responded with a status of 404 ()
Unchecked runtime.lastError: Could not establish connection. Receiving end does not exist.
```
**Cause:**
The `Unchecked runtime.lastError` warning is caused by a third-party browser extension trying to communicate with a page script that isn't loaded; it has no effect on the web app. The `404` was due to the absence of a `favicon.ico` document in the frontend's `public` directory.
**Resolution:**
Generated a standard `favicon.ico` in the `frontend/public/` folder using a base64 string to resolve the 404 network request error.

---

## 8. Agent Worker Crash: Missing Voice Settings
**Error:**
```
AttributeError: 'Settings' object has no attribute 'default_bot_voice'
```
**Cause:**
After the backend properly initialized, whenever a user connected to a LiveKit room, Pipecat would spawn a new bot worker. The worker's `bot/pipeline.py` script attempted to use `settings.default_bot_voice`, which was completely missing from `core/config.py`.
**Resolution:**
Added the missing bot agent parameters to `core/config.py`:
- `self.default_bot_voice: str = os.getenv("DEFAULT_BOT_VOICE", "Aoede")`
- `self.default_bot_model: str = os.getenv("DEFAULT_BOT_MODEL", "gemini-2.0-flash-live-001")`

---

## 9. Agent Worker Crash: Unauthenticated LLM Service
**Error:**
```
❌ Worker crashed (attempt 3/3): No Gemini credentials found. Set GEMINI_API_KEY (local dev) or GOOGLE_APPLICATION_CREDENTIALS_JSON (production).
```
**Cause:**
The agents were failing to connect to the Google Live API. Due to step #3 above, we had to strip out the API keys and credentials from `service.yaml`. Thus, the LiveKit worker subprocess environment had no valid keys.
**Resolution:**
The application acts predictably and terminates the agent. Real API credentials (`GEMINI_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS_JSON`) must be injected into the application securely directly via the variables settings panel on the Cloud Run Deployment interface.

---

## 10. Frontend Connection Hang: "waiting for AI agent"
**Error:**
```
The browser UI indefinitely shows: "waiting for AI agent"
```
**Cause:**
This is the frontend manifestation of the missing API keys (Error #9). The backend successfully deployed and is running, and the user successfully connected to the LiveKit room, but the backend's Pipecat worker crashed upon startup because `GEMINI_API_KEY` or `GOOGLE_APPLICATION_CREDENTIALS_JSON` was missing from the deployed Cloud Run environment variables. Since the worker died, the AI agent never actually entered the LiveKit room to greet the user.
**Resolution:**
Do not commit raw API keys to GitHub or `service.yaml`. Instead:
1. Navigate to the Google Cloud Run Console for the `voice-bot` service.
2. Click **Edit & Deploy New Revision**.
3. Under the **Variables & Secrets** tab, manually add the `GEMINI_API_KEY` and `GOOGLE_APPLICATION_CREDENTIALS_JSON` variables.
4. Click **Deploy**. The agent will spawn correctly on the next call.
