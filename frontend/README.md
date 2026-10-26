# TETHER console

React 18 + Vite + three.js (react-three-fiber, drei, postprocessing). Pages: landing, console, attack lab, alerts, approvals, contracts, upside-down, chain, ledger, coverage, benchmarks.

```bash
npm install
npm run dev        # http://localhost:5173 (proxies /api and /ws to :8000)
npm run build      # outputs dist/, which the backend serves in production
```

By default the UI talks to the same origin. For a split deploy set `VITE_API_URL=https://your-backend` (see `.env.example` and `../docs/DEPLOY.md`).

`src/store.js` holds the WebSocket client and a small external store (renders are batched to ~5/s). 3D scenes lower their quality automatically when the frame rate drops.
