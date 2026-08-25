# SQLite connection + schema.
#
# This file owns the machine-written state (data.db, gitignored) that's kept
# deliberately separate from the human-authored cards/ markdown. Three tables:
#
#   cards_state(card_id, repetitions, ease_factor, interval_days, due_date,
#               last_reviewed_at, last_quality)
#   daily_log(date, slot, sent_at)
#   bot_state(key, value)


import sqlite3
import bot.config as config


def get_connection():
    # Opens a connection to DB_PATH via sqlite3.connect
    con = sqlite3.connect(config.DB_PATH)
    # Row so query results can be accessed by
    # column name (row["card_id"]) instead of positional index - makes the
    # rest of the codebase (card_store.py, scheduler.py) much easier to read.
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = get_connection()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS cards_state (
        card_id TEXT PRIMARY KEY,
        repetitions INTEGER NOT NULL,
        ease_factor REAL NOT NULL,
        interval_days INTEGER NOT NULL,
        due_date TEXT NOT NULL,
        last_reviewed_at TEXT,
        last_quality INTEGER
    );
    CREATE TABLE IF NOT EXISTS daily_log (
        date TEXT NOT NULL,
        slot TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        PRIMARY KEY (date, slot)
    );
    create table if not exists bot_state (
        key text primary key,
        value text not null 
    );
    """)
    con.commit()
    con.close()

def ensure_card_state(card_id: str):
    con = get_connection()
    con.execute(
        "INSERT OR IGNORE INTO cards_state (card_id, repetitions, ease_factor, interval_days, due_date) "
        "VALUES (?, 0, 2.5, 0, date('now'))",
        (card_id,)
    )
    con.commit()
    con.close()
# ensure_card_state(card_id):
#   - Get a connection.
#   - INSERT OR IGNORE a fresh cards_state row for this card_id: repetitions
#     0, ease_factor 2.5 (SM-2's documented starting value), interval_days 0,
#     due_date today (use Python's date.today().isoformat() so it matches the
#     TEXT column format). OR IGNORE is what makes this safe to call
#     unconditionally - it's a no-op if the card already has a row.
#   - This is what makes "a card with no state row is due immediately" work:
#     card_store.py can call this the first time it sees a card, and from
#     then on the row already exists.
#   - Commit, close.
