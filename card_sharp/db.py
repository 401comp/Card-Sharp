import sqlite3
from pathlib import Path
from datetime import datetime
from .prefs import app_support_dir


DB_PATH = app_support_dir() / "card_sharp.sqlite"


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    preset_name TEXT NOT NULL,
    starting_bankroll INTEGER NOT NULL,
    ending_bankroll INTEGER,
    hands_played INTEGER DEFAULT 0,
    correct_moves INTEGER DEFAULT 0,
    total_moves INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    played_at TEXT NOT NULL,
    bet INTEGER NOT NULL,
    dealer_up TEXT NOT NULL,
    dealer_final TEXT NOT NULL,
    player_final TEXT NOT NULL,
    outcome TEXT NOT NULL,
    payout INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_id INTEGER NOT NULL,
    step INTEGER NOT NULL,
    player_cards TEXT NOT NULL,
    dealer_up TEXT NOT NULL,
    player_action TEXT NOT NULL,
    correct_action TEXT NOT NULL,
    was_correct INTEGER NOT NULL,
    FOREIGN KEY (hand_id) REFERENCES hands(id)
);

CREATE TABLE IF NOT EXISTS drill_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at TEXT NOT NULL,
    drill TEXT NOT NULL,          -- 'hard', 'soft', 'splits', 'doubles', 'surrender', 'mixed'
    preset_name TEXT NOT NULL,
    player_cards TEXT NOT NULL,
    dealer_up TEXT NOT NULL,
    player_action TEXT NOT NULL,
    correct_action TEXT NOT NULL,
    was_correct INTEGER NOT NULL,
    category TEXT NOT NULL         -- 'hard', 'soft', 'pair'
);

CREATE INDEX IF NOT EXISTS idx_drill_attempts_drill ON drill_attempts(drill);
CREATE INDEX IF NOT EXISTS idx_drill_attempts_correct ON drill_attempts(was_correct);
CREATE INDEX IF NOT EXISTS idx_decisions_correct ON decisions(was_correct);

CREATE TABLE IF NOT EXISTS deviation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at TEXT NOT NULL,
    hand_key TEXT NOT NULL,          -- e.g. "hard_8", "soft_18", "pair_8"
    upcard TEXT NOT NULL,            -- "2".."9","T","A"
    chosen_action TEXT NOT NULL,     -- your deviation action code
    bs_action TEXT NOT NULL,         -- what BS would have said
    hand_outcome TEXT NOT NULL,      -- 'win','lose','push','blackjack','surrender'
    hand_payout INTEGER NOT NULL     -- net $ for the hand
);

CREATE INDEX IF NOT EXISTS idx_deviation_events_key ON deviation_events(hand_key, upcard);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA)
    return conn


def start_session(preset_name: str, bankroll: int) -> int:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO sessions (started_at, preset_name, starting_bankroll) VALUES (?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), preset_name, bankroll),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def end_session(session_id: int, bankroll: int, hands: int, correct: int, total: int):
    conn = connect()
    conn.execute(
        "UPDATE sessions SET ending_bankroll=?, hands_played=?, correct_moves=?, total_moves=? WHERE id=?",
        (bankroll, hands, correct, total, session_id),
    )
    conn.commit()
    conn.close()


def log_hand(session_id: int, bet: int, dealer_up: str, dealer_final: str,
             player_final: str, outcome: str, payout: int) -> int:
    conn = connect()
    cur = conn.execute(
        """INSERT INTO hands (session_id, played_at, bet, dealer_up, dealer_final, player_final, outcome, payout)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, datetime.now().isoformat(timespec="seconds"), bet, dealer_up,
         dealer_final, player_final, outcome, payout),
    )
    conn.commit()
    hid = cur.lastrowid
    conn.close()
    return hid


def log_decision(hand_id: int, step: int, player_cards: str, dealer_up: str,
                 player_action: str, correct_action: str):
    conn = connect()
    conn.execute(
        """INSERT INTO decisions (hand_id, step, player_cards, dealer_up, player_action, correct_action, was_correct)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (hand_id, step, player_cards, dealer_up, player_action, correct_action,
         1 if player_action == correct_action else 0),
    )
    conn.commit()
    conn.close()


def log_drill_attempt(drill: str, preset_name: str, player_cards: str, dealer_up: str,
                       player_action: str, correct_action: str, category: str):
    conn = connect()
    conn.execute(
        """INSERT INTO drill_attempts
             (played_at, drill, preset_name, player_cards, dealer_up,
              player_action, correct_action, was_correct, category)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(timespec="seconds"), drill, preset_name,
         player_cards, dealer_up, player_action, correct_action,
         1 if player_action == correct_action else 0, category),
    )
    conn.commit()
    conn.close()


def log_deviation_event(hand_key: str, upcard: str, chosen_action: str,
                         bs_action: str, hand_outcome: str, hand_payout: int):
    conn = connect()
    conn.execute(
        """INSERT INTO deviation_events
             (played_at, hand_key, upcard, chosen_action, bs_action, hand_outcome, hand_payout)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(timespec="seconds"),
         hand_key, upcard, chosen_action, bs_action, hand_outcome, hand_payout),
    )
    conn.commit()
    conn.close()


def deviation_stats() -> list[dict]:
    """Aggregate per-deviation stats: uses, W/L/P counts, net $ across affected hands."""
    conn = connect()
    rows = conn.execute(
        """SELECT hand_key, upcard, chosen_action, bs_action,
                  COUNT(*) as uses,
                  SUM(CASE WHEN hand_outcome IN ('win','blackjack') THEN 1 ELSE 0 END) AS wins,
                  SUM(CASE WHEN hand_outcome IN ('lose','surrender') THEN 1 ELSE 0 END) AS losses,
                  SUM(CASE WHEN hand_outcome = 'push' THEN 1 ELSE 0 END) AS pushes,
                  SUM(hand_payout) AS net
             FROM deviation_events
             GROUP BY hand_key, upcard, chosen_action, bs_action
             ORDER BY uses DESC"""
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        uses = r[4] or 0
        net = r[8] or 0
        out.append({
            "hand_key": r[0], "upcard": r[1],
            "chosen_action": r[2], "bs_action": r[3],
            "uses": uses,
            "wins": r[5] or 0, "losses": r[6] or 0, "pushes": r[7] or 0,
            "net": net,
            "avg": (net / uses) if uses else 0.0,
        })
    return out


def stats_overview() -> dict:
    """All-time counts across simulated play and drills."""
    conn = connect()
    d = conn.execute("SELECT COUNT(*), SUM(was_correct) FROM decisions").fetchone()
    dr = conn.execute("SELECT COUNT(*), SUM(was_correct) FROM drill_attempts").fetchone()
    total = (d[0] or 0) + (dr[0] or 0)
    correct = (d[1] or 0) + (dr[1] or 0)
    conn.close()
    return {
        "play_decisions": d[0] or 0,
        "play_correct": d[1] or 0,
        "drill_attempts": dr[0] or 0,
        "drill_correct": dr[1] or 0,
        "total_decisions": total,
        "total_correct": correct,
        "overall_accuracy": (correct / total * 100.0) if total else 0.0,
    }


def stats_by_drill() -> list[dict]:
    conn = connect()
    rows = conn.execute(
        """SELECT drill, COUNT(*), SUM(was_correct)
             FROM drill_attempts GROUP BY drill ORDER BY drill"""
    ).fetchall()
    conn.close()
    return [
        {"drill": r[0], "attempts": r[1], "correct": r[2] or 0,
         "accuracy": ((r[2] or 0) / r[1] * 100.0) if r[1] else 0.0}
        for r in rows
    ]


def stats_by_category() -> list[dict]:
    conn = connect()
    rows = conn.execute(
        """SELECT category, COUNT(*), SUM(was_correct)
             FROM drill_attempts GROUP BY category ORDER BY category"""
    ).fetchall()
    conn.close()
    return [
        {"category": r[0], "attempts": r[1], "correct": r[2] or 0,
         "accuracy": ((r[2] or 0) / r[1] * 100.0) if r[1] else 0.0}
        for r in rows
    ]


def top_mistakes(limit: int = 10) -> list[dict]:
    """Most-repeated wrong situations across drills + play."""
    conn = connect()
    rows = conn.execute(
        """SELECT player_cards, dealer_up, player_action, correct_action, COUNT(*) as cnt
             FROM (
               SELECT player_cards, dealer_up, player_action, correct_action FROM drill_attempts WHERE was_correct = 0
               UNION ALL
               SELECT player_cards, dealer_up, player_action, correct_action FROM decisions WHERE was_correct = 0
             )
             GROUP BY player_cards, dealer_up, player_action, correct_action
             ORDER BY cnt DESC
             LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {"player_cards": r[0], "dealer_up": r[1],
         "player_action": r[2], "correct_action": r[3], "count": r[4]}
        for r in rows
    ]


def recent_sessions(limit: int = 12) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        """SELECT started_at, preset_name, hands_played, correct_moves, total_moves,
                  starting_bankroll, ending_bankroll
             FROM sessions ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        acc = ((r[3] or 0) / r[4] * 100.0) if r[4] else 0.0
        delta = (r[6] - r[5]) if r[6] is not None else None
        out.append({
            "started_at": r[0], "preset": r[1], "hands": r[2] or 0,
            "correct": r[3] or 0, "total": r[4] or 0, "accuracy": acc,
            "start_bankroll": r[5], "end_bankroll": r[6], "delta": delta,
        })
    return out


def session_stats(session_id: int) -> dict:
    conn = connect()
    row = conn.execute(
        "SELECT hands_played, correct_moves, total_moves, ending_bankroll FROM sessions WHERE id=?",
        (session_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {}
    return {
        "hands_played": row[0] or 0,
        "correct_moves": row[1] or 0,
        "total_moves": row[2] or 0,
        "ending_bankroll": row[3],
    }
