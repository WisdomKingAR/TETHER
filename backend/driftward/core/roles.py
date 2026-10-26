"""Role definitions: the declared Role Contracts and the benign behaviour model for each simulated agent."""
import hashlib
import numpy as np


def tool_hash(name: str) -> str:
    return hashlib.sha1(("tool-description-v1:" + name).encode()).hexdigest()[:12]

# tool tuple: (name, data_class, mean_bytes, is_sink, ingests_untrusted)
ROLES = {
    "procurement": dict(
        display="Procurement Agent", parent=None, color="#ff4a4a",
        tools=[("price.read", "supplier", 3e3, 0, 0), ("doc.open", "supplier", 8e4, 0, 1), ("pr.create", "pr", 6e3, 0, 0),
               ("email.send", "supplier", 2e4, 1, 0), ("web.fetch", "web", 5e4, 0, 1), ("po.lookup", "pr", 4e3, 0, 0)],
        allow_classes=["supplier", "pr", "web"], deny_classes=["hr", "hr_salary", "ledger", "credentials"],
        egress=["*.approved-suppliers.in", "corp-mail.local"], decoys=["pr/_draft_payroll.xlsx", "creds/.aws_backup"],
        rate=120, max_out=8.0e5, delegate=["pricing"]),
    "pricing": dict(
        display="Pricing Agent", parent="procurement", color="#ffb347",
        tools=[("price.read", "supplier", 3e3, 0, 0), ("fx.rate", "supplier", 1e3, 0, 0), ("quote.compare", "supplier", 9e3, 0, 0),
               ("doc.open", "supplier", 6e4, 0, 1), ("cache.write", "pr", 2e3, 0, 0)],
        allow_classes=["supplier", "pr"], deny_classes=["hr", "hr_salary", "ledger", "credentials"],
        egress=["corp-mail.local"], decoys=["pricing/_margin_model_v0.xlsx"], rate=120, max_out=3.0e5, delegate=[]),
    "hr_help": dict(
        display="HR Helpdesk Agent", parent=None, color="#7fd4ff",
        tools=[("kb.search", "hr_public", 4e3, 0, 0), ("ticket.read", "hr_ticket", 9e3, 0, 0), ("doc.open", "hr_public", 7e4, 0, 1),
               ("ticket.update", "hr_ticket", 5e3, 0, 0), ("email.send", "hr_ticket", 1.5e4, 1, 0), ("faq.read", "hr_public", 3e3, 0, 0)],
        allow_classes=["hr_public", "hr_ticket"], deny_classes=["hr_salary", "ledger", "credentials", "code"],
        egress=["corp-mail.local"], decoys=["hr/_payroll_export.csv"], rate=120, max_out=8.0e5, delegate=[]),
    "code_review": dict(
        display="Code Review Agent", parent=None, color="#9dff8a",
        tools=[("repo.read", "code", 6e4, 0, 0), ("diff.analyze", "code", 2e4, 0, 0), ("web.fetch", "web", 5e4, 0, 1),
               ("comment.post", "code", 3e3, 1, 0), ("ci.read", "ci", 8e3, 0, 0), ("lint.run", "code", 5e3, 0, 0)],
        allow_classes=["code", "ci", "web"], deny_classes=["hr", "hr_salary", "ledger", "credentials"],
        egress=["github.com", "*.github.com", "corp-mail.local"], decoys=["repo/.env.production.bak"], rate=120, max_out=6.0e5, delegate=[]),
    "finance_recon": dict(
        display="Finance Recon Agent", parent=None, color="#d8a8ff",
        tools=[("ledger.read", "ledger", 9e4, 0, 0), ("bank.feed", "finance", 1.2e5, 0, 0), ("doc.open", "finance", 6e4, 0, 1),
               ("report.write", "ledger", 2e4, 1, 0), ("email.send", "finance", 1.5e4, 1, 0), ("fx.rate", "finance", 2e3, 0, 0)],
        allow_classes=["ledger", "finance"], deny_classes=["hr", "hr_salary", "credentials", "code"],
        egress=["corp-mail.local", "*.bank-partner.in"], decoys=["finance/_treasury_keys.txt"], rate=120, max_out=8.0e5, delegate=[]),
}

AGENT_ORDER = ["procurement", "pricing", "hr_help", "code_review", "finance_recon"]
BASE_ORDER = list(AGENT_ORDER)
SPAWN_COLORS = ["#ff9de2", "#a0f0ff", "#ffe27a", "#b5ff9a", "#ffb0a0", "#c9b6ff"]


def transition_matrix(role: str) -> np.ndarray:
    n = len(ROLES[role]["tools"])
    rng = np.random.default_rng(sum(map(ord, ROLES[role].get("seed_role", role))))
    return np.array([rng.dirichlet(np.ones(n) * 0.45 + 0.1) for _ in range(n)])


def default_contract(role: str) -> dict:
    r = ROLES[role]
    return dict(
        agent=role, version=1, owner="it-" + role.replace("_", "-"),
        allow_tools=[t[0] for t in r["tools"]], allow_classes=list(r["allow_classes"]), deny_classes=list(r["deny_classes"]),
        egress=list(r["egress"]), rate_per_min=r["rate"], max_bytes_out=r["max_out"], delegate_to=list(r["delegate"]),
        untrusted_sources=["email", "pdf", "web"], decoys=list(r["decoys"]), tool_hashes={t[0]: tool_hash(t[0]) for t in r["tools"]}, canary_until=None, signature="",
    )
