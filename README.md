# SRS Learning Bot

Status: draft

## Problem

The owner wants to learn SW/AI/ML/Data by doing retrieval practice, but the real
blocker isn't a lack of material — it's decision-paralysis and procrastination about
what to study, in what order, and giving up after a few days. The bot's job is to
remove that decision entirely: push one due question at fixed times, let the owner
self-grade, and let a real SM-2 scheduler own the "what comes back when" question.

v1 is deliberately small — hand-written cards, self-grading, no LLM — to prove the
daily habit loop actually holds before investing in content generation or automated
grading (phase 2, out of scope here).

## Goals

- A fixed daily cadence the owner can't easily skip or negotiate with.
- Real SM-2 scheduling per card, not a placeholder algorithm.
- Self-healing delivery: a missed or failed send recovers on the next check rather
  than needing manual intervention.
- An external dead-man's-switch alert if the bot goes silent, independent of Telegram.
- A codebase shaped so phase 2 (LLM-generated cards, LLM-assisted grading) is a
  drop-in swap, not a rewrite.

## Non-goals (explicitly out of scope for v1)

- LLM content generation or dedup
- LLM-graded answers
- Claim-level card decomposition
- Card versioning beyond a stable `id`
- Multi-device / multi-writer DB handling
- Job queues or precise one-shot timers
- Alerting infra beyond the heartbeat
- Source-material ingestion pipeline

## Core loop

1. **Cards** are hand-authored: one fixed question, one fixed reference answer, one
   topic tag. ~15–20 to start. No decomposition, no generation.
2. **Scheduling**: real SM-2 applied per-card. State per card: `repetitions`,
   `ease_factor` (starts at 2.5), `interval_days`, `due_date`.
3. **Delivery cadence**: 2 fixed daily slots (hardcoded local timezone), plus an
   on-demand `/card` command, plus an inactivity nudge if no answer within 48–72h.
4. **Grading**: self-report via 4 buttons — Again / Hard / Good / Easy — mapped to
   SM-2 quality 0 / 3 / 4 / 5.
5. **Reliability**: no job queue. A periodic idempotent check ("has this slot been
   sent today?") makes missed/failed sends self-healing on the next tick. Short
   retry-with-backoff on the send call itself.
6. **Observability**: ping healthchecks.io after every successful cycle. Local logs
   are for diagnosis after an alert, not for detection.

## Data model

Three sources of truth, deliberately kept apart:

- **`cards/`** — markdown files with frontmatter (`id`, `question`, `answer`,
  `topic`). Human-edited, low write frequency. `id` is a stable identity never tied
  to wording — editing a question's text in place does not reset its SRS history;
  only a genuinely different claim gets a new `id`.
- **`data.db`** (SQLite, gitignored) — machine-owned, high write frequency:
  - `cards_state(card_id, repetitions, ease_factor, interval_days, due_date, last_reviewed_at, last_quality)`
  - `daily_log(date, slot, sent_at)`
  - `bot_state(key, value)` — e.g. `last_interaction_at` for the nudge
- Source notes / ingestion pipeline — out of scope entirely, don't build.

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

## Extensibility seams for phase 2

Don't build interfaces now — just keep these isolated so phase 2 can swap the body
without touching callers:

- `grading.py`: fixed contract `grade(...) -> quality_int`.
- `card_store.py`: `get_due_cards()` / `add_card()` shape stays stable.
- `delivery.py`: all Telegram SDK calls live here only.
- The scheduler/review loop is the most stable piece and should not need to change.

## Acceptance criteria (v1 "done")

- [ ] 15–20 hand-authored cards exist in `cards/` with stable `id`s.
- [ ] Two fixed daily slots reliably deliver one due card each via Telegram.
- [ ] `/card` delivers a due (or next-due) card on demand.
- [ ] A 4-button reply (Again/Hard/Good/Easy) updates `cards_state` via real SM-2.
- [ ] A missed send (bot down during a slot) recovers automatically on the next
      periodic check, without manual replay.
- [ ] No answer within 48–72h triggers an inactivity nudge.
- [ ] A successful cycle pings healthchecks.io; a stopped bot triggers an email
      alert within the configured threshold.
- [ ] Runs continuously on the Raspberry Pi / home server target.

## Open questions

- Exact wording/count of starter cards and topic taxonomy — hand-authored separately,
  not blocking this spec.
- Exact SEND_TIMES values (owner's actual daily schedule).

## Implementation note

Per `CLAUDE.md` "Working with me": this is pair-mode work, not autonomous
implementation. Draft files (especially `sm2.py`, `scheduler.py`, `grading.py`) as a
first pass for the owner to react to and rework — don't polish straight to "done."
