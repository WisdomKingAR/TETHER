// Tiny external store + websocket client. One immutable state object, batched per animation frame.
import { useSyncExternalStore } from "react";

let state = {
  connected: false, agents: {}, order: [], events: [], alerts: {}, runs: {}, activeRun: null, mode: "enforce", paused: false, speed: 1,
  counts: { events: 0, flagged: 0, sandboxed: 0, leaked: 0 }, series: {}, toasts: [], pulses: [], lastAlert: null, autopilot: false, pendingCount: 0, shock: 0, fired: null,
};
const subs = new Set();
let pending = null, raf = 0;
const emit = () => subs.forEach((f) => f());
function flush() {
  if (!pending) return;
  state = { ...state, ...pending }; pending = null; raf = 0; emit();
}
function commit(patch) {
  pending = { ...(pending || {}), ...patch };
  if (!raf) { raf = 1; setTimeout(flush, 180); }   // batch websocket bursts: at most ~5 renders per second
}
const cur = () => ({ ...state, ...(pending || {}) });

export const useStore = () => useSyncExternalStore((f) => { subs.add(f); return () => subs.delete(f); }, () => state);
export const getState = () => cur();
export const updateStore = (patch) => commit(patch);

const pushToast = (t) => {
  const id = Math.random().toString(36).slice(2);
  commit({ toasts: [...cur().toasts, { id, ...t }].slice(-4) });
  setTimeout(() => commit({ toasts: cur().toasts.filter((x) => x.id !== id) }), 6000);
};

export function pollRun(runId, onDone) {
  let attempts = 0;
  const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
  const timer = setInterval(async () => {
    attempts++;
    try {
      const res = await fetch(`${base}/api/runs/${runId}`);
      if (res.ok) {
        const r = await res.json();
        const s = cur();
        commit({ runs: { ...s.runs, [runId]: r }, activeRun: runId });
        if (r.status === "done" || attempts > 50) {
          clearInterval(timer);
          if (onDone) onDone(r);
        }
      } else if (attempts > 50) {
        clearInterval(timer);
      }
    } catch (_) {
      if (attempts > 50) clearInterval(timer);
    }
  }, 900);
  return () => clearInterval(timer);
}

export function syncState(data) {
  if (!data) return;
  const s = cur();
  const agents = { ...s.agents };
  if (data.agents) {
    data.agents.forEach((a) => (agents[a.id] = a));
  }
  let counts = s.counts;
  if (data.counts) {
    counts = {
      events: Math.max(s.counts.events, data.counts.events || 0),
      flagged: Math.max(s.counts.flagged, data.counts.flagged || 0),
      sandboxed: Math.max(s.counts.sandboxed, data.counts.sandboxed || 0),
      leaked: Math.max(s.counts.leaked, data.counts.leaked || 0),
    };
  }
  commit({
    agents,
    counts,
    order: data.agents ? data.agents.map((a) => a.id) : s.order,
    mode: typeof data.enforce === "boolean" ? (data.enforce ? "enforce" : "shadow") : s.mode,
    pendingCount: typeof data.pending === "number" ? data.pending : s.pendingCount,
  });
}

export function recordEvent(m) {
  if (m) onMessage(m);
}

function onMessage(m) {
  const s = cur();
  if (m.type === "hello") {
    const agents = {}; m.snapshot.agents.forEach((a) => (agents[a.id] = a));
    const series = {}; const events = (m.tail || []).slice(-80).reverse();
    (m.tail || []).forEach((e) => { (series[e.agent] ||= []).push({ id: e.id, risk: e.agent_risk, ev: e.risk, level: e.level }); });
    Object.keys(series).forEach((k) => (series[k] = series[k].slice(-90)));
    const runs = {}; (m.runs || []).forEach((r) => (runs[r.id] = r));
    let evCount = m.snapshot.events || 0;
    let flCount = 0, sbCount = 0, lkCount = 0;
    m.snapshot.agents.forEach((a) => {
      if (a.stats) {
        flCount += a.stats.flagged || 0;
        sbCount += a.stats.sandboxed || 0;
        lkCount += a.stats.leaked || 0;
      }
    });
    const counts = m.snapshot.counts || { events: evCount, flagged: flCount, sandboxed: sbCount, leaked: lkCount };
    commit({ connected: true, autopilot: !!m.autopilot, pendingCount: (m.pending || []).length, agents, order: m.snapshot.agents.map((a) => a.id), mode: m.snapshot.enforce ? "enforce" : "shadow", events, series, runs, counts });
  } else if (m.type === "event") {
    const agents = { ...s.agents, [m.agent]: m.agent_state };
    const series = { ...s.series }; series[m.agent] = [...(series[m.agent] || []), { id: m.id, risk: m.agent_risk, ev: m.risk, level: m.level }].slice(-90);
    const counts = { ...s.counts, events: s.counts.events + 1, flagged: s.counts.flagged + (m.risky ? 1 : 0), sandboxed: s.counts.sandboxed + ((m.verdict.includes("ISOLATE") || m.verdict.includes("SANDBOX")) ? 1 : 0), leaked: s.counts.leaked + m.leaked };
    const pulses = [...s.pulses, { id: m.id, agent: m.agent, risk: m.risk, bad: m.risky, t: performance.now() }].slice(-12);
    commit({ agents, series, counts, pulses, events: [m, ...s.events].slice(0, 120), pendingCount: s.pendingCount + ((m.verdict === "CLIP_HELD" || m.verdict === "STEP_UP") ? 1 : 0), shock: m.escalated && m.level >= 3 ? s.shock + 1 : s.shock });
  } else if (m.type === "alert") {
    const alerts = { ...s.alerts, [m.alert.id]: m.alert };
    commit({ alerts, lastAlert: m.alert.id });
    if (m.new) pushToast({ kind: "alert", title: `${m.alert.id} · ${m.alert.display}`, body: m.alert.reasons[0] || "behaviour left the declared role", to: `/alerts/${m.alert.id}` });
  } else if (m.type === "spawned") commit({ agents: { ...s.agents, [m.agent.id]: m.agent }, order: m.order });
  else if (m.type === "removed") { const agents = { ...s.agents }; delete agents[m.id]; commit({ agents, order: m.order }); }
  else if (m.type === "autopilot") commit({ autopilot: m.on });
  else if (m.type === "autopilot_fired") { commit({ fired: m }); pushToast({ kind: "red", title: "Red-team autopilot", body: "Launching: " + m.title, to: "/lab" }); }
  else if (m.type === "approval") commit({ pendingCount: Math.max(0, s.pendingCount - 1), agents: { ...s.agents, [m.agent.id]: m.agent } });
  else if (m.type === "pending_update") commit({ pendingCount: m.count });
  else if (m.type === "agent") {
    commit({ agents: { ...s.agents, [m.agent.id]: m.agent } });
  } else if (m.type === "mode") commit({ mode: m.enforce ? "enforce" : "shadow" });
  else if (m.type === "sim") commit({ paused: m.paused, speed: m.speed });
  else if (m.type === "run_start") {
    const existing = s.runs[m.run.id] || {};
    commit({
      runs: { ...s.runs, [m.run.id]: { ...existing, ...m.run, steps: m.steps || m.run.steps || existing.steps || [], results: existing.results || [] } },
      activeRun: m.run.id
    });
  } else if (m.type === "run_step") {
    const r = s.runs[m.run_id]; if (!r) return;
    const results = [...(r.results || [])];
    const idx = results.findIndex((x) => x.i === m.i);
    if (idx >= 0) results[idx] = m;
    else results.push(m);
    commit({ runs: { ...s.runs, [m.run_id]: { ...r, results } } });
  } else if (m.type === "run_end") {
    const r = s.runs[m.run_id]; if (!r) return;
    commit({ runs: { ...s.runs, [m.run_id]: { ...r, summary: m.summary, status: "done" } } });
  } else if (m.type === "reset") {
    const agents = {}; m.snapshot.agents.forEach((a) => (agents[a.id] = a));
    commit({ agents, events: [], alerts: {}, runs: {}, series: {}, counts: { events: 0, flagged: 0, sandboxed: 0, leaked: 0 }, activeRun: null, pendingCount: 0 });
  }
}

let ws, retry = 0;

function connectSSE(base) {
  const url = (base || "") + "/api/stream";
  const es = new EventSource(url);
  es.onmessage = (e) => { try { onMessage(JSON.parse(e.data)); } catch (err) { console.error(err); } };
  es.onerror = () => {
    commit({ connected: false });
    es.close();
    setTimeout(() => connectSSE(base), Math.min(4000, 500 * ++retry));
  };
}

export function connect() {
  const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
  const url = base
    ? base.replace(/^http/, "ws") + "/ws"
    : (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";

  let settled = false;

  // Give the WebSocket 3 s to open. If it doesn't (Vercel serverless), fall back to SSE.
  const fallbackTimer = setTimeout(() => {
    if (!settled) {
      settled = true;
      try { ws.close(); } catch (_) {}
      connectSSE(base);
    }
  }, 3000);

  ws = new WebSocket(url);
  ws.onopen = () => {
    settled = true;
    clearTimeout(fallbackTimer);
    retry = 0;
  };
  ws.onmessage = (e) => { try { onMessage(JSON.parse(e.data)); } catch (err) { console.error(err); } };
  ws.onclose = () => {
    clearTimeout(fallbackTimer);
    commit({ connected: false });
    if (settled) {
      // Normal reconnect on Render / local dev
      setTimeout(connect, Math.min(4000, 500 * ++retry));
    }
    // If not settled, fallbackTimer already fired or will fire → SSE path
  };
}
export const toast = pushToast;
