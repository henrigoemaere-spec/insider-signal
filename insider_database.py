"""insider_database.py — SQLite storage for insider signals"""
import os
import sqlite3
import pandas as pd
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "data", "insider.db")


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def create_tables():
    con = connect()
    con.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            company TEXT,
            insider TEXT NOT NULL,
            role TEXT,
            date TEXT NOT NULL,
            value REAL,
            shares REAL,
            price REAL,
            pct_holding REAL,
            n_transactions INTEGER,
            cluster INTEGER,
            score INTEGER,
            reasons TEXT,
            first_seen TEXT,
            UNIQUE(ticker, insider, date)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            n_signals INTEGER,
            n_tickers INTEGER
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_signals_score ON signals(score)")
    con.commit()
    con.close()


def save_signals(signals):
    if not signals:
        return 0
    create_tables()
    con = connect()
    added = 0
    now = datetime.now().isoformat()
    for s in signals:
        try:
            con.execute("""
                INSERT OR IGNORE INTO signals
                (ticker, company, insider, role, date, value, shares, price,
                 pct_holding, n_transactions, cluster, score, reasons, first_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s.get("ticker", ""),
                s.get("company", ""),
                s.get("insider", ""),
                s.get("role", ""),
                s.get("date", ""),
                s.get("value", 0),
                s.get("shares", 0),
                s.get("price", 0),
                s.get("pct_holding", 0),
                s.get("n_transactions", 0),
                s.get("cluster", 0),
                s.get("score", 0),
                " | ".join(s.get("reasons", [])),
                now,
            ))
            if con.total_changes > added:
                added += 1
        except Exception:
            continue
    con.commit()
    con.close()
    return added


def save_scan(n_signals, n_tickers):
    create_tables()
    con = connect()
    con.execute("""
        INSERT INTO scans (date, n_signals, n_tickers)
        VALUES (?, ?, ?)
    """, (datetime.now().isoformat(), n_signals, n_tickers))
    con.commit()
    con.close()


def get_all_signals(limit=None, min_score=0):
    create_tables()
    con = connect()
    query = "SELECT * FROM signals WHERE score >= ? ORDER BY date DESC, score DESC"
    if limit:
        query += f" LIMIT {int(limit)}"
    df = pd.read_sql_query(query, con, params=[min_score])
    con.close()
    return df


def get_signals_by_ticker(ticker):
    create_tables()
    con = connect()
    df = pd.read_sql_query(
        "SELECT * FROM signals WHERE ticker = ? ORDER BY date DESC",
        con, params=[ticker.upper()]
    )
    con.close()
    return df


def search_insider(name):
    create_tables()
    con = connect()
    df = pd.read_sql_query(
        "SELECT * FROM signals WHERE insider LIKE ? ORDER BY date DESC",
        con, params=[f"%{name}%"]
    )
    con.close()
    return df


def statistics():
    create_tables()
    con = connect()
    total = con.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    per_ticker = pd.read_sql_query("""
        SELECT ticker, COUNT(*) AS count, AVG(score) AS avg_score,
               SUM(value) AS total_value, MAX(date) AS latest
        FROM signals
        GROUP BY ticker
        ORDER BY count DESC
    """, con)
    recent = pd.read_sql_query("""
        SELECT * FROM signals
        ORDER BY first_seen DESC
        LIMIT 10
    """, con)
    last_scan = con.execute(
        "SELECT date FROM scans ORDER BY date DESC LIMIT 1"
    ).fetchone()
    con.close()
    return {
        "total_signals": total,
        "per_ticker": per_ticker,
        "recent": recent,
        "last_scan": last_scan[0] if last_scan else None,
    }


if __name__ == "__main__":
    create_tables()
    print(f"Database: {DB_PATH}")
    stats = statistics()
    print(f"Total signals: {stats['total_signals']}")
    print(f"Last scan: {stats['last_scan']}")
    if not stats["per_ticker"].empty:
        print("\nPer ticker:")
        print(stats["per_ticker"].to_string(index=False))