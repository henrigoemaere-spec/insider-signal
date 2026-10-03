"""substack_generator.py — Human-written style Substack post (final)"""
import sys
import os
import re
from datetime import datetime

import insider_database as idb


ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


def fmt_money(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    if v >= 1_000_000_000:
        return f"${v/1_000_000_000:.2f}B"
    if v >= 1_000_000:
        m = v / 1_000_000
        return f"${m:.1f}M" if m < 10 else f"${m:.0f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"


def fix_insider_name(name):
    """SEC format: 'LAST FIRST M I' -> 'First M. Last III'
    Detect companies (LLC, Inc, etc.) and skip reversal."""
    name = str(name).strip()
    if not name:
        return name

    # If it looks like a company, return as title case
    company_suffixes = ["llc", "inc", "corp", "corporation", "ltd", "limited",
                        "plc", "co.", "co", "lp", "llp", "trust", "fund",
                        "partners", "capital", "holdings", "advisors", "group"]
    last_word = name.split()[-1].lower().strip(".,")
    if last_word in company_suffixes:
        return name.title().replace("Llc", "LLC").replace("Lp", "LP")

    parts = name.split()
    if len(parts) < 2:
        return name

    # Check for Roman numeral at end
    suffix = ""
    if len(parts) >= 2 and parts[-1].lower().strip(".") in ROMAN:
        suffix = parts[-1].upper()
        parts = parts[:-1]

    # Check for middle initial(s)
    middle = []
    while len(parts) >= 3 and len(parts[-1].strip(".")) == 1:
        middle.insert(0, parts[-1].strip(".").upper() + ".")
        parts = parts[:-1]

    if len(parts) < 2:
        return name

    last_name = parts[0].title()
    first_name = " ".join(p.title() for p in parts[1:])

    result = first_name
    if middle:
        result += " " + " ".join(middle)
    result += " " + last_name
    if suffix:
        result += " " + suffix
    return result


def clean_company(name, ticker):
    """Normalize company name to title case, remove suffixes."""
    c = str(name).strip().rstrip(",").strip()
    if not c:
        return ticker

    # Remove common suffixes
    for suffix in [" Incorporated", " Corporation", " Inc.", " Inc",
                   " Corp.", " Corp", " Ltd.", " Ltd", " LLC", " Co.",
                   " Co", " Plc", " plc", " Holdings, Inc.", " Holdings Inc",
                   " REIT", " Trust"]:
        if c.endswith(suffix):
            c = c[:-len(suffix)].strip()

    # If it's ALL CAPS, title case it
    if c.isupper() or (len(c) > 5 and sum(1 for ch in c if ch.isupper()) / len(c) > 0.7):
        c = c.title()

    # Fix "Of", "The", "And" - keep lowercase
    c = c.replace(" Of ", " of ").replace(" The ", " the ").replace(" And ", " and ")

    return c


def clean_role(role):
    """Turn a role string into a clean parenthetical."""
    r = str(role).strip()
    if not r or "see remarks" in r.lower() or len(r) > 45:
        return ""
    rl = r.lower()
    if "chief executive" in rl and "president" in rl:
        return "President & CEO"
    if "chief executive" in rl:
        return "CEO"
    if "chief financial" in rl:
        return "CFO"
    if "chief operating" in rl:
        return "COO"
    if "executive chairman" in rl:
        return "Executive Chairman"
    if "chairman" in rl:
        return "Chairman"
    if "president" in rl:
        return "President"
    if "treasurer" in rl:
        return "Treasurer"
    return r


def nice_date(d):
    """2026-09-30 -> September 30"""
    try:
        dt = datetime.strptime(str(d), "%Y-%m-%d")
        return dt.strftime("%B ") + str(dt.day)
    except Exception:
        return str(d)


def build_post(min_score=50, top_n=8):
    df = idb.get_all_signals(limit=top_n * 4, min_score=min_score)

    if df.empty:
        return None

    df["score"] = df["score"].astype(int)
    df["value"] = df["value"].astype(float)
    df = df.sort_values("score", ascending=False).head(top_n).reset_index(drop=True)

    today = datetime.now().strftime("%B ") + str(datetime.now().day) + ", " + str(datetime.now().year)

    lines = []
    lines.append(f"# Insider Buying — {today}")
    lines.append("")

    total = df["value"].sum()
    n = len(df)
    n_clusters = int((df["cluster"] >= 2).sum())
    n_ceos = int(df["role"].apply(
        lambda r: "ceo" in str(r).lower() or "chief executive" in str(r).lower()
    ).sum())

    intro = f"{n} insider buys worth {fmt_money(total)} this week."
    if n_clusters >= 2:
        intro += f" {n_clusters} of them were clusters — multiple insiders buying the same stock."
    if n_ceos >= 2:
        intro += f" {n_ceos} were CEOs."
    lines.append(intro)
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, r in df.iterrows():
        ticker = str(r["ticker"]).upper()
        insider = fix_insider_name(r["insider"])
        company = clean_company(r["company"], ticker)
        role = clean_role(r["role"])
        value = fmt_money(r["value"])
        date = nice_date(r["date"])
        pct = float(r["pct_holding"]) if r["pct_holding"] else 0
        n_tx = int(r["n_transactions"]) if r["n_transactions"] else 1
        cluster = int(r["cluster"]) if r["cluster"] else 0
        score = int(r["score"])

        if role:
            lead = f"**{company} ({ticker})** — {insider}, {role}, bought {value}"
        else:
            lead = f"**{company} ({ticker})** — {insider} bought {value}"

        if n_tx > 1:
            lead += f" across {n_tx} transactions"
        lead += f" on {date}."

        context = []
        if pct >= 10:
            if pct >= 500:
                context.append(f"more than {int(pct)}% of their existing position")
            else:
                context.append(f"{pct:.0f}% more of their existing position")
        if cluster >= 2:
            context.append(f"one of {cluster} insiders buying at the same time")

        if context:
            lead += " That's " + " and ".join(context) + "."

        lead += f" Score: {score}."

        lines.append(lead)
        lines.append("")

    lines.append("---")
    lines.append("")

    if n_clusters >= 2:
        lines.append(f"**Cluster watch:** {n_clusters} stocks had multiple insiders "
                     f"buying at the same time. That's the strongest setup — when "
                     f"several executives independently decide to buy.")
    elif n_ceos >= 2:
        lines.append(f"**CEO watch:** {n_ceos} CEOs bought this week. When the person "
                     f"running the company puts their own money in, that's worth noting.")
    else:
        lines.append("Signal quality matters more than signal count. A single CEO buy "
                     "beats ten director trades.")

    lines.append("")
    lines.append("*Not investment advice.*")

    return "\n".join(lines)


def save_post(post, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(post)


def main():
    min_score = 50
    top_n = 8

    if len(sys.argv) > 1:
        try:
            min_score = int(sys.argv[1])
        except ValueError:
            pass
    if len(sys.argv) > 2:
        try:
            top_n = int(sys.argv[2])
        except ValueError:
            pass

    print(f"\n  Substack generator")
    print(f"  Min score: {min_score}  |  Top: {top_n}\n")

    post = build_post(min_score=min_score, top_n=top_n)

    if not post:
        print(f"  No signals with score >= {min_score} in database.")
        print(f"  Run `python insider_scanner.py fast 10` first.\n")
        return

    print("=" * 78)
    print(post)
    print("=" * 78)

    date = datetime.now().strftime("%Y%m%d")
    path = f"C:\\Users\\henri\\substack_post_{date}.md"
    save_post(post, path)
    print(f"\n  Saved: {path}")
    print(f"  Copy to Substack and publish.\n")


if __name__ == "__main__":
    main()