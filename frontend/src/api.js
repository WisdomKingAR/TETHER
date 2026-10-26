// Same-origin by default (Render serves the app + API together, Vite proxies in dev).
// For a split deploy (Vercel UI + separate backend) set VITE_API_URL=https://your-backend.onrender.com
export const API = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const U = (u) => (u.startsWith("/") ? API + u : u);
const j = async (r) => { if (!r.ok) throw new Error((await r.text()) || r.statusText); return r.json(); };
const send = (method, url, body) => fetch(U(url), { method, headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined }).then(j);
export const api = {
  get: (u) => fetch(U(u)).then(j),
  post: (u, b) => send("POST", u, b || {}),
  put: (u, b) => send("PUT", u, b),
  del: (u) => send("DELETE", u),
};

export const LEVEL_COLORS = ["#6cc58a", "#e8c34a", "#f08a3c", "#ff3b3b", "#9b1c4a"];
export const LEVEL_NAMES = ["ALLOW", "WATCH", "CLIP", "ISOLATE", "REVOKE"];
export const PLANE_LABEL = { scope: "Scope (P1)", taint: "Taint (P2)", seq: "Sequence (P4)", cusum: "CUSUM (P6)", chain: "Chain (P5)", p1: "Role contract", p2: "Provenance", p3: "Decoy", p4: "Behaviour", p5: "Delegation", p6: "Slow drift", pid: "Identity proof" };
export const PLANE_COLOR = { scope: "#ff4a4a", taint: "#ff8a3c", seq: "#7fd4ff", cusum: "#6cc58a", chain: "#c08bff", p1: "#ff4a4a", p2: "#ff8a3c", p3: "#e8c34a", p4: "#7fd4ff", p5: "#c08bff", p6: "#6cc58a", pid: "#ff6fb1" };
export const OWASP = { p1: ["ASI02 Tool misuse", "LLM06 Excessive agency"], p2: ["ASI01 Goal hijack", "LLM01 Prompt injection"], p3: ["ASI10 Rogue agent"], pid: ["ASI03 Identity abuse"], p5: ["ASI07 Inter-agent trust"], p6: ["ASI10 Rogue agent"], p4: ["ASI08 Cascading failure"] };
export const fmtBytes = (b) => (b >= 1e6 ? (b / 1e6).toFixed(1) + " MB" : b >= 1e3 ? Math.round(b / 1e3) + " KB" : Math.round(b) + " B");
export const clock = (ts) => new Date(ts * 1000).toLocaleTimeString([], { hour12: false });
export const verdictClass = (v) => (!v ? "bad" : v.includes("ALLOW") ? "ok" : (v.includes("ISOLATE") || v.includes("SANDBOX")) ? "sand" : (v.includes("CLIP_HELD") || v.includes("STEP") || v.includes("WATCH")) ? "warn" : v.includes("SHADOW") ? "shadow" : "bad");

