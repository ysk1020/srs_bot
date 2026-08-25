# SRS Learning Bot

## What this is

A personal Telegram bot that fights procrastination/decision-paralysis around learning
SW, AI/ML, and Data topics by using **retrieval practice** (spaced repetition). The real
problem it solves isn't lack of material — it's that the owner gets distracted and
anxious about what to study, in what order, and gives up. The bot removes that decision:
it proactively pushes one due question at fixed times per day, the owner answers and
self-reports correct/incorrect, and a real SM-2 scheduler decides when that question
comes back.

This is **v1 of a two-phase plan**. v1 is a plain SRS with hand-written content and
self-grading — deliberately small, to prove the daily habit loop works. Phase 2 (later,
not now) adds an LLM layer: auto-generated questions and LLM-assisted grading. v1's job
is to make phase 2 a drop-in swap later, not a rewrite — see "Extensibility seams" below.

## Stack & deployment

Python, `python-telegram-bot`, SQLite (stdlib `sqlite3`), `python-frontmatter`,
`python-dotenv`. Runs continuously on a Raspberry Pi / home server as the delivery host.
Development happens in this WSL2 (Ubuntu-22.04) environment specifically because it
mirrors that Linux deployment target.

## Core loop

1. **Cards** are hand-authored: one fixed question + one fixed reference answer + a topic
   tag, written upfront (~15–20 to start). No decomposition into atomic claims, no LLM
   generation — both deferred until hand-authoring is an actual bottleneck.
2. **Scheduling**: real SM-2, applied per-card (not decomposed sub-claims). Per card:
   `repetitions`, `ease_factor` (starts 2.5), `interval_days`, `due_date`.
3. **Delivery cadence**: **2 fixed daily slots** (hardcoded local timezone) + an on-demand
   `/card` command ("I'm bored, give me one now") + an inactivity nudge if no answer
   within **48–72h**.
4. **Grading**: self-report via a **4-button rating** — Again / Hard / Good / Easy (Anki's
   own scheme), not binary. Maps to SM-2 quality: Again→0, Hard→3, Good→4, Easy→5, so the
   real SM-2 formula gets actual signal instead of a made-up 2-value stand-in. Still
   self-report, still no LLM — one tap with 4 options instead of 2.
5. **Reliability**: no job queue, no precise one-shot timers. A periodic idempotent check
   ("has this slot been sent today?") makes missed/failed sends self-healing on the
   next tick, plus short retry-with-backoff on the send call itself.
6. **Observability**: a dead-man's-switch heartbeat (healthchecks.io) pinged after every
   successful cycle — it emails (a channel independent of Telegram) if a ping doesn't
   arrive within a threshold. Local logs are for diagnosis after that alert, not detection.

## Data model — three sources of truth, deliberately kept apart

- **`cards/`** — markdown files with frontmatter (`id`, `question`, `answer`, `topic`).
  Human-edited, low write frequency. `id` is a stable identity never tied to wording —
  editing a question's text in place does not reset its SRS history; only a genuinely
  different claim gets a new `id`.
- **`data.db`** (SQLite, gitignored) — machine-owned, high write frequency:
  `cards_state(card_id, repetitions, ease_factor, interval_days, due_date,
  last_reviewed_at, last_quality)`, `daily_log(date, slot, sent_at)`, `bot_state(key,
  value)` (e.g. `last_interaction_at` for the nudge).
- Source notes / ingestion pipeline — out of scope for v1 entirely, don't build.

## File layout

```
bot/
├── config.py       # timezone, SEND_TIMES, tokens — loaded from .env
├── card_store.py   # get_card(id), get_due_cards(), add_card() — swappable content seam
├── db.py           # SQLite connection + schema
├── sm2.py          # pure function: update_card_state(state, quality) -> new_state
├── grading.py      # grade(user_report) -> quality int — swappable grading seam
├── delivery.py     # send(text), handlers — swappable delivery seam, only file touching the Telegram SDK
├── scheduler.py    # core loop: idempotent check, due-card selection, nudge, retry
├── heartbeat.py    # ping healthchecks.io after a successful cycle
└── main.py         # entrypoint
```

## Extensibility seams for phase 2 (don't build interfaces now — just keep these isolated)

- `grading.py`: fixed contract `grade(...) -> quality_int`. v1 = 4-button self-report
  (Again/Hard/Good/Easy → 0/3/4/5); phase 2 swaps the body for an LLM call without
  touching callers.
- `card_store.py`: `get_due_cards()` / `add_card()`. Phase 2's LLM-generated cards just
  need to produce the same shape and call `add_card()`.
- `delivery.py`: all Telegram SDK calls live here only — nothing else talks to Telegram
  directly.
- The scheduler/review loop is the most stable piece and should not need to change in
  phase 2.

## Explicitly out of scope for v1 — do not build unless asked

LLM content generation/dedup, LLM-graded answers, claim-level card decomposition, card
versioning beyond a stable `id`, multi-device/multi-writer DB handling, job queues,
alerting infra beyond the heartbeat, source-material ingestion pipeline.

## Agent skills

### Issue tracker

Issues live as markdown files under `.scratch/<feature-slug>/` in this repo. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context layout: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Working with me

I'm building this project specifically to *learn* SW/AI/ML/Data by doing — not just to
have a working bot. Keep that in mind for implementation work:

- **Pair mode, not autonomous mode.** Draft a full first-pass implementation of a file so
  I have something concrete to react to — but expect me to rewrite/rework the core logic
  myself afterward (e.g. the actual SM-2 update math, the scheduling checks), not just
  accept your draft as final. Don't polish drafts into "done" on your own; leave room for
  me to actually engage with the meaningful parts.
- Explaining *why* something works (like the SM-2 formula walkthrough) is genuinely useful
  — keep doing that, don't just hand over code silently.
- This applies to implementation code specifically. Repo scaffolding, config boilerplate,
  and docs are fine for you to just handle directly.

## Run

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, HEARTBEAT_URL
python -m bot.main
```
