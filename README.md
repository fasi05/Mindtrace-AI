# MINDTRACE AI

*Don't just correct the answer. Discover the misconception.*

A Streamlit application that diagnoses **why** a learner's algebra answer is wrong, verifies the maths symbolically, teaches the underlying idea, and tests whether it was repaired. Everything shown comes from the real AI pipeline and saved records. There is no demo mode and no simulated AI output.

## Verification status (be honest about what was tested)

| Item | Status |
|---|---|
| Automated tests (`pytest`) | **80 passed** in the build environment. AI calls in tests use a scripted test-only provider (`tests/conftest.py`); it is never imported by the app. |
| App boots with `streamlit run app.py` | Verified (health endpoint and root returned HTTP 200). All pages render under Streamlit's `AppTest` without exceptions. |
| Live AI provider calls | **Not tested.** No API key was available when this was built. The Anthropic, OpenAI and Gemini integrations are written against their official SDKs (Gemini error mapping is unit-tested with simulated SDK errors); use **Settings → Test AI connection** with your own key to confirm. |
| PostgreSQL | Code path (SQLAlchemy + `psycopg2`) is supported but **not tested against a live server**. SQLite was tested. |
| Streamlit Community Cloud deployment | **Not performed.** Follow the guide below. |

## What changed in this update (bug-fix release)

**Root causes found in the diagnosis pipeline**
1. *Unsupported question formatting made verification silently fail.* Questions written as ``Solve `2x + 3 = 11` `` (backticks/`$`) or with trailing clauses could not be parsed, so no deterministic check ran. Fixed in `extract_math`.
2. *Compact working hid wrong steps.* `2x = 14, x = 7`, `2x = 14 -> x = 7` etc. were read as one unreadable line, so errors were never compared. Statements are now split on newlines, `;`, arrows and commas.
3. *Unverifiable problems could receive an AI diagnosis.* Now they return `insufficient_evidence` with no AI call.
4. *A verified-wrong answer could be reported as "insufficient"* when the AI declined or its evidence failed grounding, which looked like "nothing happened". There is now a distinct **`incorrect`** status: wrong is established by the maths engine, a *misconception* only when grounded evidence supports it.
5. *Stale results.* An unfinished result for identical input was cached forever, and the results/mission selectors depended on option order. Now only final results (`correct`, `misconception_found`) are reused; unfinished ones are re-evaluated and updated in place (mastery counted once); selector state is reset after each new submission.
6. *Quote grounding was incomplete:* the "incorrect step" quote is now also verified against the submission.

Correctness is decided only by sympy; the AI is asked *why*, never *whether*. No database schema change, so existing databases keep working (old rows with the previous statuses load unchanged).

**UI:** light theme with a shared design system (`components/theme.py`), navy sidebar/hero, distinct states for correct / incorrect / insufficient evidence, focus outlines, responsive tweaks, `use_container_width` replaced by `width="stretch"`. Not checked in a real browser in this build; please review visually.

## Features

- **Misconception Trace Engine**: sympy checks every line of the work, the AI proposes a misconception that must quote the learner's own text (quotes that don't appear in the submission are discarded), and the result is shown with a confidence level and an explicit evidence-versus-inference split.
- **Honest refusal**: a bare wrong answer with no working returns "can't diagnose confidently, please show your steps" instead of an invented explanation. A verified-correct answer returns no misconception.
- **Deterministic maths**: correct solutions, practice answers, and transfer answers are computed by sympy, never taken from the AI. Input is whitelisted before parsing; no learner or model text is executed.
- **Repair mission**: verified practice questions (easy → hard), optional two-level hints, deterministic grading, optional AI coaching on wrong answers, and a no-hint transfer question.
- **Mastery from real attempts**: weighted estimate (diagnosis 1×, practice 1×, transfer 2×, hinted-correct 0.7 credit). A concept needs 3 attempts before it counts as assessed.
- **Pages**: Overview, Dashboard, Diagnosis workspace, Results, Repair mission, Knowledge map, Analytics, Settings.

## Project layout

```
app.py                  entry point + navigation
pages/                  one file per page
components/             state (context), ui (design system), charts (Plotly)
services/               config, ai_client, ai_providers/, math_verifier, diagnosis, practice, mastery, workflow, prompts
database/               SQLAlchemy models, session/engine, repository
models/                 Pydantic schemas, concept graph
utils/                  input validation
tests/                  pytest suite
.streamlit/             config.toml, secrets.toml.example
```

```mermaid
flowchart LR
  L[Learner] --> UI[Streamlit pages]
  UI --> WF[workflow.py]
  WF --> MV[math_verifier<br/>sympy, no eval of AI code]
  WF --> DX[diagnosis.py]
  DX --> AI[StructuredAI<br/>JSON + Pydantic + retry]
  AI --> P[Provider: Anthropic / OpenAI]
  DX --> GR[Evidence grounding<br/>+ confidence caps]
  WF --> PR[practice.py<br/>verified items]
  WF --> REPO[repository.py]
  REPO --> DB[(SQLite / PostgreSQL)]
  REPO --> MA[mastery.py]
```

## 1. Open in VS Code (Windows)

1. Unzip the project, open VS Code, **File → Open Folder…** and choose the `mindtrace` folder.
2. Open a terminal (**Terminal → New Terminal**, PowerShell).

## 2. Install

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then reopen the terminal. In VS Code, choose the `.venv` interpreter (Ctrl+Shift+P → *Python: Select Interpreter*).

## 3. Configure the AI provider

Provider access, free tiers and pricing change over time and are not guaranteed; check each provider's current pricing page.

| Provider | Variable | Default model | Get a key |
|---|---|---|---|
| Anthropic (default) | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5` | console.anthropic.com |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini` | platform.openai.com |
| Gemini | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | `gemini-2.5-flash` | aistudio.google.com |

```powershell
copy .env.example .env
notepad .env
```

Set `AI_PROVIDER` (`anthropic`, `openai` or `gemini`), the matching key, and optionally `AI_MODEL`. Model names change; if you get "model not found", set `AI_MODEL` to a model your account can use. `.env` is git-ignored. Adding a provider means writing one class in `services/ai_providers/` and registering it in `factory.py`.

Without a key the app shows configuration instructions and disables AI features. It never substitutes fake output.

**Using Gemini (PowerShell, in the project folder):**

```powershell
copy .env.example .env
notepad .env      # set  AI_PROVIDER=gemini   and   GEMINI_API_KEY=<your key>   (AI_MODEL optional)
streamlit run app.py
```

Then open **Settings → Test AI connection**. If you already store the key as `GOOGLE_API_KEY`, that name works too. If you get "model not found", set `AI_MODEL` to a Gemini model your key can use.

## 4. Run

```powershell
streamlit run app.py
```

Open http://localhost:8501. Try **Diagnosis workspace → Load sample input** (fills `2x + 3 = 11` with `2x = 14`, `x = 7`), then **Analyse my work**.

Run tests: `python -m pytest -q`

## 5. Upload to GitHub

```powershell
git init
git add .
git status        # confirm .env and secrets.toml are NOT listed
git commit -m "MindTrace AI"
git branch -M main
git remote add origin https://github.com/<you>/mindtrace-ai.git
git push -u origin main
```

Create the empty repository on github.com first. Never commit real keys; rotate any key that was ever committed.

## 6. Deploy to Streamlit Community Cloud

1. Go to share.streamlit.io, sign in with GitHub, **Create app**.
2. Pick the repository, branch `main`, main file `app.py`. Python 3.11+ recommended (Advanced settings).
3. Open **Advanced settings → Secrets** and paste (see `.streamlit/secrets.toml.example`):

```toml
AI_PROVIDER = "anthropic"
ANTHROPIC_API_KEY = "your-key"
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"
```

4. Deploy. Then open **Settings** in the app and press **Test AI connection**.

## 7. Persistent PostgreSQL (needed for real multi-user data)

Streamlit Community Cloud's local disk is not durable: a SQLite file can be lost when the app restarts or redeploys. Provision any hosted PostgreSQL (e.g. Neon, Supabase, Railway, Render), copy its connection string into `DATABASE_URL` (`postgres://` and `postgresql://` are both accepted), and redeploy. Tables are created automatically on first start (`Base.metadata.create_all`, with a `schema_info` version row). There is no Alembic migration history yet: schema changes after launch need a manual migration or a new table. Nothing is provisioned by this project; you create and own the database.

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| "AI is not configured" | Set the key variable for the chosen `AI_PROVIDER`; restart the app. |
| "API key was rejected" | Key is wrong, revoked, or for the other provider. |
| "rate limit" / quota | Wait and press Retry; check provider billing and limits. |
| "model not found" | Set `AI_MODEL` to a model available to your account. |
| "timed out" | Raise `AI_TIMEOUT_SECONDS`. |
| "did not pass validation" | The model returned malformed JSON twice; Retry, or use a stronger model. |
| Progress vanished on cloud | You are on SQLite. Configure PostgreSQL via `DATABASE_URL`. |
| `psycopg2` install error | Use Python 3.11-3.13 and `pip install --upgrade pip`. |
| `ModuleNotFoundError` | Activate `.venv` and re-run `pip install -r requirements.txt`. |
| Learner data "reset" | Progress is keyed to an anonymous code kept in the URL (`?learner=`) and the session. Copy it from **Settings** and use **Resume with an existing code**. |

## Security, privacy, and limitations

- Keys live only in environment variables or Streamlit secrets and are never rendered, logged, or stored in the database.
- All SQL goes through SQLAlchemy (parameterised). Input lengths are limited and control characters stripped. Logging records error types only, not learner text.
- **There is no authentication.** A learner is an anonymous random code; anyone with the code can see that data. Do not treat this as a multi-user account system.
- Learner questions and answers are sent to the configured AI provider and stored in your database. No retention policy is enforced; users can delete their own data in **Settings**.
- Only algebra (single-variable equations and expression simplification) is machine-verified. Other problem types are flagged as unverified and capped at low confidence. Expression "simplified" checks rely on sympy's automatic evaluation and may accept a restated original.
- Misconceptions are hypotheses. No claim of improved learning outcomes is made; that would need a proper evaluation.
