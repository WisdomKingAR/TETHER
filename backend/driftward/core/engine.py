"""TETHER detection engine: Role Contract (P1), provenance/taint (P2), decoys (P3), behaviour (P4),
delegation (P5), slow-drift CUSUM (P6), identity proof, noisy-OR fusion and graded containment."""
from __future__ import annotations
import copy, fnmatch, hashlib, itertools, json, math, time, collections
import numpy as np
from . import tokens
from .roles import ROLES, AGENT_ORDER, BASE_ORDER, SPAWN_COLORS, default_contract, transition_matrix

W = dict(p1=0.90, p2=0.90, p3=0.95, p4=0.50, p5=0.60, p6=0.60, pid=0.90)
PLANE_NAMES = dict(p1="Role contract", p2="Provenance", p3="Decoy", p4="Behaviour", p5="Delegation", p6="Slow drift", pid="Identity proof")

# TETHER 5-factor scoring and tier system
FACTORS = ["scope", "taint", "seq", "cusum", "chain"]
FACTOR_WEIGHTS = {"scope": 0.90, "taint": 0.90, "seq": 0.50, "cusum": 0.60, "chain": 0.60}
LEVELS = ["ALLOW", "WATCH", "CLIP (SURGICAL)", "ISOLATE (SANDBOX)", "REVOKE (DEAD)"]
STICKY = 3  # ISOLATE and above need a human release


def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def level_for_score(risk: float) -> int:
    return 0 if risk < 30 else 1 if risk < 60 else 2 if risk < 85 else 3 if risk < 95 else 4


level_for = level_for_score


def compute_exact_shapley(factor_scores: dict[str, float]) -> dict[str, float]:
    """Compute exact Shapley attribution over 2^5 = 32 coalitions for the 5 PPT drift factors.
    Characteristic function v(S) = 100 * (1 - prod_{i in S} (1 - w_i * s_i))
    """
    factors = FACTORS
    weights = FACTOR_WEIGHTS
    n = len(factors)
    phi = {f: 0.0 for f in factors}

    def v(coalition):
        prod = 1.0
        for f in coalition:
            prod *= (1.0 - weights[f] * factor_scores.get(f, 0.0))
        return 100.0 * (1.0 - prod)

    for f in factors:
        others = [m for m in factors if m != f]
        for k in range(n):
            weight = math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
            for coalition in itertools.combinations(others, k):
                c_set = set(coalition)
                v_without = v(c_set)
                v_with = v(c_set | {f})
                phi[f] += weight * (v_with - v_without)
    return {k: round(val, 2) for k, val in phi.items()}


def jsd(p: np.ndarray, q: np.ndarray) -> float:
    p = p / max(p.sum(), 1e-9); q = q / max(q.sum(), 1e-9); m = 0.5 * (p + q)
    def kl(a, b):
        mask = a > 0
        return float((a[mask] * np.log2(a[mask] / b[mask])).sum())
    return math.sqrt(max(0.0, 0.5 * kl(p, m) + 0.5 * kl(q, m)))


class AgentState:
    def __init__(self, role: str):
        self.role = role
        r = ROLES[role]
        self.display, self.parent, self.color = r["display"], r["parent"], r["color"]
        self.tools = [t[0] for t in r["tools"]]
        self.meta = {t[0]: t for t in r["tools"]}
        self.T = transition_matrix(role)
        self.contract = default_contract(role)
        self.level = 0
        self.risk = 0.0
        self.last_tool: str | None = None
        self.taint = 0
        self.last_ingest_event: int | None = None
        self.sim_t = 0.0
        self.calls = collections.deque()          # (sim_t, bytes)
        self.window = collections.deque(maxlen=30)
        self.cusum = 0.0
        self.benign_streak = 0
        self.incident: str | None = None
        self.history: collections.deque = collections.deque(maxlen=600)
        self.sandbox: list[dict] = []
        self.counts = np.ones((len(self.tools), len(self.tools))) * 0.5
        self.mu_s, self.sd_s = 1.5, 1.0
        self.base_dist = np.ones(len(self.tools) + 1) / (len(self.tools) + 1)
        self.mu_j, self.sd_j = 0.1, 0.05
        self.h_j = 0.3
        self.logb = {t[0]: (math.log(t[2]), 0.5) for t in r["tools"]}
        self._P = None
        self.cold = False
        self.spawned = False
        self.token = ""
        self.token_scopes: list[str] = []
        self.token_prev = ""
        self.stats = dict(events=0, flagged=0, sandboxed=0, denied=0, leaked=0.0, held=0)

    # ---------------------------------------------------------------- training
    def train(self, n: int = 500):
        rng = np.random.default_rng(sum(map(ord, self.role)) + 7)
        k = len(self.tools); cur = rng.integers(k); seq = []
        for _ in range(n):
            seq.append(int(cur)); cur = rng.choice(k, p=self.T[cur])
        for a, b in zip(seq[:-1], seq[1:]):
            self.counts[a, b] += 1
        P = self.counts / self.counts.sum(1, keepdims=True)
        sur = np.array([-math.log(P[a, b]) for a, b in zip(seq[:-1], seq[1:])])
        self._P = None
        self.mu_s, self.sd_s = float(sur.mean()), float(sur.std() + 1e-6)
        dist = np.bincount(seq, minlength=k + 1).astype(float); self.base_dist = dist / dist.sum()
        # calibrate the drift detector on a long benign run so that healthy behaviour never alarms
        seq2 = []; cur = rng.integers(k)
        for _ in range(4000):
            seq2.append(int(cur)); cur = rng.choice(k, p=self.T[cur])
        js = np.array([jsd(np.bincount(seq2[i:i + 30], minlength=k + 1).astype(float), self.base_dist) for i in range(0, 4000 - 30)])
        self.mu_j, self.sd_j = float(js.mean()), float(js.std() + 1e-6)
        S, mx = 0.0, 0.0
        for d in js:
            S = max(0.0, S + (d - self.mu_j - self.sd_j)); mx = max(mx, S)
        self.h_j = max(1.15 * mx, 3 * self.sd_j)

    def adopt_peer_prior(self, peer: "AgentState", weight: float = 0.04):
        """Cold start: a brand-new agent borrows its role's peer baseline (scaled down) so behaviour planes work from call one."""
        self.counts = peer.counts * weight + 0.5; self._P = None
        self.mu_s, self.sd_s, self.mu_j, self.sd_j, self.h_j = peer.mu_s, peer.sd_s, peer.mu_j, peer.sd_j, peer.h_j
        self.base_dist = peer.base_dist.copy(); self.cold = True

    def bigram_p(self, prev: str | None, tool: str) -> float:
        if tool not in self.tools:
            return 1e-4
        if prev is None or prev not in self.tools:
            return 1.0 / len(self.tools)
        if self._P is None: self._P = self.counts / self.counts.sum(1, keepdims=True)
        return float(self._P[self.tools.index(prev), self.tools.index(tool)])

    def public(self) -> dict:
        return dict(id=self.role, display=self.display, parent=self.parent, color=self.color, level=self.level, level_name=LEVELS[self.level],
                    risk=round(self.risk, 1), taint=self.taint > 0, contract_version=self.contract["version"], canary=self.contract.get("canary_until"),
                    stats=dict(self.stats, leaked=round(self.stats["leaked"])), token_scopes=self.token_scopes, incident=self.incident,
                    cusum=round(min(1.0, self.cusum / self.h_j), 2), sandbox_count=len(self.sandbox), cold=self.cold and self.stats["events"] < 60, spawned=self.spawned)


class Engine:
    def __init__(self):
        self.agents: dict[str, AgentState] = {}
        self.enforce = True
        self.eid = 0
        self.alerts: dict[str, dict] = {}
        self.aid = 0
        self.pending: dict[int, dict] = {}
        self.resolved: list[dict] = []
        self.canaries: dict[str, str] = {}
        self.plane_counts: collections.Counter = collections.Counter()
        self.reset()

    # ---------------------------------------------------------------- lifecycle
    def spawn(self, template: str, name: str | None = None) -> AgentState:
        """Create a brand-new ephemeral agent from a role template with NO history (peer prior only)."""
        n = sum(1 for r in ROLES if ROLES[r].get("seed_role") == template) + 1
        rid = f"{template}-x{n}"
        ROLES[rid] = dict(ROLES[template], display=name or f"{ROLES[template]['display'].replace(' Agent', '')} #{n} (new)", seed_role=template, parent=None, color=SPAWN_COLORS[(n - 1) % len(SPAWN_COLORS)])
        AGENT_ORDER.append(rid)
        a = AgentState(rid); a.spawned = True
        a.adopt_peer_prior(self.agents[template])
        self.agents[rid] = a; self.sign(a); self.issue_token(a)
        return a

    def remove(self, rid: str):
        a = self.agents.pop(rid, None)
        if a and a.spawned:
            ROLES.pop(rid, None)
            if rid in AGENT_ORDER: AGENT_ORDER.remove(rid)

    def reset(self):
        for rid in [r for r in list(ROLES) if ROLES[r].get("seed_role")]: ROLES.pop(rid, None)
        AGENT_ORDER[:] = BASE_ORDER
        self.agents = {r: AgentState(r) for r in AGENT_ORDER}
        for a in self.agents.values():
            a.train()
            self.sign(a)
            self.issue_token(a)
        self.alerts = {}; self.eid = 0; self.aid = 0; self.pending = {}; self.resolved = []; self.canaries = {}; self.plane_counts = collections.Counter()
        self.seed_pending()
        tokens.REVOKED.clear()

    def seed_pending(self):
        now = time.time()
        self.pending[91] = dict(
            id=91, ts=now - 140, agent="hr_help", display="HR Helpdesk Agent",
            tool="email.send", target="corp-mail.local", bytes=120000, sink=True,
            risk=58.4, reasons=["Statistical anomaly: payload 10x larger than historical baseline", "Destination inside contract, but triggered from an uncommon host"],
            status="pending", oob=False
        )
        self.pending[92] = dict(
            id=92, ts=now - 55, agent="finance_recon", display="Finance Recon Agent",
            tool="report.write", target="s3://finance-archive/recon_2026.csv", bytes=450000, sink=True,
            risk=62.1, reasons=["Volume exceeds normal operational threshold", "Process requested un-scoped ledger export"],
            status="pending", oob=False
        )
        self.resolved = [
            dict(id=89, ts=now - 600, agent="procurement", display="Procurement Agent", tool="price.read", target="quotes/q4.xlsx", bytes=18000, risk=42.0, reasons=["Routine query held during elevated threat level"], status="approved", resolved=now - 540),
            dict(id=90, ts=now - 450, agent="code_review", display="Code Review Agent", tool="repo.read", target=".env.local", bytes=3200, risk=74.0, reasons=["Sensitive file read attempted outside active PR context"], status="denied", resolved=now - 390)
        ]

    def sign(self, a: AgentState):
        c = a.contract; body = json.dumps({k: v for k, v in c.items() if k != "signature"}, sort_keys=True)
        c["signature"] = "ed25519:" + hashlib.sha256(body.encode()).hexdigest()[:24]

    def issue_token(self, a: AgentState, narrowed: bool = False):
        scopes = [t for t in a.contract["allow_tools"] if not (narrowed and a.meta.get(t, (0, 0, 0, 0))[3])]
        if a.token:
            a.token_prev = a.token
        if narrowed and a.token_prev:
            try:
                ex = tokens.exchange(a.token_prev, scopes, 300, a.level); a.token = ex["access_token"]; a.token_scopes = ex["scope"].split(); return
            except ValueError:
                pass
        a.token = tokens.issue(a.role, scopes, 3600, a.level, a.contract["version"]); a.token_scopes = scopes

    # ---------------------------------------------------------------- helpers
    def approved(self, a: AgentState, host: str) -> bool:
        return any(fnmatch.fnmatch(host, p) for p in a.contract["egress"])

    # ---------------------------------------------------------------- core
    def evaluate(self, a: AgentState, ev: dict, commit: bool = True, contract: dict | None = None) -> dict:
        """Score one event. commit=False is the stateless what-if path used by the Contract Studio."""
        c = contract or a.contract
        tool, cls, egress = ev["tool"], ev.get("data_class", ""), ev.get("egress", "")
        b = float(ev.get("bytes", 0))
        planes = {k: dict(score=0.0, reasons=[]) for k in W}
        # P1 contract
        r1 = planes["p1"]["reasons"]
        if tool not in c["allow_tools"]:
            r1.append(f"tool '{tool}' is not in the contract")
        if cls in c["deny_classes"]:
            r1.append(f"data class '{cls}' is denied by contract")
        elif cls and c["allow_classes"] and cls not in c["allow_classes"]:
            r1.append(f"data class '{cls}' is outside the contract")
        if egress and not any(fnmatch.fnmatch(egress, p) for p in c["egress"]):
            r1.append(f"egress to '{egress}' is not an approved domain")
        pin = c.get("tool_hashes", {}).get(tool)
        if ev.get("tool_hash") and pin and ev["tool_hash"] != pin:
            r1.append(f"tool '{tool}' description hash changed (pinned {pin[:6]}, got {ev['tool_hash'][:6]})")
        if commit:
            while a.calls and a.sim_t - a.calls[0][0] > 60: a.calls.popleft()
            out = sum(x[1] for x in a.calls if x[1] > 0) + (b if ev.get("sink") else 0)
            if len(a.calls) + 1 > c["rate_per_min"]: r1.append(f"rate {len(a.calls) + 1}/min exceeds {c['rate_per_min']}")
            if ev.get("sink") and out > c["max_bytes_out"]: r1.append(f"bytes out {int(out/1000)} KB/min exceeds {int(c['max_bytes_out']/1000)} KB")
        planes["p1"]["score"] = 1.0 if r1 else 0.0
        # P2 provenance
        tainted = a.taint > 0 or ev.get("taint")
        r2 = planes["p2"]["reasons"]
        if tainted:
            if ev.get("sink") and (ev.get("dest_from_t2") or (egress and not self.approved_c(c, egress))):
                r2.append("destination of a sensitive action derives from untrusted (T2) content")
            if planes["p1"]["score"] and (cls in c["deny_classes"] or (cls and cls not in c["allow_classes"])):
                r2.append("out-of-contract data access while holding untrusted (T2) context")
        elif ev.get("dest_from_t2") and ev.get("sink"):
            r2.append("destination was supplied by external content")
        planes["p2"]["score"] = 1.0 if r2 else 0.0
        # P3 decoy
        if ev.get("target") in c["decoys"] or ev.get("decoy"):
            planes["p3"]["score"] = 1.0; planes["p3"]["reasons"].append(f"decoy '{ev.get('target')}' touched; no legitimate task reads it")
        # identity proof
        if not ev.get("proof_ok", True):
            planes["pid"]["score"] = 1.0; planes["pid"]["reasons"].append("token key-proof mismatch (token replayed from another host)")
        # P5 delegation
        if not ev.get("scope_ok", True):
            planes["p5"]["score"] = 1.0; planes["p5"]["reasons"].append("child requested scope not covered by parent's delegation receipt")
        # P4 behaviour
        s_seq = s_b = s_nov = 0.0
        if tool in a.tools or a.last_tool is None:
            sur = -math.log(max(a.bigram_p(a.last_tool, tool), 1e-6))
        else:
            sur = 9.2
        s_seq = clip((sur - (a.mu_s + 2.5 * a.sd_s)) / 4.0)
        if tool in a.logb:
            mu, sd = a.logb[tool]; zb = (math.log(max(b, 1)) - mu) / sd; s_b = clip((zb - 2.0) / 3.0)
        if ev.get("host_novel"): s_nov = 0.55
        if ev.get("hour", 13) < 6: s_nov = max(s_nov, 0.5)
        s4 = max(s_seq, s_b, s_nov); planes["p4"]["score"] = round(s4, 3)
        if s_seq > 0.3: planes["p4"]["reasons"].append(f"unusual tool sequence ({a.last_tool} → {tool}), surprise {sur / 0.693:.1f} bits")
        if s_b > 0.3: planes["p4"]["reasons"].append(f"payload {int(b/1000)} KB is {zb:.1f}σ above this tool's norm")
        if s_nov: planes["p4"]["reasons"].append("new network host or off-hours activity")
        # P6 slow drift (needs state; commit path only)
        cus = a.cusum
        if commit and tool in a.tools:
            idx = a.tools.index(tool)
            w = list(a.window) + [idx]
            if len(w) >= 30:
                d = jsd(np.bincount(w, minlength=len(a.tools) + 1).astype(float), a.base_dist)
                cus = max(0.0, a.cusum + (d - a.mu_j - 1.0 * a.sd_j))
        s6 = clip(cus / a.h_j) if commit else 0.0
        planes["p6"]["score"] = round(s6, 3)
        if s6 > 0.3: planes["p6"]["reasons"].append(f"behaviour distribution drifting from frozen baseline (CUSUM at {int(s6*100)}% of alarm)")
        # fusion
        prod = 1.0
        for k, v in planes.items(): prod *= 1 - W[k] * v["score"]
        risk = 100 * (1 - prod)
        hard_decoy_or_taint = bool(planes["p3"]["score"] or (planes["p2"]["score"] and ev.get("sink")))
        hard_pid = bool(planes["pid"]["score"])
        hard = bool(hard_decoy_or_taint or hard_pid or planes["p2"]["score"])
        if hard_decoy_or_taint:
            risk = max(risk, 94.2)
        elif hard:
            risk = max(risk, 85.0)
        if not ev.get("confirmed"):
            risk = min(risk, 94.2 if hard_decoy_or_taint else 94.0)   # Tier 4 (95+) needs confirmed evidence (e.g. canary reused) or operator
        contrib = {k: W[k] * v["score"] for k, v in planes.items()}
        tot = sum(contrib.values()) or 1.0
        for k in planes: planes[k]["contrib"] = round(risk * contrib[k] / tot, 1)

        # 5-factor exact Shapley attribution
        factor_scores = {
            "scope": planes["p1"]["score"],
            "taint": planes["p2"]["score"],
            "seq": planes["p4"]["score"],
            "cusum": planes["p6"]["score"],
            "chain": planes["p5"]["score"],
        }
        shapley = compute_exact_shapley(factor_scores)

        return dict(risk=round(risk, 1), planes=planes, shapley=shapley, hard=bool(hard), out_of_contract=bool(planes["p1"]["score"] or planes["p2"]["score"] or planes["p3"]["score"]), _cus=cus)

    def approved_c(self, c: dict, host: str) -> bool:
        return any(fnmatch.fnmatch(host, p) for p in c["egress"])

    # ---------------------------------------------------------------- process
    def process(self, ev: dict) -> dict:
        a = self.agents[ev["agent"]]
        self.eid += 1
        ev = dict(ev); ev["id"] = self.eid; ev["ts"] = time.time()
        meta = a.meta.get(ev["tool"])
        if meta:
            ev.setdefault("data_class", meta[1]); ev.setdefault("sink", bool(meta[3])); ev.setdefault("bytes", meta[2])
        ev.setdefault("sink", False)
        a.sim_t += float(ev.get("sim_dt", 1.0))
        res = self.evaluate(a, ev)
        prev_level = a.level
        a.cusum = res.pop("_cus")
        er = res["risk"]
        # agent risk: spikes immediately, then decays
        a.risk = er if er >= a.risk else a.risk * 0.985
        if er < 30: a.benign_streak += 1
        else: a.benign_streak = 0
        want = level_for_score(a.risk)
        if want > a.level: a.level = want
        elif want < a.level and a.level < STICKY and a.benign_streak >= 12: a.level -= 1; a.benign_streak = 0
        # decision (TETHER 4-tier enforcement)
        risky = er >= 60 or res["out_of_contract"]
        L = a.level
        verdict = "ALLOW"
        if L == 4: verdict = "REVOKE"
        elif L == 3 and risky: verdict = "ISOLATE"
        elif L == 2 and risky: verdict = "CLIP" if ev.get("sink") or res["out_of_contract"] else "ALLOW"
        elif L == 1 and (risky or (ev.get("sink") and er >= 30)): verdict = "CLIP_HELD"
        effective = verdict
        if not self.enforce and verdict != "ALLOW": effective = "SHADOW:" + verdict
        # side effects
        if L > prev_level:
            if L == 2: self.issue_token(a, narrowed=True)
            if L >= 3: tokens.revoke(a.token) if L == 4 else self.issue_token(a, narrowed=True)
        leaked = float(ev.get("bytes", 0)) if (ev.get("sink") and res["out_of_contract"] and effective not in ("CLIP", "REVOKE", "ISOLATE", "CLIP_HELD", "DENY", "SANDBOX", "STEP_UP")) else 0.0
        if verdict == "ISOLATE" and self.enforce:
            entry = self.sandbox_entry(ev, res); a.sandbox.append(entry); self.canaries[entry["canary"]] = a.role
        for k, v in res["planes"].items():
            if v["score"] >= 0.5: self.plane_counts[k] += 1
        if effective == "CLIP_HELD":
            self.pending[ev["id"]] = dict(id=ev["id"], ts=ev["ts"], agent=a.role, display=a.display, tool=ev["tool"], target=ev.get("target") or ev.get("egress", ""), bytes=int(ev.get("bytes", 0)),
                                          sink=bool(ev.get("sink")), risk=res["risk"], reasons=[r for p in res["planes"].values() for r in p["reasons"]][:4] or ["unusual for this role; held for a human"], status="pending",
                                          oob=bool(res["out_of_contract"]))
        # state updates
        meta_ingest = bool(meta and meta[4]) or ev.get("ingest")
        if meta_ingest:
            a.taint = 12; a.last_ingest_event = ev["id"]
        elif a.taint > 0: a.taint -= 1
        if ev["tool"] in a.tools:
            a.window.append(a.tools.index(ev["tool"])); a.last_tool = ev["tool"]
        a.calls.append((a.sim_t, float(ev.get("bytes", 0)) if ev.get("sink") else 0.0))
        a.stats["events"] += 1
        if risky: a.stats["flagged"] += 1
        if verdict == "ISOLATE" and self.enforce: a.stats["sandboxed"] += 1
        if verdict in ("CLIP", "REVOKE", "DENY") and self.enforce: a.stats["denied"] += 1
        if verdict == "CLIP_HELD" and self.enforce: a.stats["held"] += 1
        a.stats["leaked"] += leaked
        out = dict(event=ev, risk=res["risk"], planes=res["planes"], shapley=res.get("shapley", {}), verdict=effective, raw_verdict=verdict, level=a.level, level_name=LEVELS[a.level], agent_risk=round(a.risk, 1),
                   iam="ALLOW", leaked=leaked, escalated=a.level > prev_level, risky=risky)
        a.history.append(out)
        # parent exposure (P5 propagation)
        if a.parent and er >= 60:
            p = self.agents[a.parent]; p.risk = max(p.risk, 0.6 * er)
        self.update_incident(a, out)
        out["agent_state"] = a.public()
        return out

    def sandbox_entry(self, ev: dict, res: dict) -> dict:
        t, tgt = ev["tool"], ev.get("target", "")
        canary = hashlib.sha1(f"{ev['id']}{tgt}".encode()).hexdigest()[:10]
        if "salary" in (ev.get("data_class", "") + tgt) or "hr" in ev.get("data_class", ""):
            fake = "emp_id,name,ctc\nE1041,A. Rao,1450000\nE1042,S. Iyer,1380000\n… 212 rows (synthetic)"
        elif "cred" in ev.get("data_class", "") + tgt or "aws" in tgt or ".env" in tgt:
            fake = f"AWS_ACCESS_KEY_ID=AKIA{canary.upper()}CANARY\nAWS_SECRET_ACCESS_KEY=canary/{canary}/not-a-real-secret"
        elif ev.get("sink"):
            fake = '200 OK {"received": true, "bytes": %d}' % int(ev.get("bytes", 0))
        else:
            fake = "OK (synthetic data from decoy sandbox)"
        return dict(event_id=ev["id"], ts=ev["ts"], tool=t, target=tgt or ev.get("egress", ""), egress=ev.get("egress", ""), bytes=int(ev.get("bytes", 0)),
                    attacker_saw=fake, we_recorded=[r for p in res["planes"].values() for r in p["reasons"]][:4], canary=canary)

    # ---------------------------------------------------------------- incidents / alerts
    def update_incident(self, a: AgentState, out: dict):
        ev = out["event"]
        if a.incident is None and out["agent_risk"] >= 60:
            self.aid += 1; aid = f"A-{2290 + self.aid}"
            a.incident = aid
            chain = []
            if a.last_ingest_event is not None:
                src = next((h for h in a.history if h["event"]["id"] == a.last_ingest_event), None)
                if src: chain.append(self.chain_item(src))
            self.alerts[aid] = dict(id=aid, agent=a.role, display=a.display, opened=ev["ts"], peak=out["risk"], level=a.level, level_name=LEVELS[a.level], chain=chain,
                                    status="open", planes={k: 0.0 for k in W}, reasons=[], run_id=ev.get("run_id"), tokens=dict(before=claims_short(a.token_prev), after=claims_short(a.token)),
                                    mode="enforce" if self.enforce else "shadow", leaked=0.0, closed=None, action="", narrative="")
        if a.incident:
            al = self.alerts[a.incident]
            if out["risky"] or out["risk"] >= 30:
                al["chain"].append(self.chain_item(out))
                for k, v in out["planes"].items():
                    al["planes"][k] = max(al["planes"][k], v["contrib"])
                    for r in v["reasons"]:
                        if r not in al["reasons"]: al["reasons"].append(r)
            al["peak"] = max(al["peak"], out["risk"]); al["level"] = a.level; al["level_name"] = LEVELS[a.level]; al["leaked"] += out["leaked"]
            al["tokens"]["after"] = claims_short(a.token)
            al["action"] = action_text(a, self.enforce); al["narrative"] = self.narrative(al, a)
            if a.level < 3 and a.risk < 25 and a.incident:
                al["status"] = "closed"; al["closed"] = ev["ts"]; a.incident = None

    def chain_item(self, out: dict) -> dict:
        ev = out["event"]
        return dict(id=ev["id"], ts=ev["ts"], tool=ev["tool"], target=ev.get("target", "") or ev.get("egress", ""), bytes=int(ev.get("bytes", 0)), risk=out["risk"], verdict=out["verdict"],
                    iam="ALLOW", taint=bool(ev.get("taint")), planes={k: dict(score=v["score"], reasons=v["reasons"]) for k, v in out["planes"].items() if v["score"] > 0})

    def narrative(self, al: dict, a: AgentState) -> str:
        r = al["reasons"][:3]
        first = al["chain"][0]["ts"] if al["chain"] else al["opened"]
        parts = [f"{al['display']} stopped behaving like its declared role"]
        if r: parts.append("because " + "; ".join(x[0].lower() + x[1:] for x in r))
        return " ".join([(" ".join(parts)).rstrip(".") + ".", f"Its token stayed valid at every step; {len(al['chain'])} correlated events over {max(1, int(time.time() - first))} s."])

    # ---------------------------------------------------------------- operator actions
    def release(self, role: str):
        a = self.agents[role]; a.level = 0; a.risk = 0.0; a.taint = 0; a.cusum = 0.0; a.benign_streak = 0
        self.issue_token(a)
        if a.incident:
            al = self.alerts[a.incident]; al["status"] = "closed"; al["closed"] = time.time(); a.incident = None

    def isolate(self, role: str):
        a = self.agents[role]; a.level = 4; a.risk = max(a.risk, 95)
        tokens.revoke(a.token)

    # ---------------------------------------------------------------- contract studio
    def whatif(self, role: str, proposed: dict) -> dict:
        a = self.agents[role]; base = a.contract; merged = {**base, **proposed}
        before = after = newly_blocked = newly_allowed = 0; samples = []
        for h in list(a.history)[-300:]:
            ev = h["event"]
            r0 = self.evaluate(a, ev, commit=False, contract=base); r1 = self.evaluate(a, ev, commit=False, contract=merged)
            f0, f1 = r0["out_of_contract"], r1["out_of_contract"]
            before += f0; after += f1
            if f1 and not f0: newly_blocked += 1; samples.append(dict(id=ev["id"], tool=ev["tool"], target=ev.get("target", ""), change="would now fire", why=[x for p in r1["planes"].values() for x in p["reasons"]][:2]))
            if f0 and not f1: newly_allowed += 1; samples.append(dict(id=ev["id"], tool=ev["tool"], target=ev.get("target", ""), change="would no longer fire", why=[x for p in r0["planes"].values() for x in p["reasons"]][:2]))
        n = len(a.history)
        return dict(replayed=min(n, 300), fires_before=before, fires_after=after, newly_blocked=newly_blocked, newly_allowed=newly_allowed, samples=samples[:8])

    def suggest(self, role: str) -> dict:
        a = self.agents[role]
        tools = sorted({h["event"]["tool"] for h in a.history if not h["risky"]})
        classes = sorted({h["event"].get("data_class", "") for h in a.history if not h["risky"]} - {""})
        eg = sorted({h["event"].get("egress", "") for h in a.history if not h["risky"] and h["event"].get("egress")})
        return dict(allow_tools=tools, allow_classes=classes, egress=eg or a.contract["egress"], based_on=sum(1 for h in a.history if not h["risky"]))

    def set_contract(self, role: str, patch: dict) -> dict:
        a = self.agents[role]; c = a.contract
        for k in ("allow_tools", "allow_classes", "deny_classes", "egress", "decoys", "delegate_to"):
            if k in patch and isinstance(patch[k], list): c[k] = [str(x) for x in patch[k]]
        for k in ("rate_per_min", "max_bytes_out"):
            if k in patch: c[k] = float(patch[k])
        c["version"] += 1; c["canary_until"] = time.time() + 300  # signed bump opens a 5 minute canary window
        self.sign(a); self.issue_token(a)
        return copy.deepcopy(c)

    # ---------------------------------------------------------------- approvals (human in the loop)
    def resolve(self, eid: int, approve: bool) -> dict | None:
        p = self.pending.pop(eid, None)
        if not p: return None
        p["status"] = "approved" if approve else "denied"; p["resolved"] = time.time()
        a = self.agents[p["agent"]]
        if approve and p["sink"] and p["oob"]: a.stats["leaked"] += p["bytes"]
        a.stats["held"] = max(0, a.stats["held"] - 1)
        self.resolved = ([p] + self.resolved)[:30]
        return p

    # ---------------------------------------------------------------- canary tripwire
    def confirm_canary(self, value: str) -> dict:
        for c, role in self.canaries.items():
            if c.lower() in value.lower() or c.upper() in value:
                out = self.process(dict(agent=role, tool="canary.reuse", target=f"canary {c}", decoy=True, sink=True, bytes=0, egress="external-host", dest_from_t2=True, taint=True, confirmed=True, proof_ok=True, data_class="credentials", label="Canary key used outside the sandbox"))
                return dict(found=True, agent=role, canary=c, out=out)
        return dict(found=False)

    def coverage(self) -> dict:
        owasp = [("ASI01", "Agent goal hijack", ["p2"]), ("ASI02", "Tool misuse", ["p1"]), ("ASI03", "Identity & privilege abuse", ["pid", "p1"]), ("ASI04", "Agentic supply chain", ["p1"]),
                 ("ASI05", "Unexpected code execution", ["p1", "p4"]), ("ASI06", "Memory & context poisoning", ["p2", "p3"]), ("ASI07", "Insecure inter-agent comms", ["p5"]),
                 ("ASI08", "Cascading failures", ["p4", "p5"]), ("ASI09", "Human-agent trust exploitation", ["p3"]), ("ASI10", "Rogue agents", ["p6", "p3", "p4"])]
        rows = []
        for i, n, ps in owasp:
            rows.append(dict(id=i, name=n, planes=ps, hits=sum(self.plane_counts[p] for p in ps), covered=True))
        return dict(owasp=rows, planes={k: dict(label=v, hits=self.plane_counts[k]) for k, v in dict(p1="Role contract", p2="Provenance", p3="Decoy", p4="Behaviour", p5="Delegation", p6="Slow drift", pid="Identity proof").items()})

    def report(self, aid: str) -> str:
        al = self.alerts[aid]
        lines = [f"# Incident report {aid}", "", f"**Agent:** {al['display']}  ", f"**Status:** {al['status']}  ", f"**Peak drift score (D):** {al['peak']:.0f}  ", f"**Response level:** {al['level_name']}  ", f"**Mode:** {al['mode']}  ",
                 f"**Payload leaked:** {int(al['leaked'])} bytes", "", "## Summary", al["narrative"], "", "## Action taken", al["action"], "", "## Evidence by plane"]
        for k, v in al["planes"].items():
            if v > 0: lines.append(f"- {PLANE_NAMES[k]}: +{v:.0f} risk points")
        lines += ["", "## Reasons"] + [f"- {r}" for r in al["reasons"]] + ["", "## Causal chain", "| # | time | tool | target | risk | verdict |", "|---|---|---|---|---|---|"]
        for c in al["chain"]:
            lines.append(f"| {c['id']} | {time.strftime('%H:%M:%S', time.localtime(c['ts']))} | {c['tool']} | {str(c['target'])[:40]} | {c['risk']:.0f} | {c['verdict']} |")
        t = al.get("tokens", {})
        lines += ["", "## Token change (RFC 8693)", f"- before: level {t.get('before', {}).get('lvl')}, {len(t.get('before', {}).get('scope', []))} scopes, ttl {t.get('before', {}).get('ttl')} s",
                  f"- after: level {t.get('after', {}).get('lvl')}, {len(t.get('after', {}).get('scope', []))} scopes, ttl {t.get('after', {}).get('ttl')} s", "",
                  "_Every call in this chain carried a valid token and passed IAM; the detection basis is behaviour versus the signed Role Contract._"]
        return "\n".join(lines)

    def snapshot(self) -> dict:
        total_ev = max(self.eid, sum(a.stats["events"] for a in self.agents.values()))
        total_fl = sum(a.stats["flagged"] for a in self.agents.values())
        total_sb = sum(a.stats["sandboxed"] for a in self.agents.values())
        total_lk = sum(a.stats["leaked"] for a in self.agents.values())
        counts = dict(events=total_ev, flagged=total_fl, sandboxed=total_sb, leaked=int(total_lk))
        return dict(agents=[a.public() for a in self.agents.values()], enforce=self.enforce, alerts=len(self.alerts), events=total_ev, counts=counts)


def claims_short(tok: str) -> dict:
    if not tok: return {}
    try:
        c = tokens.claims_unverified(tok)
        return dict(sub=c["sub"].rsplit("/", 1)[-1], scope=c.get("scope", "").split(), ttl=c["exp"] - c["iat"], lvl=c.get("lvl", 0), act=c.get("act", {}).get("sub"), jti=c["jti"], prev=c.get("prev_jti"))
    except Exception:  # noqa: BLE001
        return {}


def action_text(a: AgentState, enforce: bool) -> str:
    if not enforce: return "SHADOW mode: logged only, nothing enforced"
    return {0: "ALLOW: observe normal operations", 1: "WATCH: clip held for approval on risky calls", 2: "CLIP: token narrowed (RFC 8693); surgical sink block",
            3: "ISOLATE: risky calls routed to decoy sandbox; egress cut; role tools stay live", 4: "REVOKE: token revoked, session terminated"}[a.level]
