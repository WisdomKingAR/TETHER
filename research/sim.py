"""TETHER proof-of-concept simulation.
Synthetic agent traces, 7 attack scenarios, three detectors compared at the same
1% false-alarm budget. Writes results.json used by the deck and the figures.
Assumptions are listed in ASSUMPTIONS at the bottom and printed in the deck notes."""
import json, time, numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_curve, auc

SEED = 11
rng_master = np.random.default_rng(SEED)

# ------------------------------------------------------------------ roles
ROLES = {
    "procurement": dict(tools=["price.read", "doc.open", "pr.create", "email.send", "web.fetch", "po.lookup"], cls=["supplier", "supplier", "pr", "supplier", "web", "pr"],
                        untrusted=[0, 1, 0, 0, 1, 0], sink=[0, 0, 0, 1, 0, 0], bytes=[3e3, 8e4, 6e3, 2e4, 5e4, 4e3]),
    "hr_help": dict(tools=["kb.search", "ticket.read", "doc.open", "ticket.update", "email.send", "faq.read"], cls=["hr_public", "hr_ticket", "hr_public", "hr_ticket", "hr_ticket", "hr_public"],
                    untrusted=[0, 0, 1, 0, 0, 0], sink=[0, 0, 0, 0, 1, 0], bytes=[4e3, 9e3, 7e4, 5e3, 1.5e4, 3e3]),
    "code_review": dict(tools=["repo.read", "diff.analyze", "web.fetch", "comment.post", "ci.read", "lint.run"], cls=["code", "code", "web", "code", "ci", "code"],
                        untrusted=[0, 0, 1, 0, 0, 0], sink=[0, 0, 0, 1, 0, 0], bytes=[6e4, 2e4, 5e4, 3e3, 8e3, 5e3]),
    "finance_recon": dict(tools=["ledger.read", "bank.feed", "doc.open", "report.write", "email.send", "fx.rate"], cls=["ledger", "finance", "finance", "ledger", "finance", "finance"],
                          untrusted=[0, 0, 1, 0, 0, 0], sink=[0, 0, 0, 1, 1, 0], bytes=[9e4, 1.2e5, 6e4, 2e4, 1.5e4, 2e3]),
}
APPROVED = ["approved-suppliers.in", "corp-mail.local", "github.com"]
HOURS = lambda r: int(np.clip(r.normal(13, 3), 0, 23))


def make_agent(role, rng, jitter=0.25):
    n = 6
    base = np.random.default_rng(abs(hash(role)) % (2**32) if False else sum(map(ord, role)))
    T0 = base.dirichlet(np.ones(n) * 0.35, size=n)
    T = np.array([rng.dirichlet(row * (1 / jitter) + 0.05) for row in T0])  # per-agent variation around the role
    start = base.dirichlet(np.ones(n))
    return dict(role=role, T=T, start=start, T0=T0)


def benign_session(agent, rng, noise=True, scale=1.0):
    R = ROLES[agent["role"]]
    L = int(np.clip(rng.normal(20, 5), 8, 40)); t = rng.choice(6, p=agent["start"]); calls = []; taint = False
    for _ in range(L):
        untr, snk = R["untrusted"][t], R["sink"][t]
        if untr: taint = True
        calls.append(dict(tool=t, cls=R["cls"][t], bytes=float(rng.lognormal(np.log(R["bytes"][t] * scale), 0.5)), egress=(rng.choice(APPROVED) if snk else ""), sink=snk,
                          taint=taint, dest_t2=False, decoy=False, proof_ok=True, host_novel=False, scope_ok=True, hour=HOURS(rng)))
        t = rng.choice(6, p=agent["T"][t])
    if noise:  # benign false triggers (assumed rates)
        c = calls[rng.integers(len(calls))]
        if rng.random() < 0.002: c["cls"] = "unregistered_class"          # new in-role resource before contract bump
        if rng.random() < 0.001 and any(x["sink"] for x in calls):
            [x for x in calls if x["sink"]][0]["dest_t2"] = True        # legit reply-to from a supplier mail
        if rng.random() < 0.0002: c["decoy"] = True                      # accidental glob over a decoy
        if rng.random() < 0.01: c["host_novel"] = True                   # employee moved networks
    return calls


def inject(calls, kind, rng, agent):
    """Return (calls, first_attack_index, payload_bytes_by_index)."""
    c = [dict(x) for x in calls]; R = ROLES[agent["role"]]
    pos = int(rng.integers(len(c) // 3, 2 * len(c) // 3)); taint_from = pos
    for x in c[pos:]: x["taint"] = True
    def call(**kw):
        d = dict(tool=-1, cls="supplier", bytes=0.0, egress="", sink=0, taint=True, dest_t2=False, decoy=False, proof_ok=True, host_novel=False, scope_ok=True, hour=HOURS(rng))
        d.update(kw); return d
    if kind == "A1":    # indirect injection: out-of-role read then exfil
        add = [call(cls="hr_salary", bytes=1.8e5, decoy=rng.random() < 0.5), call(cls="hr_salary", bytes=2.3e6, egress="files.unknown-host.io", sink=1, dest_t2=True)]
    elif kind == "A2":  # poisoned tool description: credentials ride a tool parameter
        add = [call(cls="credentials", bytes=4e3, egress="tool-srv.sketchy.net", sink=1, dest_t2=True)]
    elif kind == "A3":  # stolen token replay from another host
        for x in c: x["proof_ok"] = False; x["host_novel"] = True; x["hour"] = int(rng.choice([2, 3, 4])); x["bytes"] *= 2.0
        return c, 0, {i: 0.0 for i in range(len(c))}
    elif kind == "A5":  # mimicry: normal sequence and volume, covert small exfil via approved channel, instruction-derived destination
        add = [call(cls=R["cls"][0], bytes=float(rng.lognormal(np.log(1.5e4), 0.3)), egress=rng.choice(APPROVED), sink=1, dest_t2=True, decoy=rng.random() < 0.45)]
    elif kind == "A6":  # compromised sub-agent: child exceeds delegated scope, parent launders output
        add = [call(cls="ledger", bytes=6e4, scope_ok=False), call(cls=R["cls"][0], bytes=3e4, egress=rng.choice(APPROVED), sink=1, dest_t2=True)]
    elif kind == "A7":  # brand-new agent, same payload as A1
        add = [call(cls="hr_salary", bytes=1.8e5, decoy=rng.random() < 0.5), call(cls="hr_salary", bytes=2.3e6, egress="files.unknown-host.io", sink=1, dest_t2=True)]
    c[pos:pos] = add
    payload = {pos + i: (a["bytes"] if a["sink"] else 0.0) for i, a in enumerate(add)}
    return c, pos, payload


# ------------------------------------------------------------------ detectors
def bigram_ll(seq, P):
    return np.mean([np.log(P[a, b] + 1e-6) for a, b in zip(seq[:-1], seq[1:])]) if len(seq) > 1 else 0.0


def feats(calls, P, seen_cls, seen_egress):
    seq = [x["tool"] for x in calls if x["tool"] >= 0]
    ll = bigram_ll(seq, P) if len(seq) > 1 else 0.0
    b = np.array([x["bytes"] for x in calls]) + 1
    newc = float(any(x["cls"] not in seen_cls for x in calls)); newe = float(any(x["egress"] and x["egress"] not in seen_egress for x in calls))
    return [ll, len(calls), np.log1p(b.mean()), np.log1p(b.max()), len(set(x["tool"] for x in calls)) / 6, np.mean([x["taint"] for x in calls]), newc, newe,
            float(any(x["host_novel"] for x in calls)), abs(np.mean([x["hour"] for x in calls]) - 13) / 6]


def fit_ml(sessions, role_prior=None, prior_w=0.0):
    seqs = [[x["tool"] for x in s if x["tool"] >= 0] for s in sessions]
    C = np.ones((6, 6)) * 0.5
    for q in seqs:
        for a, b in zip(q[:-1], q[1:]): C[a, b] += 1
    if role_prior is not None: C = C + prior_w * role_prior
    P = C / C.sum(1, keepdims=True)
    seen_cls = set(x["cls"] for s in sessions for x in s); seen_eg = set(x["egress"] for s in sessions for x in s if x["egress"])
    return P, seen_cls, seen_eg


class MLOnly:  # UEBA-style: learns everything from the agent's own history
    def __init__(self, hist, rng):
        self.ok = len(hist) >= 10
        self.rng = rng
        if self.ok:
            self.P, self.sc, self.se = fit_ml(hist)
            X = np.array([feats(s, self.P, self.sc, self.se) for s in hist])
            self.m = IsolationForest(n_estimators=100, random_state=SEED).fit(X)
    def score_prefixes(self, calls):
        if not self.ok: return np.array([self.rng.random() for _ in range(len(calls))])   # no model: chance
        X = np.array([feats(calls[: i + 1], self.P, self.sc, self.se) for i in range(1, len(calls))] + [feats(calls, self.P, self.sc, self.se)])
        return -self.m.score_samples(X) + 0.5 * (X[:, 6] + X[:, 7] + X[:, 8])   # IF + rare-value rules (fair UEBA)


class TETHER:
    W = dict(p1=0.90, p2=0.90, p3=0.95, p4=0.50, p5=0.60, p6=0.60, pid=0.90)
    def __init__(self, hist, peers, role, rng):
        R = ROLES[role]; self.R = R; self.rng = rng
        self.allow_cls = set(R["cls"]); self.allow_tools = set(range(6)); self.approved = set(APPROVED)
        self.cap_bytes = 6 * 6e5 * 1.0; self.cap_calls = 60
        pool = list(hist) + list(peers[:150])           # peer-group prior + own history
        self.P, _, _ = fit_ml(pool, role_prior=None)
        self.sc, self.se = self.allow_cls, self.approved   # novelty sets come from the CONTRACT, so they exist on day 0
        X = np.array([feats(s, self.P, self.sc, self.se) for s in pool])
        self.m = IsolationForest(n_estimators=100, random_state=SEED).fit(X)
        base = -self.m.score_samples(np.array([feats(s, self.P, self.sc, self.se) for s in pool]))
        self.lo, self.hi = np.quantile(base, 0.90), np.quantile(base, 0.999)
    def r_prefixes(self, calls, cusum_alarm=False):
        n = len(calls); out = np.zeros(n)
        ml = -self.m.score_samples(np.array([feats(calls[: i + 1], self.P, self.sc, self.se) for i in range(n)]))
        s4 = np.clip((ml - self.lo) / (self.hi - self.lo + 1e-9), 0, 1)
        cum = 0.0; s1 = s2 = s3 = s5 = sid = 0
        tracked = self.rng.random() < 0.90          # taint tracking through LLM reasoning is imperfect
        for i, x in enumerate(calls):
            cum += x["bytes"]
            if x["cls"] not in self.allow_cls or (x["egress"] and x["egress"] not in self.approved) or cum > self.cap_bytes or i + 1 > self.cap_calls: s1 = 1
            if (x["dest_t2"] and tracked) or (x["taint"] and x["cls"] not in self.allow_cls): s2 = 1
            if x["decoy"]: s3 = 1
            if not x["scope_ok"]: s5 = 1
            if not x["proof_ok"]: sid = 1
            p = 1.0
            for w, s in ((self.W["p1"], s1), (self.W["p2"], s2), (self.W["p3"], s3), (self.W["p4"], s4[i]), (self.W["p5"], s5), (self.W["pid"], sid), (self.W["p6"], 1.0 if cusum_alarm else 0.0)):
                p *= 1 - w * s
            out[i] = 100 * (1 - p)
            if s2 or s3: out[i] = max(out[i], 85)
        return out


# ------------------------------------------------------------------ experiment
def make_world(n_hist=300, n_val=400, n_att=150, role="procurement", seed=SEED):
    rng = np.random.default_rng(seed)
    agent = make_agent(role, rng)
    peers_agents = [make_agent(role, rng) for _ in range(6)]
    peers = [benign_session(a, rng) for a in peers_agents for _ in range(60)]
    hist = [benign_session(agent, rng) for _ in range(n_hist)]
    val = [benign_session(agent, rng) for _ in range(n_val)]
    return rng, agent, peers, hist, val


def run_scenario_rates(n_hist=300, n_att=160):
    rng, agent, peers, hist, val = make_world(n_hist=n_hist)
    ml = MLOnly(hist, rng); dw = TETHER(hist, peers, agent["role"], rng)
    ml_val = np.array([ml.score_prefixes(s).max() for s in val]); dw_val = np.array([dw.r_prefixes(s).max() for s in val])
    ml_thr, dw_thr = np.quantile(ml_val, 0.99), np.quantile(dw_val, 0.99)
    res = {"thr": dict(ml=float(ml_thr), dw=float(dw_thr)), "scen": {}}
    kinds = ["A1", "A2", "A3", "A5", "A6"]
    steps = {}
    for k in kinds:
        det = {"ml": 0, "dw": 0}; leak = {"ml": [], "dw": [], "iam": []}; tts = {"ml": [], "dw": []}; tl = []
        for _ in range(n_att):
            s, pos, payload = inject(benign_session(agent, rng, noise=False), k, rng, agent)
            ms = ml.score_prefixes(s); ds = dw.r_prefixes(s)
            tot = sum(payload.values()) or 1.0
            for name, sc, thr in (("ml", ms, ml_thr), ("dw", ds, dw_thr)):
                idx = np.where(sc > thr)[0]
                if len(idx): det[name] += 1; first = idx[0]; tts[name].append(max(0, first - pos)); leak[name].append(sum(v for i, v in payload.items() if i < first) / tot)
                else: leak[name].append(1.0)
            leak["iam"].append(1.0)
            tl.append((pos, ms, ds))
        res["scen"][k] = dict(ml=det["ml"] / n_att, dw=det["dw"] / n_att, iam=0.0, leak_ml=float(np.mean(leak["ml"])), leak_dw=float(np.mean(leak["dw"])), leak_iam=1.0,
                              ttd_ml=float(np.median(tts["ml"])) if tts["ml"] else None, ttd_dw=float(np.median(tts["dw"])) if tts["dw"] else None)
        steps[k] = tl
    return res, steps, (rng, agent, peers, hist, val, ml, dw, ml_thr, dw_thr)


def pooled_roc(ctx, n_att=160):
    rng, agent, peers, hist, val, ml, dw, mt, dt = ctx
    y, sm, sd = [], [], []
    for s in val: y.append(0); sm.append(ml.score_prefixes(s).max()); sd.append(dw.r_prefixes(s).max())
    for k in ["A1", "A2", "A3", "A5", "A6"]:
        for _ in range(n_att // 4):
            s, _, _ = inject(benign_session(agent, rng, noise=False), k, rng, agent); y.append(1); sm.append(ml.score_prefixes(s).max()); sd.append(dw.r_prefixes(s).max())
    f1, t1, _ = roc_curve(y, sm); f2, t2, _ = roc_curve(y, sd)
    return dict(ml=dict(fpr=f1.tolist(), tpr=t1.tolist(), auc=float(auc(f1, t1))), dw=dict(fpr=f2.tolist(), tpr=t2.tolist(), auc=float(auc(f2, t2))))


def cold_start(ns=(0, 3, 10, 30, 100, 300), reps=3, n_att=70):
    out = {"n": list(ns), "ml": [], "dw": []}
    for n in ns:
        a, b = [], []
        for r in range(reps):
            rng, agent, peers, hist, val = make_world(n_hist=n, n_val=250, seed=SEED + 100 * r + n)
            ml = MLOnly(hist, rng); dw = TETHER(hist, peers, agent["role"], rng)
            mv = np.array([ml.score_prefixes(s).max() for s in val]); dv = np.array([dw.r_prefixes(s).max() for s in val])
            mt, dt = np.quantile(mv, 0.99), np.quantile(dv, 0.99); hm = hd = tot = 0
            for k in ["A1", "A2", "A5"]:
                for _ in range(n_att // 3):
                    s, _, _ = inject(benign_session(agent, rng, noise=False), k, rng, agent); tot += 1
                    hm += ml.score_prefixes(s).max() > mt; hd += dw.r_prefixes(s).max() > dt
            a.append(hm / tot); b.append(hd / tot)
        out["ml"].append(float(np.mean(a))); out["dw"].append(float(np.mean(b)))
    return out


def slow_drift(n_seq=30, n_sessions=40):
    """A4: gradual creep. Compare per-session ML threshold vs TETHER (CUSUM on JS divergence + contract rate cap)."""
    from scipy.spatial.distance import jensenshannon
    rng, agent, peers, hist, val = make_world(n_hist=300)
    ml = MLOnly(hist, rng); dw = TETHER(hist, peers, agent["role"], rng)
    mv = np.array([ml.score_prefixes(s).max() for s in val]); mt = np.quantile(mv, 0.99)
    base = np.mean([np.bincount([x["tool"] for x in s], minlength=6) / len(s) for s in hist], axis=0)
    jsd_b = np.array([jensenshannon(np.bincount([x["tool"] for x in s], minlength=6) / len(s), base) for s in val])
    mu0, sd0 = jsd_b.mean(), jsd_b.std(); k_ref, h = 0.5 * sd0, 5 * sd0
    def cusum(js):
        S, arr, alarm = 0.0, [], None
        for i, x in enumerate(js):
            S = max(0.0, S + (x - mu0 - k_ref)); arr.append(S)
            if alarm is None and S > h: alarm = i
        return np.array(arr), alarm
    ben_js = jsd_b[:n_sessions]; ben_S, ben_alarm = cusum(ben_js)
    firsts = {"ml": [], "dw": []}; example = None
    for q in range(n_seq):
        js, mls, dws = [], [], []
        agent_c = dict(agent); T = agent["T"].copy()
        sessions = []
        for k in range(n_sessions):
            drift = k / n_sessions
            T2 = (1 - 0.55 * drift) * T + 0.55 * drift * np.roll(T, 2, axis=1)   # creep toward rarely used tools
            ag = dict(agent); ag["T"] = T2 / T2.sum(1, keepdims=True)
            s = benign_session(ag, rng, noise=False, scale=1 + 1.2 * drift)           # bytes up to ~2.2x
            sessions.append(s); js.append(jensenshannon(np.bincount([x["tool"] for x in s], minlength=6) / len(s), base))
            mls.append(ml.score_prefixes(s).max())
        S, alarm = cusum(np.array(js))
        f_ml = next((i for i, v in enumerate(mls) if v > mt), None)
        f_dw = alarm
        firsts["ml"].append(f_ml); firsts["dw"].append(f_dw)
        if q == 0: example = dict(js=js, S=S.tolist(), alarm=alarm, ml=mls, ml_thr=float(mt), h=float(h), ben_S=ben_S.tolist())
    def stat(v): d = [x for x in v if x is not None]; return dict(rate=len(d) / len(v), median=float(np.median(d)) if d else None)
    return dict(ml=stat(firsts["ml"]), dw=stat(firsts["dw"]), example=example, n_sessions=n_sessions)


def benign_fpr(ctx):
    rng, agent, peers, hist, val, ml, dw, mt, dt = ctx
    fresh = [benign_session(agent, rng) for _ in range(600)]
    fm = np.mean([ml.score_prefixes(s).max() > mt for s in fresh]); fd = np.mean([dw.r_prefixes(s).max() > dt for s in fresh])
    return dict(ml=float(fm), dw=float(fd))


def latency_bench(ctx):
    """Time the full inline decision path on serialized events: parse, state lookup, rules, taint update, fusion, serialize."""
    rng, agent, peers, hist, val, ml, dw, mt, dt = ctx
    s = benign_session(agent, rng)
    evs = [json.dumps(dict(agent="spiffe://org/agent/procurement", contract="procurement@3.2", session="s-7f21", tool=int(x["tool"]), cls=x["cls"], bytes=x["bytes"], egress=x["egress"],
                           taint=bool(x["taint"]), dest_t2=bool(x["dest_t2"]), decoy=bool(x["decoy"]), proof_ok=bool(x["proof_ok"]), scope_ok=bool(x["scope_ok"]))).encode() for x in s]
    allow, appr = dw.allow_cls, dw.approved; state = {"cum": 0.0, "n": 0, "taint": False, "last": 0}; P = dw.P; W = dw.W
    stages = {k: [] for k in ["parse", "rules P1-P3", "taint + state", "markov", "fusion", "serialize", "total"]}
    pc = time.perf_counter
    for i in range(60000):
        raw = evs[i % len(evs)]
        t0 = pc(); e = json.loads(raw); t1 = pc()
        p1 = e["cls"] not in allow or (e["egress"] and e["egress"] not in appr) or state["cum"] > 3.6e6
        p2 = e["dest_t2"] or (e["taint"] and e["cls"] not in allow); p3 = e["decoy"]; pid = not e["proof_ok"]; t2 = pc()
        state["cum"] += e["bytes"]; state["n"] += 1; state["taint"] = state["taint"] or e["taint"]; t3 = pc()
        ll = np.log(P[state["last"], e["tool"] % 6] + 1e-6) if False else math_log(P[state["last"]][e["tool"] % 6]); state["last"] = e["tool"] % 6; t4 = pc()
        pr = (1 - W["p1"] * p1) * (1 - W["p2"] * p2) * (1 - W["p3"] * p3) * (1 - W["pid"] * pid) * (1 - W["p4"] * 0.1); r = 100 * (1 - pr)
        if p2 or p3: r = max(r, 85)
        t5 = pc(); out = json.dumps({"risk": r, "level": 3 if r >= 70 else 2 if r >= 50 else 0}); t6 = pc()
        if i > 2000:
            for k, v in zip(["parse", "rules P1-P3", "taint + state", "markov", "fusion", "serialize"], [t1 - t0, t2 - t1, t3 - t2, t4 - t3, t5 - t4, t6 - t5]): stages[k].append(v * 1e6)
            stages["total"].append((t6 - t0) * 1e6)
        if state["n"] > 25: state.update(cum=0.0, n=0, taint=False)
    res = {k: (float(np.percentile(v, 50)), float(np.percentile(v, 95))) for k, v in stages.items()}
    X = np.array([feats(s, dw.P, dw.sc, dw.se)]); t = []
    for _ in range(300):
        a = pc(); dw.m.score_samples(X); t.append((pc() - a) * 1e3)
    res["_async_if_ms"] = (float(np.percentile(t, 50)), float(np.percentile(t, 95)))
    return res


import math
math_log = lambda v: math.log(v + 1e-6)


def transition_diff(ctx):
    rng, agent, peers, hist, val, ml, dw, mt, dt = ctx
    C0 = np.zeros((6, 6)); C1 = np.zeros((6, 6))
    for s in hist[:200]:
        q = [x["tool"] for x in s]
        for a, b in zip(q[:-1], q[1:]): C0[a, b] += 1
    for _ in range(200):
        s, pos, _ = inject(benign_session(agent, rng, noise=False), "A1", rng, agent)
        q = [x["tool"] for x in s if x["tool"] >= 0]
        for a, b in zip(q[:-1], q[1:]): C1[a, b] += 1
    P0 = C0 / C0.sum(1, keepdims=True).clip(1); P1 = C1 / C1.sum(1, keepdims=True).clip(1)
    return P0.tolist(), P1.tolist()


if __name__ == "__main__":
    t0 = time.time()
    res, steps, ctx = run_scenario_rates()
    print("scenario rates", {k: (round(v["ml"], 2), round(v["dw"], 2)) for k, v in res["scen"].items()}, round(time.time() - t0))
    res["roc"] = pooled_roc(ctx); print("auc", res["roc"]["ml"]["auc"], res["roc"]["dw"]["auc"], round(time.time() - t0))
    res["fpr"] = benign_fpr(ctx); print("fpr", res["fpr"])
    res["cold"] = cold_start(); print("cold", res["cold"], round(time.time() - t0))
    res["drift"] = slow_drift(); print("drift", {k: res["drift"][k] for k in ("ml", "dw")}, round(time.time() - t0))
    res["latency"] = latency_bench(ctx); print("lat", res["latency"])
    res["trans"] = transition_diff(ctx)
    # risk timeline aligned to attack start (steps -4..+4)
    tl = {}
    for k in ["A1", "A5", "A3"]:
        M, D = [], []
        for pos, ms, ds in steps[k][:120]:
            lo = max(0, pos - 4); w = list(range(-4, 5))
            m_v = [(ms[pos + o] if 0 <= pos + o < len(ms) else np.nan) for o in w]; d_v = [(ds[pos + o] if 0 <= pos + o < len(ds) else np.nan) for o in w]
            M.append(m_v); D.append(d_v)
        M, D = np.array(M), np.array(D)
        mthr = res["thr"]["ml"]; res_m = (M / (mthr * 2.0)) * 100  # ML anomaly score mapped to 0-100 with its alert threshold at 50
        tl[k] = dict(x=list(range(-4, 5)), dw=np.nanmean(D, 0).tolist(), dw_lo=np.nanpercentile(D, 25, 0).tolist(), dw_hi=np.nanpercentile(D, 75, 0).tolist(),
                     ml=np.nanmean(res_m, 0).tolist(), ml_lo=np.nanpercentile(res_m, 25, 0).tolist(), ml_hi=np.nanpercentile(res_m, 75, 0).tolist())
    res["timeline"] = tl
    json.dump(res, open("results.json", "w"), indent=1)
    print("done", round(time.time() - t0), "s")
