// Cloudflare Worker — thin Yahoo Finance relay for the UK CGT calculator.
//
// This mirrors the /api/yahoo endpoint in serve.py so the calculator can run as
// a fully static, serverless deployment (e.g. Cloudflare Pages / GitHub Pages)
// instead of needing python3 serve.py on your own machine.
//
// PRIVACY: only a ticker symbol and a date range ever pass through here. Your
// vests, sales and BenefitHistory.xlsx are parsed entirely in your browser and
// never touch this worker — that's why there is deliberately NO /api/benefit
// endpoint here. Keep it that way.
//
// Deploy:
//   npm install -g wrangler        # once
//   wrangler deploy                # uses wrangler.toml in this folder
// then set WORKER_URL in index.html to the printed https://...workers.dev URL.

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
           "(KHTML, like Gecko) Chrome/124.0 Safari/537.36";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    const url = new URL(request.url);
    if (url.pathname !== "/api/yahoo") {
      return json(404, { error: "not found" });
    }

    const symbol = url.searchParams.get("symbol");
    const period1 = url.searchParams.get("period1");
    const period2 = url.searchParams.get("period2");
    const interval = url.searchParams.get("interval") || "1d";

    if (!(symbol && period1 && period2)) {
      return json(400, { error: "symbol, period1 and period2 are required" });
    }
    if (!(/^\d+$/.test(period1) && /^\d+$/.test(period2))) {
      return json(400, { error: "period1/period2 must be unix seconds" });
    }

    const yahoo = "https://query1.finance.yahoo.com/v8/finance/chart/" +
      encodeURIComponent(symbol) +
      `?period1=${period1}&period2=${period2}&interval=${encodeURIComponent(interval)}`;

    try {
      const resp = await fetch(yahoo, {
        headers: { "User-Agent": UA, "Accept": "application/json" },
      });
      const body = await resp.arrayBuffer();
      return new Response(body, {
        status: resp.status,
        headers: { "Content-Type": "application/json; charset=utf-8", ...CORS },
      });
    } catch (e) {
      return json(502, { error: "Could not reach Yahoo: " + e.message });
    }
  },
};

function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...CORS },
  });
}
