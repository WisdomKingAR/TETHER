import json, numpy as np, pandas as pd, seaborn as sns, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, FancyBboxPatch

R = json.load(open("results.json"))
BG, INK, GRID = "#F4E9D6", "#1E0C0C", "#D8C6A6"
C_DW, C_ML, C_IAM, C_AMB, C_GRN = "#A3151B", "#2F4B6E", "#8C8C8C", "#B8741A", "#2E6B3F"
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 10, "axes.edgecolor": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK, "text.color": INK,
                     "axes.facecolor": BG, "figure.facecolor": BG, "savefig.facecolor": BG, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})


def save(fig, name): fig.savefig(name, dpi=300); plt.close(fig)


# ---------- F1 risk timeline (slide 2)
fig, ax = plt.subplots(figsize=(3.75, 1.5))
tl = R["timeline"]; x = tl["A1"]["x"]
ax.axhspan(50, 70, color=C_AMB, alpha=0.18, lw=0); ax.axhspan(70, 112, color=C_DW, alpha=0.10, lw=0)
ax.plot(x, tl["A1"]["ml"], color=C_ML, lw=1.6, ls="-", marker="s", ms=3, label="UEBA / ML-only: injection")
ax.plot(x, tl["A5"]["ml"], color=C_ML, lw=1.6, ls="--", marker="s", ms=3, label="UEBA / ML-only: mimicry")
ax.plot(x, tl["A1"]["dw"], color=C_DW, lw=2.2, marker="o", ms=4, label="TETHER: injection")
ax.plot(x, tl["A5"]["dw"], color=C_DW, lw=2.2, ls="--", marker="o", ms=4, label="TETHER: mimicry")
ax.axvline(0, color=INK, lw=1, ls=":"); ax.text(0.15, 10, "◂ first malicious call", fontsize=7, va="center", ha="left")
ax.text(-4.1, 52, "L2", fontsize=7, color=C_AMB, va="bottom", fontweight="bold"); ax.text(-4.1, 72, "L3", fontsize=7, color=C_DW, va="bottom", fontweight="bold")
ax.set_ylim(0, 112); ax.set_xlim(-4.2, 4.2); ax.set_xlabel("tool calls relative to attack start", fontsize=7.5); ax.set_ylabel("risk score", fontsize=7.5); ax.tick_params(labelsize=7)
ax.legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.4), ncol=2, handlelength=2.0, columnspacing=1.0)
fig.subplots_adjust(left=0.13, right=0.985, top=0.97, bottom=0.42); save(fig, "f1_timeline.png")

# ---------- F2 behaviour fingerprint + CUSUM (slide 3)
fig, (a, b) = plt.subplots(1, 2, figsize=(4.7, 1.62), gridspec_kw={"width_ratios": [1, 1.25]})
names = ["price", "doc", "pr", "mail", "web", "po"]
P0 = np.array(R["trans"][0])
sns.heatmap(P0, ax=a, cmap=sns.light_palette(C_DW, as_cmap=True), xticklabels=names, yticklabels=names, cbar=False, linewidths=0.6, linecolor=BG, annot=False)
a.set_title("Normal tool→tool behaviour", fontsize=8.5); a.tick_params(labelsize=7, length=0); a.grid(False); plt.setp(a.get_xticklabels(), rotation=45)
ex = R["drift"]["example"]; k = np.arange(len(ex["S"]))
b.plot(k, ex["S"], color=C_DW, lw=2, label="creeping agent"); b.plot(k, ex["ben_S"], color=C_GRN, lw=1.8, label="healthy agent")
b.axhline(ex["h"], color=INK, ls="--", lw=1, label="threshold h")
if ex["alarm"] is not None: b.axvline(ex["alarm"], color=C_AMB, lw=1.4, label=f"alarm: session {ex['alarm']}")
b.set_title("Slow drift: CUSUM on JS-divergence", fontsize=8.5); b.set_xlabel("session #", fontsize=8.5); b.set_ylabel("CUSUM S", fontsize=8.5); b.tick_params(labelsize=8); b.legend(fontsize=7, loc="upper left")
fig.tight_layout(pad=0.4); save(fig, "f2_behaviour.png")

# ---------- F3 Gantt (slide 4)
rows = [("Contract + registry", 1, 2, 0), ("Gateway + identity", 1, 3, 0), ("Provenance + decoys", 2, 4, 0), ("Detectors + fusion", 3, 6, 0), ("Response + token service", 5, 7, 0),
        ("Console + explainer", 4, 8, 1), ("Attack harness + evals", 6, 9, 1), ("Pilot hardening", 9, 12, 2)]
fig, ax = plt.subplots(figsize=(3.2, 1.45)); cols = [C_DW, C_AMB, C_IAM]
for i, (n, s, e, c) in enumerate(rows):
    ax.barh(i, e - s + 1, left=s - 1, color=cols[c], height=0.7, edgecolor=INK, lw=0.5)
    ax.text(s - 1 + (e - s + 1) / 2, i, f"{s}–{e}", ha="center", va="center", color="white", fontsize=6.5, fontweight="bold")
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], fontsize=7); ax.invert_yaxis(); ax.set_xlim(0, 12); ax.set_xticks(np.arange(0.5, 12, 1)); ax.set_xticklabels(range(1, 13), fontsize=6.5)
ax.set_xlabel("week", fontsize=7); ax.grid(axis="y", visible=False)
fig.tight_layout(pad=0.4); save(fig, "f3_gantt.png")

# ---------- F4 risk heat-map (slide 4)
fig, ax = plt.subplots(figsize=(2.4, 1.4))
M = np.array([[2, 3, 4], [1, 2, 3], [0, 1, 2]]); cm = sns.blend_palette(["#CFE3C8", "#F0D58A", "#E69A4C", "#B5322C", "#6E1216"], as_cmap=True)
sns.heatmap(M, ax=ax, cmap=cm, cbar=False, linewidths=1.5, linecolor=BG, xticklabels=["Low", "Med", "High"], yticklabels=["High", "Med", "Low"], vmin=0, vmax=4)
place = {(0, 1): "1  2  3  6", (0, 0): "4  8", (1, 1): "5  7"}
for (r, c), t in place.items(): ax.text(c + 0.5, r + 0.5, t, ha="center", va="center", fontsize=8.5, fontweight="bold", color="white" if r == 0 and c == 1 else INK)
ax.set_xlabel("likelihood", fontsize=7.5); ax.set_ylabel("impact", fontsize=7.5); ax.tick_params(length=0, labelsize=7); ax.grid(False)
fig.tight_layout(pad=0.4); save(fig, "f4_risk.png")

# ---------- F5 measured latency (slide 4)
L = R["latency"]; order = ["parse", "rules P1-P3", "taint + state", "markov", "fusion", "serialize"]; lab = ["JSON parse", "rules P1–P3", "taint + state", "Markov update", "fusion", "serialize"]
fig, ax = plt.subplots(figsize=(3.15, 1.4)); p50 = [L[k][0] for k in order]; p95 = [L[k][1] for k in order]
ax.barh(range(6), p50, color=C_DW, height=0.6, edgecolor=INK, lw=0.6)
for i, (a_, b_) in enumerate(zip(p50, p95)): ax.text(b_ + 0.04, i, f"{a_:.2f}", va="center", fontsize=6.5)
ax.set_yticks(range(6)); ax.set_yticklabels(lab, fontsize=6.5); ax.invert_yaxis(); ax.set_xlabel("µs per event (p50)", fontsize=7); ax.tick_params(axis="x", labelsize=6.5); ax.set_xlim(0, 3.1); ax.grid(axis="y", visible=False)
ax.set_title(f"total {L['total'][0]:.1f} µs p50, {L['total'][1]:.1f} µs p95", fontsize=7.5)
fig.tight_layout(pad=0.4); save(fig, "f5_latency.png")

# ---------- F8 detection by scenario (slide 5)
cold = R["cold"]; i3 = cold["n"].index(3)
sc = R["scen"]; d = R["drift"]
data = [("Prompt injection", 0, sc["A1"]["ml"], sc["A1"]["dw"]), ("Tool poisoning", 0, sc["A2"]["ml"], sc["A2"]["dw"]), ("Token replay", 0, sc["A3"]["ml"], sc["A3"]["dw"]),
        ("Slow drift", 0, d["ml"]["rate"], d["dw"]["rate"]), ("Mimicry", 0, sc["A5"]["ml"], sc["A5"]["dw"]), ("Sub-agent", 0, sc["A6"]["ml"], sc["A6"]["dw"]),
        ("New agent (3 sessions)", 0, cold["ml"][i3], cold["dw"][i3])]
df = pd.DataFrame([(n, s, v * 100) for n, i, m, w in data for s, v in (("Token + scope check", i), ("UEBA / ML-only", m), ("TETHER", w))], columns=["scenario", "system", "tpr"])
fig, ax = plt.subplots(figsize=(6.1, 1.68))
sns.barplot(df, x="scenario", y="tpr", hue="system", palette=[C_IAM, C_ML, C_DW], ax=ax, edgecolor=INK, linewidth=0.6, saturation=1)
for c in ax.containers: ax.bar_label(c, fmt="%.0f", fontsize=6.5, padding=1)
ax.set_ylim(0, 125); ax.set_ylabel("detection % at 1% FPR", fontsize=7.5); ax.set_xlabel(""); ax.tick_params(axis="x", labelsize=7.5); ax.tick_params(axis="y", labelsize=7); plt.setp(ax.get_xticklabels(), rotation=0)
ax.legend(fontsize=7, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.2)); ax.grid(axis="x", visible=False)
labels = [t.get_text() for t in ax.get_xticklabels()]; ax.set_xticklabels([l.replace(" (3 sessions)", "\n(3 sessions)").replace(" ", "\n", 1) if len(l) > 11 and "\n" not in l else l for l in labels])
fig.tight_layout(pad=0.4); save(fig, "f8_detect.png")

# ---------- F9 ROC (slide 5)
fig, ax = plt.subplots(figsize=(1.94, 1.42)); roc = R["roc"]
ax.plot(roc["ml"]["fpr"], roc["ml"]["tpr"], color=C_ML, lw=2, label=f"UEBA / ML-only  AUC {roc['ml']['auc']:.2f}")
ax.plot(roc["dw"]["fpr"], roc["dw"]["tpr"], color=C_DW, lw=2.4, label=f"TETHER  AUC {roc['dw']['auc']:.2f}")
ax.plot([0, 1], [0, 1], color=C_IAM, ls=":", lw=1); ax.axvline(0.01, color=INK, ls="--", lw=0.9); ax.text(0.02, 0.08, "1% FPR", fontsize=5.5)
ax.set_xlim(0, 0.2); ax.set_ylim(0, 1.03); ax.set_xlabel("false-positive rate", fontsize=6.5); ax.set_ylabel("true-positive rate", fontsize=6.5); ax.tick_params(labelsize=6); ax.set_xticks([0, 0.1, 0.2]); ax.legend(fontsize=5.5, loc="center right", bbox_to_anchor=(1.0, 0.42))
fig.tight_layout(pad=0.4); save(fig, "f9_roc.png")

# ---------- F10 cold start (slide 5)
fig, ax = plt.subplots(figsize=(1.94, 1.42)); xs = np.arange(len(cold["n"]))
ax.plot(xs, np.array(cold["ml"]) * 100, color=C_ML, lw=2, marker="s", label="UEBA / ML-only"); ax.plot(xs, np.array(cold["dw"]) * 100, color=C_DW, lw=2.4, marker="o", label="TETHER")
ax.set_xticks(xs); ax.set_xticklabels(cold["n"]); ax.set_ylim(0, 112); ax.set_xlabel("sessions of history", fontsize=6.5); ax.set_ylabel("detection %", fontsize=6.5); ax.tick_params(labelsize=6); ax.legend(fontsize=5.5, loc="upper right", bbox_to_anchor=(1.0, 0.62))
ax.annotate("Day-0 cover", xy=(0, cold["dw"][0] * 100), xytext=(0.3, 82), fontsize=5.5, arrowprops=dict(arrowstyle="->", color=INK))
fig.tight_layout(pad=0.4); save(fig, "f10_cold.png")

# ---------- F12 radar (slide 6)
axes = ["Declared role\nas reference", "Works with\nno history", "Injection\nby cause", "Resists\nmimicry", "Slow-drift\ndetection", "Chain\naccountability", "Explainable\nscore", "Graded\nresponse"]
S = {"TETHER": [5, 5, 5, 4, 4, 5, 5, 5], "UEBA / ML-only": [0, 0, 0, 0, 2, 0, 2, 0], "IAM / PAM": [2, 5, 0, 1, 0, 0, 0, 2], "Prompt guard": [0, 5, 3, 0, 0, 0, 0, 1]}
col = {"TETHER": C_DW, "UEBA / ML-only": C_ML, "IAM / PAM": C_IAM, "Prompt guard": C_AMB}
fig = plt.figure(figsize=(3.8, 2.55)); ax = fig.add_axes([0.26, 0.3, 0.48, 0.52], polar=True); ang = np.linspace(0, 2 * np.pi, len(axes), endpoint=False).tolist(); ang += ang[:1]
for n, v in S.items():
    vv = v + v[:1]; ax.plot(ang, vv, color=col[n], lw=2.6 if n == "TETHER" else 1.6, label=n); ax.fill(ang, vv, color=col[n], alpha=0.22 if n == "TETHER" else 0.05)
ax.set_xticks(ang[:-1]); ax.set_xticklabels(axes, fontsize=7); ax.tick_params(axis="x", pad=14); ax.set_yticks([1, 2, 3, 4, 5]); ax.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=7); ax.set_ylim(0, 5)
ax.grid(color=GRID); ax.spines["polar"].set_color(INK); ax.set_facecolor(BG)
fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncol=4, fontsize=7, frameon=False, bbox_to_anchor=(0.5, 0.0), columnspacing=0.9, handlelength=1.4)
save(fig, "f12_radar.png")

# ---------- F11 payload leaving before containment (slide 5)
sc = R["scen"]
labs = ["Injection", "Mimicry", "Poisoned\ntool"]; keys = ["A1", "A5", "A2"]
fig, ax = plt.subplots(figsize=(1.94, 1.42)); w = 0.26; xs = np.arange(3)
for j, (nm, key, col_) in enumerate((("Token + scope", "leak_iam", C_IAM), ("UEBA / ML", "leak_ml", C_ML), ("TETHER", "leak_dw", C_DW))):
    vals = [sc[k][key] * 100 for k in keys]
    ax.bar(xs + (j - 1) * w, vals, w, color=col_, label=nm, edgecolor=INK, lw=0.4)
    for x_, v in zip(xs + (j - 1) * w, vals): ax.text(x_, v + 2, f"{v:.0f}", ha="center", fontsize=5.5)
ax.set_xticks(xs); ax.set_xticklabels(labs, fontsize=6); ax.set_ylim(0, 128); ax.set_ylabel("payload out, %", fontsize=6.5); ax.tick_params(axis="y", labelsize=6); ax.grid(axis="x", visible=False)
ax.legend(fontsize=5.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.2), handlelength=1, columnspacing=0.6)
fig.tight_layout(pad=0.3); save(fig, "f11_leak.png")

# ---------- F13 roadmap with month periods (slide 6)
items = [("Native MCP / A2A extension", 0, 3, 0), ("LLM-made decoys per agent", 0, 3, 0), ("Real LLM agents on MCP (replace simulator)", 1, 3, 0),
         ("Federated peer baselines", 6, 12, 1), ("Cedar contracts + scope proofs", 6, 12, 1), ("Learned taint, tracking above 90%", 6, 12, 1),
         ("TPM / TEE-attested agent identity", 12, 18, 2), ("Agent risk score for insurers", 12, 18, 2), ("Cross-tenant poisoned-tool intel", 12, 18, 2)]
fig, ax = plt.subplots(figsize=(6.2, 1.85)); cols = [C_DW, C_AMB, C_IAM]
for lo, hi, c_ in ((0, 3, C_DW), (6, 12, C_AMB), (12, 18, C_IAM)): ax.axvspan(lo, hi, color=c_, alpha=0.10, lw=0)
for i, (n_, s_, e_, c_) in enumerate(items):
    ax.barh(i, e_ - s_, left=s_, color=cols[c_], height=0.62, edgecolor=INK, lw=0.5)
    ax.text((s_ + e_) / 2, i, (f"{s_}–{e_} mo" if e_ < 18 else "12 mo +"), ha="center", va="center", color="white", fontsize=6.5, fontweight="bold")
ax.set_yticks(range(len(items))); ax.set_yticklabels([x[0] for x in items], fontsize=7.5); ax.invert_yaxis()
ax.set_xlim(0, 18); ax.set_xticks([0, 3, 6, 9, 12, 15, 18]); ax.set_xticklabels(["0", "3", "6", "9", "12", "15", "18+"], fontsize=7.5); ax.set_xlabel("months after the prototype", fontsize=7.5); ax.grid(axis="y", visible=False)
for x_, t_, c_ in ((1.5, "NEXT", C_DW), (9, "MID TERM", C_AMB), (15, "LONG TERM", C_IAM)): ax.text(x_, -0.8, t_, ha="center", va="bottom", fontsize=7.5, fontweight="bold", color=c_)
ax.set_ylim(len(items) - 0.4, -1.3)
fig.tight_layout(pad=0.3); save(fig, "f13_roadmap.png")
print("figs ok")
