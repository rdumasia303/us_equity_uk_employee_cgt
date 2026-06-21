# US Equity Comp for UK Workers — E\*Trade Handler & CGT Calculator

A UK **Capital Gains Tax** calculator for US equity compensation (RSUs and stock
options) held in **E\*Trade**. Feed it your benefit history and your orders, and it
untangles E\*Trade's fragmented exports and HMRC's share-matching rules for you —
income-at-vest cost basis, same-day / 30-day / Section 104 matching, GBP
conversion, US-holiday adjustments, gains by tax year, and reports you can file.

Everything runs **on your own machine**. The only thing that ever leaves it is a
ticker symbol and a date range (to look up prices). Your benefit history, vests
and sales never go anywhere.

## Run it

You need **Python 3** — nothing else, no `pip install`, no accounts, no cloud.

```bash
python3 serve.py
```

It opens the app at `http://localhost:8000`. `serve.py` is pure standard library;
it serves the page and relays the one thing a browser can't do itself: fetch
Yahoo Finance prices (CORS). Your `BenefitHistory.xlsx` is parsed **in the browser**,
so it never leaves the page.

## Deploy it (serverless, optional)

You don't need `serve.py` at all if you'd rather host the app statically. The page
is fully self-contained except for the Yahoo price/FX lookup, which a tiny
**Cloudflare Worker** relays:

```bash
npm install -g wrangler   # once
wrangler deploy           # deploys worker.js using wrangler.toml
```

Then set `WORKER_URL` near the top of the `<script>` in `index.html` to the printed
`https://<name>.<subdomain>.workers.dev` URL, and host `index.html` (and the images)
on any static host — Cloudflare Pages, GitHub Pages, S3, etc. Holidays come straight
from `date.nager.at`, prices/FX go through your worker, and the `.xlsx` is parsed in
the browser — so even the hosted version keeps your vesting data on your own device.
Run locally with `serve.py` and deployed with the worker from the **same** file:
when served from `localhost` it uses `serve.py`'s relay, otherwise the worker.

## The workflow

1. **Fetch market data** — enter your ticker (e.g. `ROKU`) and a start date. It
   pulls daily close prices, GBP/USD averages and US market holidays, and shows a
   sample of each so you can see it worked.
2. **Import vests** — drop in E\*Trade's `BenefitHistory.xlsx`
   (*At Work → My Account → Benefit History → Download Expanded*). RSU vests become
   acquisitions at the **shares released** (delivered) quantity, valued on the vest
   date. Screenshots of where to click are right there in the app.
3. **Paste orders** — copy the table on E\*Trade's *Orders / Transactions* page
   (set the date range back to your first order) and paste it in. Sells, cash
   exercises and same-day sales are turned into the right transactions; cancelled
   rows are ignored.
4. **Calculate** — get gains/losses by UK tax year, the Section 104 pool position,
   a full matching audit log, and exports.

Anything can also be typed in by hand, and you can paste market-data CSVs offline
via the **Advanced** panel.

## What it works out

- **Cost basis = market value on the vesting date** (the figure you were taxed on
  as income; TCGA 1992 s.119A), rolled to the next trading day for weekend/holiday
  vests so the date and value stay pinned together.
- **HMRC share identification** in strict order: **same-day → 30-day "bed &
  breakfast" → Section 104 pool**. A *Matched via* column shows which rule each
  disposal used, so you can see which sales were genuine same-day non-events and
  which came out of the pool.
- **Options** treated as shares once exercised (cash-exercise-and-hold pools;
  same-day exercise-and-sell nets to ~£0).
- **USD → GBP** at the daily exchange rate.

## Exports

- **HMRC report (editable Word)** — a per-tax-year summary, detailed disposals and
  the Section 104 closing position, plus a **capital-loss four-year-claim** check
  that flags, for each loss-making year, the deadline to notify HMRC and whether
  it has passed.
- **CSVs** — disposals, the matching/audit log, the consolidated transactions, and
  your imported orders (re-importable).

## Themes

Toggle between a **Cyberpunk** and a **Corporate** look (top-right). The *How it
works* tab has both a plain-English/irreverent guide and a sober, statute-cited
version of the same tax explanation.

## Files

| File | What it is |
|------|------------|
| `index.html` | The whole app — UI + calculation engine + in-browser `.xlsx` parser, single file |
| `serve.py` | Local server: serves the app and relays Yahoo prices |
| `worker.js` | Cloudflare Worker: the same Yahoo relay, for serverless/static hosting |
| `wrangler.toml` | Cloudflare deploy config for `worker.js` |
| `*.png` / `*.jpg` | The in-app "how to get your data" screenshots |
| `logo.webp`, `favicon.png` | Branding |

## Privacy

All data lives in your browser's local storage and never leaves your machine.
The only outbound request carrying anything is a ticker symbol + date range to
Yahoo for prices — forwarded by `serve.py` locally, or by your Cloudflare Worker
when deployed (the worker deliberately has **no** benefit-history endpoint). Your
`BenefitHistory.xlsx` is parsed entirely in the browser. `.gitignore` keeps any personal exports
(`BenefitHistory.xlsx`, `stock.csv`, vesting logs, etc.) out of version control.

## Disclaimer

This is **not** financial or tax advice. It's a calculator to help you understand
and compute your position — always verify the figures and consult a qualified
professional before submitting anything to HMRC. Provided "as is", with no
warranty of accuracy. See `LICENSE`.
