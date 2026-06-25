#!/usr/bin/env node
/*
 * Parity test suite for the UK CGT engine.
 * --------------------------------------------------------------------------
 * Loads the ACTUAL calculation engine out of ../index.html (no copy, no mock)
 * and asserts it against scenarios hand-computed to the statute, so the maths
 * the report relies on is provably correct.
 *
 * Each case exercises a specific HMRC share-identification rule and shows the
 * arithmetic in its comment, so a reviewer can verify the expected figures
 * independently:
 *   - Same-day rule .......... TCGA 1992 s.105   (HMRC CG51560)
 *   - 30-day "bed & breakfast" TCGA 1992 s.106A  (HMRC CG51560)
 *   - Section 104 pool ....... TCGA 1992 s.104    (HMRC CG51575, HS284)
 *   - Cost basis at vest ..... TCGA 1992 s.119A   (HMRC HS287, ERSM110000)
 *
 * Run:  node tests/parity.js     (exit code 0 = all pass, 1 = a failure)
 */

'use strict';
const fs = require('fs');
const path = require('path');

// ---- load the engine from index.html ------------------------------------
const htmlPath = path.join(__dirname, '..', 'index.html');
const html = fs.readFileSync(htmlPath, 'utf8');
const re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;
const blocks = [];
let m;
while ((m = re.exec(html))) blocks.push(m[1]);

// Minimal browser stubs: the engine functions we test touch no DOM, but the
// file's top-level init()/IIFE do — give them harmless no-ops.
function fakeEl() {
  return new Proxy({ value: '', textContent: '', innerHTML: '', style: {}, files: [],
    classList: { add() {}, remove() {}, toggle() { return false; }, contains() { return false; } },
    addEventListener() {}, appendChild() {}, querySelector: () => fakeEl(), querySelectorAll: () => [],
    getAttribute: () => null, setAttribute() {}, scrollIntoView() {} },
    { get(t, k) { return k in t ? t[k] : () => fakeEl(); } });
}
globalThis.document = { getElementById: () => fakeEl(), querySelector: () => fakeEl(),
  querySelectorAll: () => [], createElement: () => fakeEl(), addEventListener: () => {},
  body: { classList: { toggle() { return false; }, add() {}, remove() {} } } };
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
globalThis.window = {};
globalThis.alert = () => {};

let code = blocks.join('\n;\n').replace(/\binit\(\);/g, '/* init disabled for tests */');
code += '\n;globalThis.__engine = { Transaction, processCGT, parseVestingLog, benefitPurchaseEntries, formatDate, Section104Pool };';
(0, eval)(code);
const { Transaction, processCGT, parseVestingLog, benefitPurchaseEntries } = globalThis.__engine;

// ---- helpers -------------------------------------------------------------
// Work in GBP per share with FX 1 so expected figures are transparent; the
// engine matches and computes gains on the GBP price, FX only affects display.
function row(recordType, date, qty, gbp, opts = {}) {
  return new Transaction({
    'Record Type': recordType, 'Date': date, 'Qty.': qty,
    'Price Per Share GBP': gbp, 'Price Per Share': gbp, 'Exchange Rate': 1,
    'Order Type': opts.orderType || '', 'Type': opts.type || '',
    'Grant Number': opts.grant || '', '_pairId': opts.pairId || null,
  });
}
const BUY = (date, qty, gbp, opts) => row('BUY', date, qty, gbp, opts);
const SELL = (date, qty, gbp, opts) => row('SELL', date, qty, gbp, opts);

const MONEY_TOL = 0.005;
const SHARE_TOL = 0.01;

let passed = 0, failed = 0;
const failures = [];

function near(actual, expected, tol, label) {
  if (Math.abs(actual - expected) <= tol) { passed++; return true; }
  failed++; failures.push(`${label}: expected ${expected}, got ${actual}`); return false;
}
function eq(actual, expected, label) {
  if (actual === expected) { passed++; return true; }
  failed++; failures.push(`${label}: expected "${expected}", got "${actual}"`); return false;
}

// Run one CGT case: assert per-disposal gain + matchedVia, and final pool.
function runCGT(name, txns, expected) {
  let res;
  try { res = processCGT(txns.map(t => t)); }
  catch (e) { failed++; failures.push(`${name}: threw "${e.message}"`); console.log(`  ✗ ${name} (threw)`); return; }

  const before = failed;
  const disp = res.realized;
  eq(disp.length, expected.disposals.length, `${name}: disposal count`);
  expected.disposals.forEach((ex, i) => {
    if (!disp[i]) { failed++; failures.push(`${name}: missing disposal #${i + 1}`); return; }
    near(disp[i].gainLossGBP, ex.gain, MONEY_TOL, `${name}: disposal #${i + 1} gain`);
    if (ex.via) eq(disp[i].matchedVia, ex.via, `${name}: disposal #${i + 1} matched-via`);
  });
  near(res.s104Pool.totalShares, expected.pool.shares, SHARE_TOL, `${name}: final pool shares`);
  if (expected.pool.shares > SHARE_TOL && expected.pool.avg != null) {
    near(res.s104Pool.avgCostGBP, expected.pool.avg, MONEY_TOL, `${name}: final pool avg cost`);
  }
  console.log(`  ${failed === before ? '✓' : '✗'} ${name}`);
}

// ======================================================================
console.log('\nUK CGT engine — parity tests\n');

// CASE 1 — Section 104 pool averaging (s.104).
//   Buy 1000 @ £4.00 (= £4,000) and 500 @ £5.00 (= £2,500)
//   Pool: 1,500 sh, £6,500  →  avg £4.33333/sh
//   Sell 600 @ £7.00 = £4,200 proceeds
//   Cost = 600 × 4.33333 = £2,600.00  →  gain £1,600.00
//   Pool left: 900 sh @ £4.33333 (= £3,900)
runCGT('s.104 pool averaging', [
  BUY('2020-01-15', 1000, 4.00),
  BUY('2021-06-10', 500, 5.00),
  SELL('2023-03-01', 600, 7.00),
], { disposals: [{ gain: 1600.00, via: 'Pool' }], pool: { shares: 900, avg: 4.33333 } });

// CASE 2 — Same-day rule beats the pool (s.105).
//   Hold 100 @ £10 in the pool. On 2023-02-01 buy 50 @ £20 AND sell 50 @ £21.
//   Same-day match: 50 sold against the 50 bought that day @ £20.
//   Cost £1,000, proceeds £1,050  →  gain £50.00. Pool (100 @ £10) untouched.
runCGT('s.105 same-day precedence', [
  BUY('2022-01-10', 100, 10.00),
  BUY('2023-02-01', 50, 20.00),
  SELL('2023-02-01', 50, 21.00),
], { disposals: [{ gain: 50.00, via: 'Same-day' }], pool: { shares: 100, avg: 10.00 } });

// CASE 3 — 30-day "bed & breakfast" rule (s.106A).
//   Hold 200 @ £5. Sell 100 @ £8 on 2023-05-01, then buy 100 @ £6 on 2023-05-20
//   (19 days later, inside the 30-day window). The sale matches the LATER buy,
//   not the pool: cost £600, proceeds £800  →  gain £200.00. Pool stays 200 @ £5.
runCGT('s.106A 30-day bed & breakfast', [
  BUY('2021-01-01', 200, 5.00),
  SELL('2023-05-01', 100, 8.00),
  BUY('2023-05-20', 100, 6.00),
], { disposals: [{ gain: 200.00, via: '30-day' }], pool: { shares: 200, avg: 5.00 } });

// CASE 4 — One sale split across all three rules, in priority order.
//   Pool seed: 100 @ £2. On 2023-06-15 buy 30 @ £10 AND sell 100 @ £12.
//   Then buy 20 @ £11 on 2023-07-10 (25 days later, inside the window).
//   Match the 100 sold:  30 same-day @ £10 = £300
//                        20 30-day  @ £11 = £220
//                        50 pool    @ £2  = £100   (pool was 100 @ £2)
//   Cost £620, proceeds £1,200  →  gain £580.00. Pool left: 50 @ £2.
runCGT('priority: same-day + 30-day + pool', [
  BUY('2020-01-01', 100, 2.00),
  BUY('2023-06-15', 30, 10.00),
  SELL('2023-06-15', 100, 12.00),
  BUY('2023-07-10', 20, 11.00),
], { disposals: [{ gain: 580.00, via: 'Same-day 30 + 30-day 20 + Pool 50' }], pool: { shares: 50, avg: 2.00 } });

// CASE 5 — Loss-making disposal empties the pool.
//   Buy 100 @ £10 (= £1,000). Sell 100 @ £6 = £600  →  loss £400.00. Pool empty.
runCGT('loss + pool drained to zero', [
  BUY('2021-01-01', 100, 10.00),
  SELL('2023-01-01', 100, 6.00),
], { disposals: [{ gain: -400.00, via: 'Pool' }], pool: { shares: 0 } });

// CASE 6 — Just outside the 30-day window falls to the pool, not bed & breakfast.
//   Hold 100 @ £4. Sell 100 @ £9 on 2023-03-01, buy 100 @ £5 on 2023-04-05
//   (35 days later — OUTSIDE 30 days). So the sale draws from the pool (100 @ £4):
//   cost £400, proceeds £900  →  gain £500.00. The later buy then forms the pool:
//   100 @ £5 remain.
runCGT('31+ days is NOT bed & breakfast', [
  BUY('2021-02-01', 100, 4.00),
  SELL('2023-03-01', 100, 9.00),
  BUY('2023-04-05', 100, 5.00),
], { disposals: [{ gain: 500.00, via: 'Pool' }], pool: { shares: 100, avg: 5.00 } });

// ---- vesting-log parser: cost basis uses DELIVERED (released) shares -------
// RSU vests are taxed/based on the shares actually delivered to you, net of any
// withheld-for-tax shares you never receive (so they must not enter the pool).
(function vestingBasis() {
  const csv = [
    'Date,Symbol,From Grant,Instrument,Shares Vested,Shares Released (delivered),Withheld for Tax,% Withheld',
    '2023-04-01,ROKU,12345,Restricted Stock,100,60,40,40',
  ].join('\n');
  const parsed = parseVestingLog(csv);
  const before = failed;
  eq(parsed.newEntries.length, 1, 'vesting basis: one RSU acquisition');
  if (parsed.newEntries[0]) {
    near(parsed.newEntries[0].qty, 60, SHARE_TOL, 'vesting basis: acquires DELIVERED qty (60, not 100)');
    eq(parsed.newEntries[0].action, 'acquire', 'vesting basis: action is acquire');
  }
  near(parsed.withheldTotal, 40, SHARE_TOL, 'vesting basis: 40 shares excluded as withheld');
  console.log(`  ${failed === before ? '✓' : '✗'} delivered-shares cost basis (s.119A / HS287)`);
})();

// ---- ESPP / OSPS parser: each lot enters the pool at its OWN file cost basis ----
// The multi-tab BenefitHistory.xlsx (P&G-style) carries explicit per-share cost for
// ESPP purchases and OSPS dividend-reinvestment lots, so they don't depend on a Yahoo
// close. ESPP base = market value at purchase (price paid when 0% discount; the
// income-taxed FMV when discounted). OSPS base = the stated cost basis per share.
(function esppOspsParser() {
  const sheets = {
    'ESPP': [
      ['Record Type', 'Symbol', 'Purchase Date', 'Purchase Price', 'Purchased Qty.',
        'Tax Collection Shares', 'Net Shares', 'Discount Percent', 'Grant Date FMV', 'Purchase Date FMV'],
      // 0% discount: base = price paid, kept at full precision.
      ['Purchase', 'PG', '05-APR-2022', '156.6915', '1.348', '0', '1.348', '0%', '156.6915', '$156.69'],
      // 15% discount: paid £85 but income-taxed on the £100 FMV -> CGT base = £100.
      ['Purchase', 'PG', '15-JAN-2021', '85.00', '10', '0', '10', '15%', '100.00', '$100.00'],
      ['Event', '', '', '', '', '', '', '', '', ''],   // sub-row: must be ignored
    ],
    'OSPS': [
      ['Record Type', 'Symbol', 'Acquired Date', 'Cost Basis per share', 'Acquired Qty.'],
      ['Acquisition', 'PG', '15-AUG-2024', '168.511691', '4.448'],
    ],
  };
  const before = failed;
  const { entries, symbol, earliest } = benefitPurchaseEntries(sheets);
  eq(entries.length, 3, 'espp/osps: 2 ESPP + 1 OSPS (Event row ignored)');
  const espp = entries.filter(e => e.type === 'ESPP');
  const osps = entries.filter(e => e.type === 'OSPS');
  if (espp[0]) {
    eq(espp[0].date, '2022-04-05', 'espp: DD-MON-YYYY date parsed');
    near(espp[0].qty, 1.348, SHARE_TOL, 'espp: qty from Net Shares');
    near(espp[0].price, 156.6915, MONEY_TOL, 'espp: 0% discount uses full-precision price paid');
  }
  if (espp[1]) near(espp[1].price, 100.00, MONEY_TOL, 'espp: discounted lot uses FMV (£100), not price paid (£85)');
  if (osps[0]) {
    eq(osps[0].date, '2024-08-15', 'osps: date parsed');
    near(osps[0].qty, 4.448, SHARE_TOL, 'osps: qty from Acquired Qty.');
    near(osps[0].price, 168.511691, MONEY_TOL, 'osps: stated cost basis per share');
  }
  eq(symbol, 'PG', 'espp/osps: symbol detected');
  eq(earliest, '2021-01-15', 'espp/osps: earliest acquisition date');
  console.log(`  ${failed === before ? '✓' : '✗'} ESPP & OSPS lots pooled at file cost basis`);
})();

// ======================================================================
console.log(`\n${passed} checks passed, ${failed} failed.`);
if (failed) {
  console.log('\nFailures:');
  failures.forEach(f => console.log('  - ' + f));
  process.exit(1);
}
console.log('All parity tests passed. ✓\n');
