# SRS bot — v1 implementation order

## Context

`srs-bot` is at repo-scaffold stage: `CLAUDE.md` and `.scratch/srs-bot-v1/spec.md`
fully specify the architecture, but all nine `bot/*.py` files are empty (0-byte)
stubs, `cards/` is empty, there are no git commits, and `requirements.txt` still
pins the `python-telegram-bot[job-queue]` extra even though the design explicitly
rejects a job queue. The user asked where to start implementing. This plan lays
out a concrete, dependency-ordered build sequence so they have somewhere to begin
today, rather than facing nine empty files at once.

Per `CLAUDE.md`'s "Working with me" section, this is **pair mode, not autonomous
mode**: `sm2.py`, `grading.py`, and `scheduler.py` get a full first-pass **draft**
for the user to react to and rework themselves — not polished to "done." Everything
else (config, db schema, requirements fix, main.py wiring, heartbeat) is fine to
build directly and completely.

Confirmed decisions (all recommended defaults, per user):
- **Due-card selection**: oldest `due_date` first when multiple cards are due.
- **New-card semantics**: a card with no `cards_state` row is treated as due
  immediately — no explicit enrollment step needed.
- **Testing**: add `pytest` now with a few known SM-2 reference sequences as
  regression tests for `sm2.py`.
- **Dev/dry-run**: create a second Telegram bot via @BotFather for local testing;
  swap to the real bot's credentials only at Pi-deploy time.

## Build order

1. **Fix `requirements.txt`** — `python-telegram-bot[job-queue]==21.*` →
   `python-telegram-bot==21.*`. The `[job-queue]` extra pulls in APScheduler to
   back PTB's `JobQueue`, which is exactly the job-queue CLAUDE.md says not to use.

2. **Create a test bot** via @BotFather (`/newbot`), get its token + your chat ID
   (via `getUpdates`). Fill `.env` with the test bot's credentials for all
   development; the real bot's token only goes in at Pi-deploy time.

3. **`bot/config.py`** [build directly] — load `.env`; expose
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `HEARTBEAT_URL`, a hardcoded
   `TIMEZONE` (stdlib `zoneinfo.ZoneInfo`), `SEND_TIMES` (list of `datetime.time`
   — needs your actual daily schedule, still an open value to fill in here),
   nudge threshold (pick a single value in the 48–72h range, e.g. 60h), retry
   constants (e.g. 3 attempts, 5s/15s/45s backoff — adjust to taste), and the
   `data.db` path. Raise loudly on import if a required env var is missing.
   Done when: `python -c "from bot import config; print(config.SEND_TIMES)"`
   prints real values.

4. **`bot/db.py`** [build directly] — `CREATE TABLE IF NOT EXISTS` for
   `cards_state(card_id, repetitions, ease_factor, interval_days, due_date,
   last_reviewed_at, last_quality)`, `daily_log(date, slot, sent_at)`,
   `bot_state(key, value)`. Idempotent `init_db()`, no migrations needed for a
   single-owner SQLite file. Include a small `ensure_card_state(card_id)` helper
   that inserts the initial row (repetitions=0, ease_factor=2.5, interval_days=0,
   due today) — this is what makes new-card-is-immediately-due work later.
   Done when: `init_db()` runs twice without error; `sqlite3 data.db .schema`
   shows all three tables.

5. **Author 2–3 seed cards** in `cards/` with frontmatter `id`, `question`,
   `answer`, `topic` — just enough to test `card_store.py` against real data
   before writing the full 15–20.

6. **`bot/card_store.py`** [build directly] — `get_card(id)` parses one markdown
   file via `python-frontmatter`. `get_due_cards()` returns cards whose
   `cards_state.due_date <= today` **union** cards with no state row at all
   (per the new-card-due-immediately decision). `add_card(...)` validates and
   writes a markdown file — kept thin, it's mainly the phase-2 seam.
   Done when: with the seed cards, `get_due_cards()` returns all of them; giving
   one a future `due_date` drops it from the list.

7. **`bot/sm2.py`** [DRAFT — full first pass, expect rework] — pure function
   `update_card_state(state, quality) -> new_state`. Textbook SM-2: ease-factor
   update `EF' = EF + (0.1 - (5-q)*(0.08+(5-q)*0.02))` floored at 1.3;
   quality<3 resets repetitions to 0 and interval to 1; otherwise interval
   sequence 1 → 6 → `round(interval * EF)`. I'll walk through why each term in
   the formula exists when drafting this, but stop at "draft" — this is one of
   yours to rework.

8. **`tests/test_sm2.py`** [build directly] — a handful of known SM-2 reference
   sequences (e.g. repeated "Good" ratings producing the 1→6→15-ish interval
   progression; a low-quality rating resetting the streak) as `pytest`
   regression tests. Add these *after* you've rewored the formula in step 7,
   so they check your version, not just mine.

9. **`bot/grading.py`** [DRAFT — full first pass, expect rework] — `grade(user_report)
   -> quality_int` mapping the 4 button values to `0/3/4/5`. Small, but the
   callback_data contract (e.g. `"grade:again"` vs `"again"`) is a real decision
   worth you owning since it affects delivery.py's button wiring.

10. **`bot/delivery.py`** [build directly] — `send(text, reply_markup=None)`
    wrapping PTB's `bot.send_message`; the 4-button `InlineKeyboardMarkup`; the
    `/card` command handler; the `CallbackQueryHandler` for button presses. The
    callback handler should do only SDK work (parse callback data, ack, reply)
    and hand off to an orchestration function in `scheduler.py` (e.g.
    `record_grade(card_id, user_report)`) rather than calling grading/SM2/DB
    logic inline here — otherwise "only file touching the Telegram SDK" quietly
    becomes "only file containing the grading pipeline."
    Done when: a manual `delivery.send("test")` call reaches the test bot's chat.

11. **`bot/scheduler.py`** [DRAFT — full first pass, expect rework] — the core
    loop: idempotent per-slot check against `daily_log`, due-card selection
    (oldest `due_date` first), send-with-retry via `delivery.py`, the nudge
    check against `bot_state.last_interaction_at` with a `last_nudge_sent_at`
    marker to avoid re-firing every tick, and `record_grade(...)` (grading →
    sm2 → db write). Since `requirements.txt` no longer pulls in PTB's JobQueue,
    the periodic tick should be a plain `asyncio` background task started from
    the `Application`'s `post_init` hook (`while True: await do_tick(); await
    asyncio.sleep(CHECK_INTERVAL_SECONDS)`), running alongside `run_polling()`
    so the bot can still handle `/card` and button presses concurrently.
    Done when (pre-rework, with compressed timing constants): one tick sends
    once and marks `daily_log`; a second tick in the same slot doesn't resend;
    deleting the `daily_log` row and ticking again resends (self-healing);
    backdating `last_interaction_at` triggers exactly one nudge.

12. **`bot/heartbeat.py`** [build directly] — `ping()` hits `HEARTBEAT_URL`
    (healthchecks.io), called from the end of every successful tick in
    `scheduler.py` regardless of whether a card was actually sent — it's a
    process-liveness signal, not a delivery-confirmation signal.
    Done when: a throwaway healthchecks.io check goes green after `ping()`.

13. **`bot/main.py`** [build directly] — `db.init_db()`, build the PTB
    `Application`, register `delivery.py`'s handlers, start the periodic task
    via `post_init`, call `run_polling()`.
    Done when: `python -m bot.main` starts and stays running.

14. **Author the remaining cards** to reach 15–20 total, now that the
    frontmatter shape is proven.

15. **Local dry run** (WSL2, test bot) — temporarily compress `SEND_TIMES` and
    `CHECK_INTERVAL_SECONDS` to exercise the full loop in minutes. Walk every
    line of `.scratch/srs-bot-v1/spec.md`'s acceptance criteria by hand: both
    slots deliver once each, `/card` works on demand, all 4 buttons update
    `cards_state` correctly, killing the process mid-slot and restarting it
    self-heals, the nudge fires once past threshold, healthchecks.io stays
    green. Revert the compressed constants before deploy.

16. **Pi deploy** — systemd unit (`ExecStart=.../venv/bin/python -m bot.main`,
    `Restart=on-failure`, `After=network-online.target`, non-root user); confirm
    the Pi's system timezone matches `config.py`'s `ZoneInfo`; swap `.env` to
    the real bot's credentials at this point, not before; confirm the Pi's
    clone doesn't inherit a stale `data.db` from dev; point `HEARTBEAT_URL` at
    the real (non-throwaway) check.

## Where to start today

Steps 1–4 (`requirements.txt` fix, test bot creation, `config.py`, `db.py`) have
no open decisions left and no rework expected — good to knock out first. Step 3
needs your actual `SEND_TIMES`/timezone values, which I can't fill in for you.

## Verification

Each step above has its own "done when" check — mostly manual REPL/script calls
against the test bot and a scratch `data.db`, since there's no CI yet. Step 8
(`pytest`) is the one automated check; run it after step 7's rework, and again
after any future `sm2.py` changes.
