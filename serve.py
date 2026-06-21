#!/usr/bin/env python3
"""
Local runner for the US Equity / UK CGT calculator (index.html).

Run it on your own machine — no accounts, no cloud, no pip installs. It uses
only the Python 3 standard library. It serves the app and acts as a small relay
for two things browsers can't do directly: fetch Yahoo Finance prices (CORS),
and read BenefitHistory.xlsx. Only the ticker symbol and a date range are ever
sent to Yahoo; your benefit history, vests and sales never leave your computer.

Usage:
    python3 serve.py
    (then your browser opens at http://localhost:8000 automatically)

Optionally pick a port:
    python3 serve.py 9000
"""

import io
import json
import os
import re
import sys
import threading
import webbrowser
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DIR = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# --------------------------------------------------------------------------- xlsx
# Extract the vesting log straight from E*TRADE's BenefitHistory.xlsx, so the user
# doesn't have to run etrade_translate.py first. Pure standard library. Ported from
# etrade_translate.py — see that script for the gory details of the export format.
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def _col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    idx = 0
    for c in letters:
        idx = idx * 26 + (ord(c) - ord("A") + 1)
    return idx - 1


def _read_sheets(data):
    """{sheet_name: [[cell, ...], ...]} from xlsx bytes, shared strings resolved."""
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{_NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {r.get("Id"): r.get("Target") for r in rels}
    R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    sheets = {}
    for s in wb.iter(f"{_NS}sheet"):
        target = rid_to_target[s.get(R)].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ET.fromstring(z.read(target))
        rows = []
        for row in root.iter(f"{_NS}row"):
            cells, maxc = {}, -1
            for c in row.findall(f"{_NS}c"):
                ci = _col_index(c.get("r"))
                v = c.find(f"{_NS}v")
                istr = c.find(f"{_NS}is")
                if c.get("t") == "s" and v is not None:
                    val = shared[int(v.text)]
                elif istr is not None:
                    val = "".join(x.text or "" for x in istr.iter(f"{_NS}t"))
                elif v is not None:
                    val = v.text
                else:
                    val = ""
                cells[ci] = val.strip() if isinstance(val, str) else val
                maxc = max(maxc, ci)
            rows.append([cells.get(j, "") for j in range(maxc + 1)])
        sheets[s.get("name")] = rows
    return sheets


def _header_map(header):
    m = {}
    for i, name in enumerate(header):
        if name and name not in m:
            m[name] = i
    return m


def _iso_event(d):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", d or "")
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else (d or "")


def _num(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0


def benefit_to_vesting_csv(data):
    """Build the 04_vesting_log.csv content from BenefitHistory.xlsx bytes."""
    sheets = _read_sheets(data)
    vests = []  # [date, symbol, grant, instrument, vested, released, withheld, pct]

    rsu = sheets.get("Restricted Stock", [])
    if rsu:
        H = _header_map(rsu[0])
        meta = {}
        vest_pair = defaultdict(lambda: {"vested": 0, "released": 0})
        gi = H.get("Grant Number", 0)
        for r in rsu[1:]:
            g = r[gi] if len(r) > gi else ""
            if r[0] == "Grant":
                meta[g] = r
            elif r[0] == "Event":
                etype = r[H["Event Type"]]
                date = _iso_event(r[H["Date"]])
                qty = _num(r[H["Qty. or Amount"]])
                if etype == "Shares vested":
                    vest_pair[(g, date)]["vested"] += qty
                elif etype == "Shares released":
                    vest_pair[(g, date)]["released"] += qty
        for (g, date), p in vest_pair.items():
            vested, released = p["vested"], p["released"]
            withheld = vested - released
            pct = f"{withheld / vested * 100:.0f}%" if vested else ""
            sym = meta[g][H["Symbol"]] if g in meta else ""
            vests.append([date, sym, g, "RSU", vested, released, withheld, pct])

    opt = sheets.get("Options", [])
    if opt:
        H = _header_map(opt[0])
        meta = {}
        gi = H.get("Grant Number", 0)
        for r in opt[1:]:
            g = r[gi] if len(r) > gi else ""
            if r[0] == "Grant":
                meta[g] = r
            elif r[0] == "Event" and r[H["Event Type"]] == "Shares vested":
                date = _iso_event(r[H["Date"]])
                qty = _num(r[H["Qty"]])
                sym = meta[g][H["Symbol"]] if g in meta else ""
                vests.append([date, sym, g, "Option", qty, "", "", ""])

    vests.sort(key=lambda x: x[0])
    out = io.StringIO()
    out.write("Date,Symbol,From Grant,Instrument,Shares Vested,"
              "Shares Released (delivered),Withheld for Tax,% Withheld\n")
    for row in vests:
        out.write(",".join(str(c) for c in row) + "\n")
    return out.getvalue()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/yahoo":
            return self.api_yahoo(urllib.parse.parse_qs(parsed.query))
        if parsed.path in ("/", ""):
            self.path = "/index.html"
        # everything else is served as a normal static file
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/benefit":
            length = int(self.headers.get("Content-Length") or 0)
            data = self.rfile.read(length) if length else b""
            if not data:
                return self._json(400, {"error": "no file uploaded"})
            try:
                csv_text = benefit_to_vesting_csv(data)
            except Exception as e:  # noqa: BLE001
                return self._json(400, {"error": f"Could not parse BenefitHistory.xlsx: {e}"})
            rows = max(0, csv_text.count("\n") - 1)
            return self._json(200, {"vestingCsv": csv_text, "rows": rows})
        return self._json(404, {"error": "not found"})

    def api_yahoo(self, q):
        symbol = (q.get("symbol") or [None])[0]
        period1 = (q.get("period1") or [None])[0]
        period2 = (q.get("period2") or [None])[0]
        interval = (q.get("interval") or ["1d"])[0]

        if not (symbol and period1 and period2):
            return self._json(400, {"error": "symbol, period1 and period2 are required"})
        if not (period1.isdigit() and period2.isdigit()):
            return self._json(400, {"error": "period1/period2 must be unix seconds"})

        url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
               + urllib.parse.quote(symbol)
               + f"?period1={period1}&period2={period2}&interval={urllib.parse.quote(interval)}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
            self._raw(200, body)
        except urllib.error.HTTPError as e:
            self._json(e.code, {"error": f"Yahoo returned HTTP {e.code} for {symbol}"})
        except Exception as e:  # noqa: BLE001
            self._json(502, {"error": f"Could not reach Yahoo: {e}"})

    def _raw(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._raw(code, json.dumps(obj).encode("utf-8"))

    def log_message(self, fmt, *args):
        # keep the console quiet except for API errors
        if "/api/" in (self.path or ""):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Ignoring invalid port '{sys.argv[1]}', using {port}.")

    os.chdir(DIR)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        print(f"Could not start on port {port}: {e}")
        print(f"Try a different port, e.g.  python3 serve.py {port + 1}")
        sys.exit(1)

    url = f"http://localhost:{port}/"
    print("=" * 60)
    print("  US Equity / UK CGT calculator is running.")
    print(f"  Open:  {url}")
    print("  Stop:  press Ctrl+C")
    print("=" * 60)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()
