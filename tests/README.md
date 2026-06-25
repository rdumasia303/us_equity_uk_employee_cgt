# Parity tests

Proof that the CGT engine computes UK capital gains correctly.

`parity.js` loads the **actual** calculation engine out of `../index.html` (no
copy, no mock) and runs it against scenarios that are hand-computed to the
statute. Each case shows its arithmetic in-line so the expected figures can be
checked independently, and cites the rule it exercises:

| Rule | Statute | HMRC manual |
|------|---------|-------------|
| Same-day matching | TCGA 1992 s.105 | CG51560 |
| 30-day "bed & breakfast" | TCGA 1992 s.106A | CG51560 |
| Section 104 pool (average cost) | TCGA 1992 s.104 | CG51575, HS284 |
| Cost basis = value at vest (delivered shares) | TCGA 1992 s.119A | HS287, ERSM110000 |

The suite also checks the strict **priority order** (same-day → 30-day → pool)
when a single disposal splits across all three, the 30-day window **boundary**
(31 days falls to the pool, not bed & breakfast), loss-making disposals, and
that RSU cost basis uses the **delivered** quantity (net of shares withheld for
tax, which never enter the pool).

It also covers the **ESPP** and **OSPS** tabs of a multi-tab `BenefitHistory.xlsx`:
each lot enters the Section 104 pool at its **own** per-share cost basis from the
file (no Yahoo close needed). ESPP base cost is the market value at purchase (the
price paid where the plan is undiscounted; the income-taxed FMV where it isn't);
OSPS (dividend-reinvestment) lots use the stated cost basis per share.

## Run

```bash
node tests/parity.js
```

No dependencies. Exit code `0` = all pass, `1` = a failure (with details).
