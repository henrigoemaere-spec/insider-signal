"""insider_tracker.py — View history and stats of insider signals"""
import sys
from datetime import datetime

import insider_database as idb


def show_overview():
    stats = idb.statistics()

    print(f"\n{'='*80}")
    print(f"  INSIDER SIGNALS — OVERVIEW")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*80}\n")

    print(f"  Total signals in database:  {stats['total_signals']}")
    print(f"  Last scan:                  {stats['last_scan'] or 'never'}")

    if stats["per_ticker"].empty:
        print("\n  No signals yet. Run `python insider_scanner.py` first.\n")
        return

    print(f"\n{'='*80}")
    print(f"  PER TICKER")
    print(f"{'='*80}\n")
    print(f"  {'Ticker':<8} {'#':>4} {'Avg score':>12} {'Total value':>18} {'Latest':<12}")
    print(f"  {'-'*76}")
    for _, r in stats["per_ticker"].iterrows():
        print(f"  {r['ticker']:<8} {r['count']:>4} {r['avg_score']:>12.1f} "
              f"${r['total_value']:>16,.0f} {r['latest']:<12}")


def show_top_signals(min_score=50, limit=20):
    df = idb.get_all_signals(limit=limit, min_score=min_score)

    print(f"\n{'='*100}")
    print(f"  TOP SIGNALS (score >= {min_score})")
    print(f"{'='*100}\n")

    if df.empty:
        print(f"  No signals with score >= {min_score}.\n")
        return

    print(f"  {'Score':<7} {'Ticker':<7} {'Insider':<22} {'Role':<18} {'Value':>13} {'Date':<12} {'Reasons'}")
    print(f"  {'-'*98}")
    for _, r in df.iterrows():
        insider = str(r["insider"])[:20]
        role = str(r["role"])[:16]
        print(f"  {r['score']:>3}/100 {r['ticker']:<7} {insider:<22} {role:<18} "
              f"${r['value']:>11,.0f} {r['date']:<12} {r['reasons']}")


def show_ticker(ticker):
    df = idb.get_signals_by_ticker(ticker)

    print(f"\n{'='*80}")
    print(f"  SIGNALS FOR {ticker.upper()}")
    print(f"{'='*80}\n")

    if df.empty:
        print(f"  No signals for {ticker.upper()}.\n")
        return

    for _, r in df.iterrows():
        print(f"  {r['date']}  —  {r['insider']}  ({r['role']})")
        print(f"    Score:  {r['score']}/100")
        print(f"    Value:  ${r['value']:,.0f}  ({r['shares']:,.0f} shares @ ${r['price']:.2f})")
        print(f"    Position: +{r['pct_holding']:.0f}%  |  Trades: {r['n_transactions']}  |  Cluster: {r['cluster']}")
        print(f"    Reasons: {r['reasons']}")
        print(f"    First seen: {str(r['first_seen'])[:19]}")
        print()


def search_insider(name):
    df = idb.search_insider(name)

    print(f"\n{'='*80}")
    print(f"  SIGNALS FROM INSIDER: {name}")
    print(f"{'='*80}\n")

    if df.empty:
        print(f"  No signals found for '{name}'.\n")
        return

    for _, r in df.iterrows():
        print(f"  {r['date']}  —  {r['ticker']}  ({r['role']})")
        print(f"    ${r['value']:,.0f}  |  Score {r['score']}/100")
        print()


def main():
    if len(sys.argv) == 1:
        show_overview()
        show_top_signals(min_score=50)
    elif sys.argv[1] == "top":
        min_score = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        show_top_signals(min_score=min_score)
    elif sys.argv[1] == "ticker" and len(sys.argv) > 2:
        show_ticker(sys.argv[2])
    elif sys.argv[1] == "insider" and len(sys.argv) > 2:
        search_insider(" ".join(sys.argv[2:]))
    else:
        print("\nUsage:")
        print("  python insider_tracker.py                    → overview + top signals")
        print("  python insider_tracker.py top 60             → top signals with score >= 60")
        print("  python insider_tracker.py ticker TSLA        → all signals for TSLA")
        print("  python insider_tracker.py insider Musk       → search signals from 'Musk'")


if __name__ == "__main__":
    main()