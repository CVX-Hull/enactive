#!/usr/bin/env python3
"""Snapshot-diff cost estimate over sealed host traces (#455; read-only, no model calls).

Usage: python tools/diff_cost.py <computer-sessions directory>
e.g.   python tools/diff_cost.py .runtime/evidence/397-seven-day/computer-sessions

Reads every `response-complete` event's usage and configured-rate cost from
<dir>/*/actors/*/host.jsonl and prints measured quantities and the per-diff cost model.
"Spend per request" is pooled spend over model requests (not decisions).
Record: docs/design/snapshot-diff-cost.md.
"""
import glob, json, os, statistics as st, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.runtime/evidence/397-seven-day/computer-sessions'
DIFFS = [50, 200, 500, 2000]

def pct(xs, p):
    xs = sorted(xs)
    if not xs: return float("nan")
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)

def med(xs): return st.median(xs) if xs else float("nan")

def slope(ys):
    n = len(ys)
    if n < 2: return float("nan")
    xm = (n - 1) / 2; ym = sum(ys) / n
    return sum((i - xm) * (y - ym) for i, y in enumerate(ys)) / sum((i - xm) ** 2 for i in range(n))

actors = {}
for f in sorted(glob.glob(ROOT + "/*/actors/*/host.jsonl")):
    name = f.split("computer-sessions/")[1].replace("/actors/", "/").replace("/host.jsonl", "")
    reqs, toolbytes = [], []
    for line in open(f):
        d = json.loads(line)
        if d["type"] == "response-complete" and d.get("usage_available"):
            u = d["usage"]; c = u["cost"]
            reqs.append(dict(inp=u["input"], cr=u["cacheRead"], cw=u["cacheWrite"], out=u["output"],
                             c_in=c["input"], c_cr=c["cacheRead"], c_cw=c["cacheWrite"], c_out=c["output"], c_tot=c["total"],
                             reasoning=u.get("reasoning", 0)))
        elif d["type"] == "tool-result":
            try:
                toolbytes.append(sum(len(b.get("text", "")) for b in d["result"]["content"] if b.get("type") == "text"))
            except Exception:
                pass
    actors[name] = (reqs, toolbytes)

def prompt(r): return r["inp"] + r["cr"] + r["cw"]

def stats(reqs):
    P = [prompt(r) for r in reqs]
    big_all = [r["cw"] > 0.5 * prompt(r) for r in reqs]
    big_ex1 = big_all[1:]
    return dict(n=len(reqs), P=P, big_all=sum(big_all), big_ex1=sum(big_ex1))

# --- prices -----------------------------------------------------------------
def prices(reqs):
    out = {}
    for k, ck, uk in [("input", "c_in", "inp"), ("cacheRead", "c_cr", "cr"), ("cacheWrite", "c_cw", "cw"), ("output", "c_out", "out")]:
        pr = [r[ck] / r[uk] * 1e6 for r in reqs if r[uk] > 0]
        out[k] = (min(pr), max(pr), med(pr)) if pr else (float("nan"),) * 3
    return out

allreqs = [r for rs, _ in actors.values() for r in rs]
print("=== EFFECTIVE PRICES ($/Mtok) implied by usage.cost / usage.<field>  (min, max, median over requests with field>0) ===")
pp = prices(allreqs)
for k, v in pp.items(): print(f"pooled {k:10s} min={v[0]:.6f} max={v[1]:.6f} median={v[2]:.6f}")
incons = 0
for n, (rs, _) in actors.items():
    p = prices(rs)
    for k, v in p.items():
        if abs(v[1] - v[0]) > 1e-6 * max(1, v[1]): incons += 1; print("INCONSISTENT", n, k, v)
print("inconsistent (actor,field) pairs:", incons)
# total check
chk = max(abs(r["c_in"] + r["c_out"] + r["c_cr"] + r["c_cw"] - r["c_tot"]) for r in allreqs)
print("max |sum(components)-total| over all requests: %.3g" % chk)
PR = {k: v[2] for k, v in pp.items()}   # $/Mtok
pr_r, pr_w, pr_i, pr_o = PR["cacheRead"], PR["cacheWrite"], PR["input"], PR["output"]
print(f"write/read price ratio = {pr_w/pr_r:.3f}; write/input ratio = {pr_w/pr_i:.3f}")

# --- per-actor ------------------------------------------------------------
print("\n=== PER-ACTOR (tokens per request: median / p90) ===")
hdr = f"{'actor':14s}{'req':>5s} | {'input med/p90':>14s} | {'cacheRead med/p90':>19s} | {'cacheWrite med/p90':>20s} | {'output med/p90':>15s} | {'prompt med/p90':>17s} | {'bigRW all':>9s} {'ex1st':>6s} | {'$total':>8s} {'$/req':>8s}"
print(hdr)
def row(name, reqs):
    s = stats(reqs)
    f = lambda k: f"{med([r[k] for r in reqs]):.0f}/{pct([r[k] for r in reqs],90):.0f}"
    tot = sum(r["c_tot"] for r in reqs)
    print(f"{name:14s}{s['n']:5d} | {f('inp'):>14s} | {f('cr'):>19s} | {f('cw'):>20s} | {f('out'):>15s} | {med(s['P']):.0f}/{pct(s['P'],90):.0f}".ljust(0) .replace("|  ", "| ") +
          f" | {s['big_all']/s['n']*100:8.1f}% {s['big_ex1']/(s['n']-1)*100:5.1f}% | {tot:8.4f} {tot/s['n']:8.5f}")
for n, (rs, _) in actors.items(): row(n, rs)
row("POOLED", allreqs)

# --- growth ------------------------------------------------------------------
print("\n=== PROMPT SIZE GROWTH across requests (prompt = input+cacheRead+cacheWrite) ===")
print(f"{'actor':14s}{'first':>8s}{'last':>8s}{'max':>8s}{'slope tok/req':>14s}{'med delta':>10s}{'mean delta':>11s}{'#drops':>7s}")
for n, (rs, _) in actors.items():
    P = [prompt(r) for r in rs]; d = [b - a for a, b in zip(P, P[1:])]
    print(f"{n:14s}{P[0]:8d}{P[-1]:8d}{max(P):8d}{slope(P):14.1f}{med(d):10.0f}{sum(d)/len(d):11.1f}{sum(1 for x in d if x < 0):7d}")
sl = [slope([prompt(r) for r in rs]) for rs, _ in actors.values()]
print(f"median over actors of slope: {med(sl):.1f} tok/req; mean {sum(sl)/len(sl):.1f}")

# --- large rewrite detail ------------------------------------------------------
print("\n=== LARGE REWRITE definition: cacheWrite > 0.5 * (input+cacheRead+cacheWrite) on that request ===")
allbig = [(r, prompt(r)) for rs, _ in actors.values() for r in rs[1:] if r["cw"] > 0.5 * prompt(r)]
tot_ex1 = sum(len(rs) - 1 for rs, _ in actors.values())
print(f"pooled: {len(allbig)} of {tot_ex1} non-first requests ({len(allbig)/tot_ex1*100:.2f}%)")
if allbig: print("median prompt size on large-rewrite requests:", med([p for _, p in allbig]), " median cacheWrite:", med([r['cw'] for r, _ in allbig]))
# where is the cost?
cw_cost = sum(r["c_cw"] for r in allreqs); cr_cost = sum(r["c_cr"] for r in allreqs); tot = sum(r["c_tot"] for r in allreqs)
in_cost = sum(r["c_in"] for r in allreqs); out_cost = sum(r["c_out"] for r in allreqs)
big_cost = sum(r["c_tot"] for r, _ in allbig)
print(f"pooled spend ${tot:.4f}: cacheWrite {cw_cost/tot*100:.1f}%, cacheRead {cr_cost/tot*100:.1f}%, input {in_cost/tot*100:.2f}%, output {out_cost/tot*100:.1f}%")
print(f"large-rewrite requests account for {big_cost/tot*100:.1f}% of spend")
# non-large request: new tokens per request (cw) typical
small = [r["cw"] for rs, _ in actors.values() for r in rs[1:] if r["cw"] <= 0.5 * prompt(r)]
print(f"non-large requests: median cacheWrite {med(small):.0f}, p90 {pct(small,90):.0f}; share of prompt that is cacheRead median {med([r['cr']/prompt(r) for rs,_ in actors.values() for r in rs[1:]])*100:.1f}%")

# --- tool-result text sizes ---------------------------------------------------
tb = [b for _, t in actors.values() for b in t]
print(f"\ntool-result text bytes: n={len(tb)} median={med(tb):.0f} p90={pct(tb,90):.0f} (bytes; /4 is only a rough token heuristic; images are separate and not in this)")

# --- remaining requests ------------------------------------------------------
print("\n=== REQUESTS PER ACTOR / later requests after an append at request i ===")
ns = [len(rs) for rs, _ in actors.values()]
print(f"requests per actor: min={min(ns)} median={med(ns):.0f} mean={sum(ns)/len(ns):.1f} max={max(ns)}")
# mean later requests for a diff appended at uniformly random request i (i=1..n, later = n-i)
remaining_all = [len(rs) - i for rs, _ in actors.values() for i in range(1, len(rs) + 1)]
R_mean = sum(remaining_all) / len(remaining_all)
print(f"pooled mean later-requests for a token appended at a uniformly random request: {R_mean:.1f} (median {med(remaining_all):.0f})")
print("per actor mean (n-1)/2:", {k: round((len(v[0]) - 1) / 2, 1) for k, v in actors.items()})

# --- model --------------------------------------------------------------------
q = len(allbig) / tot_ex1          # P(large rewrite on a given non-first request)
spend_per_request = tot / len(allreqs)
R_med = med(remaining_all)
print("\n=== COST MODEL ===")
print(f"Prices used ($/Mtok): write={pr_w:.4f} read={pr_r:.4f} input={pr_i:.4f}; large-rewrite rate q={q:.4f}/request; measured spend/reqision=${spend_per_request:.5f}")
print("Assumption: a diff of D tokens joins the next request as new tokens billed at the WRITE price (consistent with: non-large requests' new tokens appear as cacheWrite, input is ~3 tok),")
print("then each of the R later requests bills it at READ price (a); in (b) in each later request with prob q the whole prompt incl. the diff is rewritten: extra D*(write-read) per rewrite event.")
print("Baseline-comparison: costs below are ADDED relative to a run without the diff. Output/latency effects not modelled.")
def line(R, label):
    print(f"\n-- R = {R:.1f} later requests ({label}) --")
    print(f"{'D':>6s} | {'(a) $':>10s} {'(a) %spend/req':>15s} | {'(b) $':>10s} {'(b) %spend/req':>15s} | {'(b) worst: every later req rewrites $':>38s}")
    for D in DIFFS:
        a = D * pr_w / 1e6 + R * D * pr_r / 1e6
        b = a + R * q * D * (pr_w - pr_r) / 1e6
        worst = a + R * D * (pr_w - pr_r) / 1e6
        print(f"{D:6d} | {a:10.6f} {a/spend_per_request*100:14.2f}% | {b:10.6f} {b/spend_per_request*100:14.2f}% | {worst:10.6f} ({worst/spend_per_request*100:.1f}%)")
line(R_mean, "pooled mean, uniform append time")
line(len(allreqs)/len(actors) - 1, "append at request 1 of a mean-length actor (upper bound for position)")
# per-actor spend per request, per diff
print("\nPer-actor (a)/(b) cost as % of the actor's own spend per request, R=(n-1)/2:")
print(f"{'actor':14s}" + "".join(f"{'D='+str(D)+' (a)':>12s}{'(b)':>8s}" for D in DIFFS))
for n, (rs, _) in actors.items():
    R = (len(rs) - 1) / 2; spd = sum(r["c_tot"] for r in rs) / len(rs)
    qa = sum(1 for r in rs[1:] if r["cw"] > 0.5 * prompt(r)) / (len(rs) - 1)
    cells = ""
    for D in DIFFS:
        a = D * pr_w / 1e6 + R * D * pr_r / 1e6; b = a + R * qa * D * (pr_w - pr_r) / 1e6
        cells += f"{a/spd*100:11.2f}%{b/spd*100:7.2f}%"
    print(f"{n:14s}{cells}")

print("\n=== ADDED PROMPT TOKENS per request after k diffs have accumulated (k*D) and as % of measured median / last prompt ===")
medP = med([prompt(r) for r in allreqs]); lastP = med([prompt(rs[-1]) for rs, _ in actors.values()])
print(f"pooled median prompt {medP:.0f}; median final prompt {lastP:.0f}; mean requests per actor {sum(ns)/len(ns):.0f}")
print(f"{'D':>6s}" + "".join(f"{'k='+str(k):>14s}" for k in [1, 5, 20, 50, 100]))
for D in DIFFS:
    print(f"{D:6d}" + "".join(f"{k*D:8d}({k*D/medP*100:4.0f}%)" for k in [1, 5, 20, 50, 100]))
print("\n(per-request $ steady-state cost of holding k*D tokens at read price, per request:)")
for D in DIFFS:
    print(f"D={D:5d}: " + "  ".join(f"k={k}: ${k*D*pr_r/1e6:.5f} ({k*D*pr_r/1e6/spend_per_request*100:.1f}% of spend/req)" for k in [1, 5, 20, 50]))

# --- probe estimate ------------------------------------------------------------
print("\n=== PROBE COST ESTIMATE (not run) ===")
for P in [medP, lastP]:
    cold = P * pr_w / 1e6; warm = P * pr_r / 1e6
    print(f"one request at prompt={P:.0f}: cold write ${cold:.4f}, warm read ${warm:.4f}")
print("Probe sketch: replay one actor's prompt of ~median size, then 20 follow-up requests each appending a 500-token diff (+ varying inter-request gaps).")
P = medP; D = 500; N = 20
cost = P * pr_w / 1e6 + N * (P * pr_r / 1e6 + D * pr_w / 1e6 + 20 * pr_o / 1e6)
print(f"estimated: ${cost:.3f} per run at median prompt (20 requests, +{D} tok each, 20 output tok); x3 gap conditions = ${3*cost:.3f}")

# --- do large rewrites coincide with prompt shrinkage (context pruning)? ----------
print("\n=== LARGE REWRITE vs PROMPT DROP (prompt smaller than previous request) ===")
bb = bd = dd = nn = 0
for rs, _ in actors.values():
    P = [prompt(r) for r in rs]
    for i in range(1, len(rs)):
        big = rs[i]["cw"] > 0.5 * P[i]; drop = P[i] < P[i - 1]
        nn += 1; bb += big and drop; bd += big and not drop; dd += drop and not big
print(f"of {nn} non-first requests: large&drop={bb}, large&no-drop={bd}, drop&not-large={dd}")
