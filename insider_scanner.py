"""insider_scanner.py — SEC insider scanner with rate limiting and sanity checks (v10)"""
import sys
import os
import time
import csv
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import math

import insider_database as idb


HEADERS = {
    "User-Agent": "Henri Goemaere henri.goemaere@icloud.com",
    "Accept-Encoding": "gzip, deflate",
}

MAX_WORKERS = 8
MAX_REQ_PER_SEC = 8
MAX_FILINGS = 3
MIN_VALUE = 25_000
MAX_VALUE = 5_000_000_000        # Sanity: skip > $5B (only Musk-level)
MAX_PRICE = 10_000                # Sanity: skip > $10K/share
DEFAULT_LOOKBACK = 3


_rate_lock = Lock()
_recent_requests = []


def wait_for_request():
    global _recent_requests
    with _rate_lock:
        now = time.time()
        _recent_requests = [t for t in _recent_requests if now - t < 1.0]
        if len(_recent_requests) >= MAX_REQ_PER_SEC:
            oldest = _recent_requests[0]
            sleep_time = 1.0 - (now - oldest) + 0.01
            time.sleep(sleep_time)
            now = time.time()
            _recent_requests = [t for t in _recent_requests if now - t < 1.0]
        _recent_requests.append(now)


def safe_get(url, timeout=15):
    for attempt in range(3):
        wait_for_request()
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 429:
                print(f"    [429] Rate limit — waiting 30s...")
                time.sleep(30)
                continue
            return r
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)
    return None


IDX_PATTERN = re.compile(
    r'^(\S+)\s+(.+?)\s{2,}(\d{7,10})\s+(\d{8})\s+(edgar/\S+)'
)


_CIK_REVERSE = None


def load_cik_reverse():
    global _CIK_REVERSE
    if _CIK_REVERSE is not None:
        return _CIK_REVERSE
    r = safe_get("https://www.sec.gov/files/company_tickers.json")
    if not r:
        return {}
    data = r.json()
    reverse = {}
    for entry in data.values():
        ticker = entry.get("ticker", "").strip().upper()
        cik = str(entry["cik_str"]).zfill(10)
        if ticker:
            reverse[cik] = ticker
    _CIK_REVERSE = reverse
    return reverse


def daily_index_url(date):
    quarter = f"QTR{(date.month - 1) // 3 + 1}"
    return (f"https://www.sec.gov/Archives/edgar/daily-index/"
            f"{date.year}/{quarter}/form.{date.strftime('%Y%m%d')}.idx")


def fetch_daily_index(date):
    url = daily_index_url(date)
    r = safe_get(url, timeout=20)
    if not r or r.status_code != 200:
        return []
    text = r.text
    results = []
    for line in text.split("\n"):
        match = IDX_PATTERN.match(line.strip())
        if not match:
            continue
        form_type, company, cik, date_str, filename = match.groups()
        if form_type not in ("4", "4/A"):
            continue
        if len(date_str) == 8:
            date_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        else:
            date_iso = date_str
        parts = filename.split("/")
        try:
            accession = parts[3].replace(".txt", "").replace("-", "")
        except IndexError:
            continue
        results.append({
            "cik": cik.zfill(10),
            "accession": accession,
            "date": date_iso,
        })
    return results


def fetch_all_recent_form4(days=DEFAULT_LOOKBACK, workers=MAX_WORKERS):
    print(f"\n  Pass 1: downloading daily index files ({days} days)...")
    dates = []
    today = datetime.now().date()
    for i in range(days):
        d = today - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        dates.append(d)
    print(f"  {len(dates)} trading days to process")

    all_filings = []
    start = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_daily_index, d): d for d in dates}
        for fut in as_completed(futures):
            done += 1
            try:
                results = fut.result()
                all_filings.extend(results)
                print(f"    Day {done}/{len(dates)}: {len(results)} Form 4s")
            except Exception as e:
                print(f"    Day {done}: ERROR — {e}")

    elapsed = time.time() - start
    print(f"  Pass 1 done in {elapsed:.1f}s: {len(all_filings)} Form 4 filings")

    per_cik = defaultdict(list)
    for f in all_filings:
        per_cik[f["cik"]].append(f)
    print(f"  Unique companies: {len(per_cik)}")
    return per_cik


def find_xml_file(cik, accession):
    cik_clean = str(int(cik))
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession}/index.json"
    r = safe_get(url, timeout=10)
    if not r or r.status_code != 200:
        return None
    try:
        items = r.json().get("directory", {}).get("item", [])
    except Exception:
        return None
    for item in items:
        name = item.get("name", "")
        if name.lower().endswith(".xml") and "form4" in name.lower():
            return name
    for item in items:
        name = item.get("name", "")
        if name.lower().endswith(".xml") and not name.endswith("_cal.xml") and not name.endswith("_def.xml"):
            return name
    return None


def fetch_form4_content(cik, accession):
    try:
        cik_clean = str(int(cik))
        xml_file = find_xml_file(cik, accession)
        if not xml_file:
            return None
        url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession}/{xml_file}"
        r = safe_get(url, timeout=10)
        if not r or r.status_code != 200:
            return None
        root = ET.fromstring(r.content)
    except Exception:
        return None

    result = {"transactions": []}
    issuer = root.find(".//issuer")
    if issuer is not None:
        result["company"] = issuer.findtext("issuerName", "")
        result["ticker_xml"] = issuer.findtext("issuerTradingSymbol", "")

    owner = root.find(".//reportingOwner")
    if owner is not None:
        result["insider_name"] = owner.findtext(".//rptOwnerName", "")
        result["is_director"] = owner.findtext(".//isDirector", "0") == "1"
        result["is_officer"] = owner.findtext(".//isOfficer", "0") == "1"
        result["is_ten_percent"] = owner.findtext(".//isTenPercentOwner", "0") == "1"
        result["role"] = owner.findtext(".//officerTitle", "")

    for tx in root.findall(".//nonDerivativeTransaction"):
        code = tx.findtext(".//transactionCode", "")
        shares = tx.findtext(".//transactionShares/value", "0")
        price = tx.findtext(".//transactionPricePerShare/value", "0")
        acq_disp = tx.findtext(".//transactionAcquiredDisposedCode/value", "")
        date = tx.findtext(".//transactionDate/value", "")
        shares_after = tx.findtext(".//sharesOwnedFollowingTransaction/value", "0")
        try:
            shares_f = float(shares)
            price_f = float(price)
            shares_after_f = float(shares_after)
        except (ValueError, TypeError):
            shares_f, price_f, shares_after_f = 0, 0, 0
        result["transactions"].append({
            "code": code, "shares": shares_f, "price": price_f,
            "value": shares_f * price_f, "type": acq_disp,
            "date": date, "shares_after": shares_after_f,
        })
    return result


def role_label(title, is_director, is_officer, is_ten_percent):
    if title: return title
    if is_officer: return "Officer"
    if is_director: return "Director"
    if is_ten_percent: return "10% Owner"
    return "Insider"


def role_weight(role):
    r = role.lower()
    if "ceo" in r or "chief executive" in r: return 10
    if "cfo" in r or "chief financial" in r: return 9
    if "coo" in r or "chief operating" in r: return 8
    if "president" in r or "chairman" in r: return 7
    if "officer" in r: return 5
    if "director" in r: return 4
    if "10%" in r: return 3
    return 2


def compute_score(signal):
    score = 0
    reasons = []
    rw = signal["role_weight"]
    score += rw * 2.5
    if rw >= 9: reasons.append("top-exec")
    elif rw >= 7: reasons.append("senior")

    value = signal["value"]
    if value > 0:
        log_w = math.log10(max(value, 1))
        score += min(25, max(0, (log_w - 4) * 8.3))
        if value >= 1_000_000: reasons.append(f"${value/1_000_000:.1f}M")

    pct = signal.get("pct_holding", 0)
    if pct >= 50: score += 30; reasons.append(f"+{pct:.0f}% position")
    elif pct >= 25: score += 22; reasons.append(f"+{pct:.0f}% position")
    elif pct >= 10: score += 15; reasons.append(f"+{pct:.0f}% position")
    elif pct >= 5: score += 8
    elif pct > 0: score += 3

    n_tx = signal.get("n_transactions", 1)
    if n_tx >= 5: score += 10; reasons.append(f"{n_tx} transactions")
    elif n_tx >= 2: score += 5

    cluster = signal.get("cluster", 0)
    if cluster >= 3: score += 10; reasons.append(f"cluster {cluster}")
    elif cluster == 2: score += 5; reasons.append("cluster 2")

    if signal.get("days_ago", 999) <= 7: score += 5; reasons.append("recent")
    return min(100, int(score)), reasons


def process_filing(ticker, cik, accession, filing_date):
    content = fetch_form4_content(cik, accession)
    if not content:
        return []
    title = content.get("role", "")
    role = role_label(title,
                      content.get("is_director", False),
                      content.get("is_officer", False),
                      content.get("is_ten_percent", False))
    p_tx = [t for t in content.get("transactions", [])
            if t["code"] == "P" and t["type"] == "A"]
    if not p_tx:
        return []
    total_shares = sum(t["shares"] for t in p_tx)
    total_value = sum(t["value"] for t in p_tx)
    if total_value < MIN_VALUE:
        return []

    # === SANITY CHECKS ===
    if total_value > MAX_VALUE:
        return []
    if total_shares > 0 and (total_value / total_shares) > MAX_PRICE:
        return []

    last_shares_after = p_tx[-1]["shares_after"]
    shares_before = last_shares_after - total_shares
    pct_holding = (total_shares / shares_before * 100) if shares_before > 0 else 0

    # Extra sanity: pct_holding mag niet onrealistisch hoog zijn
    if pct_holding > 10_000:
        return []

    dates = [t["date"] for t in p_tx if t["date"]]
    last_date = max(dates) if dates else filing_date
    try:
        dt = datetime.strptime(last_date, "%Y-%m-%d").date()
        days_ago = (datetime.now().date() - dt).days
    except Exception:
        days_ago = 999

    ticker_from_xml = content.get("ticker_xml", "").strip().upper()
    if ticker_from_xml and ticker_from_xml not in ("N/A", "NA", "NONE", ""):
        ticker = ticker_from_xml
    else:
        reverse = load_cik_reverse()
        ticker = reverse.get(cik, "")
        if not ticker:
            return []

    return [{
        "ticker": ticker.upper(),
        "company": content.get("company", ""),
        "insider": content.get("insider_name", ""),
        "role": role, "role_weight": role_weight(role),
        "date": last_date, "days_ago": days_ago,
        "shares": total_shares,
        "price": total_value / total_shares if total_shares else 0,
        "value": total_value, "pct_holding": pct_holding,
        "n_transactions": len(p_tx), "cluster": 0,
    }]


def process_company(args):
    cik, filings, ticker_fallback = args
    result = []
    filings_sorted = sorted(filings, key=lambda x: x["date"], reverse=True)[:MAX_FILINGS]
    for f in filings_sorted:
        try:
            result.extend(process_filing(ticker_fallback, cik, f["accession"], f["date"]))
        except Exception:
            continue
    return result


def count_clusters(signals):
    per_ticker = defaultdict(set)
    for s in signals:
        if s["days_ago"] <= 30:
            per_ticker[s["ticker"]].add(s["insider"])
    for s in signals:
        s["cluster"] = len(per_ticker.get(s["ticker"], set()))
    return signals


def print_top_signals(signals, top_n=20):
    if not signals:
        print("\n  No signals found.\n")
        return
    signals_sorted = sorted(signals, key=lambda x: -x["score"])
    print(f"\n{'='*100}")
    print(f"  TOP {min(top_n, len(signals_sorted))} SIGNALS")
    print(f"{'='*100}\n")
    print(f"  {'#':<3} {'Score':<7} {'Ticker':<7} {'Insider':<22} {'Role':<18} {'Value':>13} {'Reason'}")
    print(f"{'-'*98}")
    for i, s in enumerate(signals_sorted[:top_n], 1):
        insider = s["insider"][:20]
        role = s["role"][:16]
        reasons = " | ".join(s["reasons"][:3])
        print(f"  {i:<3} {s['score']:>3}/100 {s['ticker']:<7} {insider:<22} {role:<18} ${s['value']:>11,.0f} {reasons}")


def save_csv(signals, path):
    if not signals: return
    fields = ["ticker", "company", "insider", "role", "score", "date",
              "value", "shares", "price", "pct_holding", "n_transactions", "cluster"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for s in sorted(signals, key=lambda x: -x.get("score", 0)):
            writer.writerow(s)


def main():
    args = sys.argv[1:]
    t0 = time.time()

    fast_mode = False
    all_mode = False
    rest_args = []
    for a in args:
        if a.lower() == "fast":
            fast_mode = True
        elif a.lower() == "all":
            all_mode = True
        else:
            rest_args.append(a)

    if rest_args and not (fast_mode or all_mode):
        tickers = [t.upper() for t in rest_args]
        label = f"specific ({', '.join(tickers)})"
        print(f"\n  Specific tickers: {', '.join(tickers)}\n")

        r = safe_get("https://www.sec.gov/files/company_tickers.json")
        data = r.json()
        cik_map = {}
        for entry in data.values():
            t = entry.get("ticker", "").strip().upper()
            if t in tickers:
                cik_map[t] = str(entry["cik_str"]).zfill(10)

        per_cik = defaultdict(list)
        for ticker, cik in cik_map.items():
            r = safe_get(f"https://data.sec.gov/submissions/CIK{cik}.json")
            if not r: continue
            sub = r.json()
            recent = sub.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            for i, form in enumerate(forms):
                if form == "4":
                    per_cik[cik].append({
                        "accession": accessions[i].replace("-", ""),
                        "date": dates[i],
                    })
                    if len(per_cik[cik]) >= MAX_FILINGS: break
    else:
        days = DEFAULT_LOOKBACK
        if rest_args and rest_args[0].isdigit():
            days = int(rest_args[0])

        if all_mode:
            days = 30
            label = f"full ({days} days)"
        else:
            label = f"fast ({days} days)"

        per_cik = fetch_all_recent_form4(days=days)

    if not per_cik:
        print("\n  No Form 4 filings found.\n")
        return

    print(f"\n{'='*78}")
    print(f"  INSIDER SCANNER v10 — {label.upper()}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Rate limit: {MAX_REQ_PER_SEC} req/s ({MAX_WORKERS} workers)")
    print(f"  Sanity: value < ${MAX_VALUE/1e9:.0f}B, price < ${MAX_PRICE:,}")
    print(f"{'='*78}")

    print(f"\n  Pass 2: fetching XML for {len(per_cik)} companies...")
    cik_reverse = load_cik_reverse()
    tasks = [(cik, fil, cik_reverse.get(cik, cik)) for cik, fil in per_cik.items()]

    all_signals = []
    start = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(process_company, t): t[0] for t in tasks}
        for fut in as_completed(futures):
            done += 1
            if done % 100 == 0 or done == len(tasks):
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                remaining = (len(tasks) - done) / rate if rate > 0 else 0
                print(f"    {done}/{len(tasks)} companies "
                      f"({rate:.1f}/s, ~{remaining:.0f}s left)")
            try:
                all_signals.extend(fut.result())
            except Exception:
                continue

    all_signals = count_clusters(all_signals)
    for s in all_signals:
        s["score"], s["reasons"] = compute_score(s)
    print_top_signals(all_signals, top_n=20)

    added = idb.save_signals(all_signals)
    idb.save_scan(len(all_signals), len(per_cik))
    print(f"\n  Database: {added} new signals saved "
          f"({len(all_signals) - added} already present)")

    if all_signals:
        date = datetime.now().strftime("%Y%m%d_%H%M")
        csv_path = f"C:\\Users\\henri\\insider_signals_{date}.csv"
        save_csv(all_signals, csv_path)
        print(f"  CSV: {csv_path}")

    total_time = time.time() - t0
    print(f"\n  Total: {len(all_signals)} insider buys from {len(per_cik)} companies")
    print(f"  Total time: {total_time/60:.1f} minutes\n")


if __name__ == "__main__":
    main()