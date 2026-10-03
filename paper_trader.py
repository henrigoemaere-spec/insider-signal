"""paper_trader.py — Paper trading tracker for insider signals"""
import sys
import os
import sqlite3
from datetime import datetime

import insider_database as idb


# ============================================================
# Database setup
# ============================================================
def create_tables():
    con = sqlite3.connect(idb.DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            insider TEXT,
            role TEXT,
            signal_score INTEGER,
            signal_date TEXT,
            entry_date TEXT NOT NULL,
            entry_price REAL NOT NULL,
            current_price REAL,
            shares REAL,
            position_size REAL,
            pnl REAL,
            pnl_pct REAL,
            status TEXT DEFAULT 'OPEN',
            exit_date TEXT,
            exit_price REAL,
            last_updated TEXT
        )
    """)
    con.commit()
    con.close()


def connect():
    create_tables()
    return sqlite3.connect(idb.DB_PATH)


# ============================================================
# Price fetching
# ============================================================
def fetch_current_price(ticker):
    """Fetch the latest close price via yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


# ============================================================
# Core actions
# ============================================================
def add_trade(ticker, position_size=1000.0, silent=False):
    """Add a paper trade from the most recent signal for a ticker."""
    con = connect()
    ticker = ticker.upper()

    # Check if already open
    existing = con.execute(
        "SELECT id FROM paper_trades WHERE ticker = ? AND status = 'OPEN'",
        [ticker]
    ).fetchone()
    if existing:
        if not silent:
            print(f"  {ticker}: already have an open position (id={existing[0]})")
        con.close()
        return False

    # Get most recent signal for this ticker
    row = con.execute("""
        SELECT insider, role, score, date
        FROM signals
        WHERE ticker = ?
        ORDER BY date DESC, score DESC
        LIMIT 1
    """, [ticker]).fetchone()

    if not row:
        if not silent:
            print(f"  {ticker}: no signal found in database")
        con.close()
        return False

    insider, role, score, signal_date = row

    # Get current price as entry price
    price = fetch_current_price(ticker)
    if price is None or price <= 0:
        if not silent:
            print(f"  {ticker}: could not fetch price")
        con.close()
        return False

    shares = position_size / price
    now = datetime.now().isoformat()

    con.execute("""
        INSERT INTO paper_trades
        (ticker, insider, role, signal_score, signal_date, entry_date,
         entry_price, current_price, shares, position_size, pnl, pnl_pct,
         status, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'OPEN', ?)
    """, (ticker, insider, role, score, signal_date, now,
          price, price, shares, position_size, now))

    con.commit()
    con.close()

    if not silent:
        print(f"  + {ticker}: bought {shares:.2f} shares @ ${price:.2f} "
              f"(${position_size:.0f} position)")
        print(f"    Signal: {insider} ({role}), score {score}")
    return True


def auto_add(min_score=70, max_trades=5, position_size=1000.0):
    """Auto-add top signals that aren't already in the portfolio."""
    con = connect()
    rows = con.execute("""
        SELECT DISTINCT ticker, insider, role, score, date, value
        FROM signals
        WHERE score >= ?
        ORDER BY score DESC, value DESC
        LIMIT ?
    """, [min_score, max_trades * 3]).fetchall()
    con.close()

    added = 0
    for ticker, insider, role, score, date, value in rows:
        if added >= max_trades:
            break
        ok = add_trade(ticker, position_size=position_size, silent=True)
        if ok:
            print(f"  + {ticker}: {insider} ({role}), score {score}")
            added += 1

    print(f"\n  Added {added} new trades.")
    return added


def update_prices():
    """Update current prices for all open trades."""
    con = connect()
    open_trades = con.execute(
        "SELECT id, ticker, entry_price, shares, position_size "
        "FROM paper_trades WHERE status = 'OPEN'"
    ).fetchall()

    if not open_trades:
        print("  No open trades to update.")
        con.close()
        return

    print(f"  Updating {len(open_trades)} trades...\n")

    for tid, ticker, entry, shares, pos_size in open_trades:
        price = fetch_current_price(ticker)
        if price is None:
            print(f"  {ticker}: price fetch failed")
            continue

        pnl = (price - entry) * shares
        pnl_pct = ((price - entry) / entry) * 100
        now = datetime.now().isoformat()

        con.execute("""
            UPDATE paper_trades
            SET current_price = ?, pnl = ?, pnl_pct = ?, last_updated = ?
            WHERE id = ?
        """, (price, pnl, pnl_pct, now, tid))

        arrow = "+" if pnl >= 0 else ""
        print(f"  {ticker:<6} ${entry:>8.2f} -> ${price:>8.2f}  "
              f"{arrow}${pnl:>7.2f}  ({arrow}{pnl_pct:.2f}%)")

    con.commit()
    con.close()


def close_trade(trade_id):
    """Close a trade at the current market price."""
    con = connect()
    row = con.execute(
        "SELECT ticker, current_price FROM paper_trades WHERE id = ? AND status = 'OPEN'",
        [trade_id]
    ).fetchone()

    if not row:
        print(f"  Trade {trade_id} not found or already closed.")
        con.close()
        return

    ticker, current = row
    price = fetch_current_price(ticker)
    if price is None:
        price = current

    now = datetime.now().isoformat()
    con.execute("""
        UPDATE paper_trades
        SET status = 'CLOSED', exit_date = ?, exit_price = ?,
            current_price = ?, last_updated = ?
        WHERE id = ?
    """, (now, price, price, now, trade_id))
    con.commit()
    con.close()
    print(f"  Closed trade {trade_id} ({ticker}) at ${price:.2f}")


def show_portfolio():
    """Show all open trades + summary."""
    con = connect()
    rows = con.execute("""
        SELECT id, ticker, insider, role, signal_score, entry_date,
               entry_price, current_price, shares, pnl, pnl_pct
        FROM paper_trades
        WHERE status = 'OPEN'
        ORDER BY pnl DESC
    """).fetchall()

    if not rows:
        print("\n  No open trades.")
        print("  Use: python paper_trader.py auto 5")
        con.close()
        return

    print(f"\n{'='*100}")
    print(f"  PAPER TRADING PORTFOLIO")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*100}\n")
    print(f"  {'ID':<4} {'Ticker':<7} {'Insider':<20} {'Score':<6} "
          f"{'Entry':>9} {'Current':>9} {'P&L':>10} {'%':>8}")
    print(f"  {'-'*98}")

    total_value = 0
    total_cost = 0
    for tid, ticker, insider, role, score, entry_date, entry, current, shares, pnl, pnl_pct in rows:
        insider_short = (insider or "")[:18]
        cur = current if current else entry
        value = cur * shares
        cost = entry * shares
        total_value += value
        total_cost += cost
        arrow = "+" if (pnl or 0) >= 0 else ""
        print(f"  {tid:<4} {ticker:<7} {insider_short:<20} {score:<6} "
              f"${entry:>8.2f} ${cur:>8.2f} {arrow}${pnl:>8.2f} "
              f"{arrow}{(pnl_pct or 0):>6.2f}%")

    total_pnl = total_value - total_cost
    total_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    print(f"  {'-'*98}")
    print(f"  {'TOTAL':<4} {len(rows)} positions{'':<30} "
          f"{'':>10} {'':>9} {'':>10} "
          f"{'+' if total_pnl >= 0 else ''}${total_pnl:>8.2f} "
          f"{'+' if total_pct >= 0 else ''}{total_pct:>6.2f}%")
    print(f"\n  Portfolio value: ${total_value:,.2f}  (cost: ${total_cost:,.2f})")

    # Closed trades summary
    closed = con.execute("""
        SELECT ticker, entry_price, exit_price, shares, pnl, pnl_pct
        FROM paper_trades WHERE status = 'CLOSED'
        ORDER BY exit_date DESC
    """).fetchall()

    if closed:
        print(f"\n{'='*100}")
        print(f"  CLOSED TRADES ({len(closed)})")
        print(f"{'='*100}\n")
        total_closed_pnl = 0
        for ticker, entry, exit_p, shares, pnl, pnl_pct in closed:
            total_closed_pnl += pnl or 0
            arrow = "+" if (pnl or 0) >= 0 else ""
            print(f"  {ticker:<7} entry ${entry:.2f} -> exit ${exit_p:.2f}  "
                  f"{arrow}${pnl:.2f} ({arrow}{pnl_pct:.2f}%)")
        print(f"\n  Total realized P&L: {'+' if total_closed_pnl >= 0 else ''}"
              f"${total_closed_pnl:,.2f}")

    con.close()


def show_help():
    print("""
Paper Trading Commands:

  python paper_trader.py auto [N]      Auto-add top N signals (default: 5, score >= 70)
  python paper_trader.py add TICKER    Add a single trade from the latest signal
  python paper_trader.py update        Fetch current prices and update P&L
  python paper_trader.py show          Show portfolio + performance
  python paper_trader.py close ID      Close a trade at current price

Examples:
  python paper_trader.py auto 5
  python paper_trader.py add TSLA
  python paper_trader.py update
  python paper_trader.py show
""")


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        show_help()
        sys.exit(0)

    cmd = args[0].lower()

    if cmd == "auto":
        n = int(args[1]) if len(args) > 1 else 5
        auto_add(min_score=70, max_trades=n)

    elif cmd == "add" and len(args) > 1:
        add_trade(args[1])

    elif cmd == "update":
        update_prices()

    elif cmd == "show":
        show_portfolio()

    elif cmd == "close" and len(args) > 1:
        try:
            close_trade(int(args[1]))
        except ValueError:
            print("  Invalid trade ID")

    else:
        show_help()