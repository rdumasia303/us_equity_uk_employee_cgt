# US Equity Comp for UK Workers — E\*Trade Handler & CGT Calculator

A UK **Capital Gains Tax** calculator for US equity compensation (RSUs, stock
options, ESPP and OSPS) held in **E\*Trade**. Feed it your benefit history and your
orders, and it untangles E\*Trade's fragmented exports and HMRC's share-matching
rules for you —
income-at-vest cost basis, same-day / 30-day / Section 104 matching, GBP
conversion, US-holiday adjustments, gains by tax year, and reports you can file.

**Try it now:** <https://www.absolutelynotfinancialadvice.co.uk/> — the hosted
version runs entirely in your browser (your benefit history, vests and sales
never leave your device). Prefer to run it yourself? See **Run it** below.

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

## The workflow

1. **Fetch market data** — enter your ticker (e.g. `ROKU`) and a start date. It
   pulls daily close prices, GBP/USD averages and US market holidays, and shows a
   sample of each so you can see it worked.
2. **Import vests** — drop in E\*Trade's `BenefitHistory.xlsx`
   (*At Work → My Account → Benefit History → Download Expanded*). RSU vests become
   acquisitions at the **shares released** (delivered) quantity, valued on the vest
   date. If your workbook also has **ESPP** and **OSPS** (dividend-reinvestment) tabs,
   those purchases are picked up too — each pooled at its own cost basis straight from
   the file. Screenshots of where to click are right there in the app.
3. **Paste orders** — copy the table on E\*Trade's *Orders / Transactions* page
   (set the date range back to your first order) and paste it in. Sells, cash
   exercises and same-day sales are turned into the right transactions; cancelled
   rows are ignored.
4. **Calculate** — get gains/losses by UK tax year, the Section 104 pool position,
   a full matching audit log, and exports.

Any transaction can also be typed in by hand.

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
- **ESPP & OSPS** lots (from a multi-tab benefit history) pooled at the cost basis
  in the file — ESPP at market value on the purchase date, OSPS (reinvested
  dividends) at the stated cost basis per share.
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
| `.github/workflows/deploy.yml` | GitHub Pages build: injects `WORKER_URL` and publishes the static site |
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

---

## Deploying the hosted version — *FOR AUTHOR ONLY*

> **Cloned this repo? Just run it locally** (see **Run it** above) — that's the
> supported way to use it, and it needs nothing but Python 3. The notes below are
> my own runbook for the official hosted instance. Please don't stand up your own
> public copy off the back of this.

The page is fully self-contained except for the Yahoo price/FX lookup, which a tiny
**Cloudflare Worker** relays. Holidays come straight from `date.nager.at` and the
`.xlsx` is parsed in the browser, so even the hosted version keeps vesting data on
the user's own device — only a ticker + date range ever reaches the worker.

The same `index.html` works both ways: served from `localhost` it uses `serve.py`'s
relay; served from anywhere else it uses the worker. So in source `WORKER_URL` is
left **blank** and the deploy fills it in (see below).

### 1. Deploy the price relay (Cloudflare Worker)

You need a **Cloudflare account** — it's free, no credit card, no domain:
sign up at <https://dash.cloudflare.com/sign-up> and confirm your email. The free
plan allows 100,000 worker requests/day (this app uses ~2 per "Fetch").

Then, from this folder (uses the bundled `worker.js` + `wrangler.toml`):

```bash
npx wrangler login    # opens a browser to authorise — run it in your own terminal
npx wrangler deploy   # first run picks a free <subdomain>.workers.dev for you
```

It prints your worker URL, e.g. `https://cgt-yahoo-relay.<subdomain>.workers.dev`.
Sanity-check it in a browser:
`…workers.dev/api/yahoo?symbol=AAPL&period1=1704067200&period2=1704153600` should
return Yahoo JSON. Re-deploy any time with `npx wrangler deploy`.

### 2a. Host the page yourself (any static host)

Set `WORKER_URL` near the top of the `<script>` in `index.html` to that URL (no
trailing slash), then upload `index.html` plus the images to any static host —
Cloudflare Pages, S3, Netlify, etc.

### 2b. Host on GitHub Pages (automated — included)

This repo ships `.github/workflows/deploy.yml`, which builds the site and injects
your worker URL into the **deployed copy only** (source stays blank, so clones and
local `serve.py` users are never routed through your worker). One-time setup:

1. **Worker URL as a repo variable** — Settings → Secrets and variables → Actions →
   **Variables** → New repository variable: name `WORKER_URL`, value your
   `https://…workers.dev` URL. (A variable, not a secret — it's public anyway.)
2. **Pages source** — Settings → Pages → Build and deployment → Source =
   **GitHub Actions**. (Repo must be public for free Pages.)

Then push to `main`. The workflow publishes to
`https://<user>.github.io/<repo>/`. If `WORKER_URL` isn't set yet the run fails
with a clear message — set it and re-run the job (no new push needed).
