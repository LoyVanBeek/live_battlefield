# Tunneling Options for Live Battleship on a Raspberry Pi

Date: 2026-09-06
Status: Decision record (Option B chosen)

## 1. Goal & Constraints

- Host the existing Docker app (`app` + `postgres` + `pgadmin`, `docker-compose.yml`) on a
  Raspberry Pi at home.
- Players need a **public, stable HTTPS URL** for the team board, GM panel, and locations page.
- The app needs **server-sent events** (`team.html:1608`, `EventSource('/api/events/stream...')`)
  with a polling fallback — the tunnel must not buffer/break streaming.
- **No app changes needed** for a new hostname: share/join/TG links are built from
  `window.location.origin` (`team.html:1109`, `game_master.html:876,1109`).
- DNS for the domain stays at **TransIP.nl** — the user will **not** move nameservers.
- Prefer **free**, then cheap; URL must be **stable** across restarts.
- The tunnel must run without open inbound ports on the Pi (CGNAT/home router friendly).

## 2. The Four Services First Asked About

| Service | Mechanics | Free tier | Stable URL cost | Caveats |
|---|---|---|---|---|
| **localhost.run** | SSH outbound (`ssh -R 80:localhost:8000 lhr.life`) | Free hostname **rotates** on each connect; speed-capped | ~$9/mo (yearly) for reserved hostname | Key-based auth via SSH; Europe-friendly? no, operator outside EU |
| **localtunnel** | Node client, public server | Random subdomains, flaky public server | unreliable; self-host for custom | public server often down/blocked (CF 403s) |
| **serveo.net** | SSH outbound, single operator | Free | not offered (was free-only) | historically down for long stretches; single operator risk |
| **pinggy.io** | SSH or TCP (`ssh -p 443 -R0:app:8000 <token>@proxy.pinggy.io`) | Free URL **expires after 60 min** | **Pro ~$2.50–3/mo** for persistent URL + custom domain | see Option A |

Common point: the free tiers all fail the "**stable URL**" requirement. Paid tiers give
persistent URLs; only Pinggy pairs that with a **single CNAME record** (no nameserver move).

## 3. Why Cloudflare Tunnel Is Ruled Out

- Free plan = **Full setup** — requires the nameserver move the user refuses.
- **Partial (CNAME) setup** exists only on the **Business** plan (~$200/mo).
- *Cloudflare for SaaS* lets you serve *other* people's domains — not your own.
- Verdict: needs either a nameserver move or Business money → **not compatible** with
  "keep DNS at TransIP".

## 4. Option A — Pinggy Pro + one CNAME at TransIP (~$3/mo)

Rewires one DNS **record** at TransIP (not the nameservers).

### TransIP DNS panel (transip.nl → dashboard → domain → DNS)
1. Make sure **"TransIP settings"** (reverse proxy/redirect layer) is **disabled** for the domain —
   otherwise it intercepts the CNAME.
2. Add a **CNAME** record:
   - Host: `battle` → `battle.<yourdomain>.nl`
   - Target/alias: `xxxxxxxx.a.pinggy.link` (shown in the Pinggy dashboard → Domains)
   - TTL: `600`
   - Keep the rest of the DNS untouched.

### Pinggy dashboard
3. Domains → Add Custom Domain → validate `battle.<yourdomain>.nl` (Pinggy does an HTTPS probe
   against your CNAME).
4. Let's Encrypt certificate is issued automatically on validation.

### Compose swap (`docker-compose.yml:48-56`)
Replace the `ngrok` service with:

```yaml
  tunnel:
    image: pinggy/pinggy
    depends_on:
      - app
    environment:
      - PINGGY_TOKEN=${PINGGY_TOKEN}
    command: -p app:8000 -R0:app:8000 ${PINGGY_TOKEN}@pro.pinggy.io
```

`.env`: drop `NGROK_AUTHTOKEN`/`NGROK_DOMAIN`, add `PINGGY_TOKEN=...`.

## 5. Option B — Tailscale Funnel (CHOSEN 🟢)

Free, stable URL, zero DNS changes, no open inbound ports, no cert management. Visitors need no
Tailscale account — any browser reaches the app.

### How it works
1. A public visitor resolves your name → **Funnel ingress** (Tailscale-operated, georeplicated
   relay frontends, separate from the DERP/VPN relays).
2. The ingress sends a "connection offer" to your Pi *over the Tailscale mesh* (via Tailscale's
   `peerapi`; the TCP path is handled in-kernel, so the ingress gets no tailnet packet access).
3. Your Pi's `tailscaled` accepts the connection, **terminates TLS on-device**, and reverse-proxies
   to `http://127.0.0.1:8000`.

Tailscale sees the TLS handshake at the edge, but content is decrypted **on the Pi** and the
Pi↔Tailscale leg is re-encrypted over WireGuard — a cleaner trust story than edge MITM.

### Setup
```bash
# on the Pi, as root
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
sudo tailscale funnel --bg 8000          # first run opens a web approval prompt
tailscale funnel status                  # inspect current config
sudo tailscale funnel reset              # remove all funnels
```

Prerequisites (default for new tailnets): Tailscale ≥ v1.38.3, MagicDNS + HTTPS enabled, and a
`funnel` node attribute in the tailnet policy (auto-added on first approval).

Behavior:
- Public URL: `https://<pi-name>.<tailnet>.ts.net` — **stable**; with `--bg` it survives reboots
  and `tailscale down/up` automatically (foreground mode would need manual restart).
- Runs as a host service (systemd), not a Compose service — app's `ports: "8000:8000"` is reused.
- Useful flags: `--set-path=/`, `--tcp=`, `--tls-terminated-tcp=`, `--proxy-protocol=2`, `--yes`.

### Limits & caveats
- **Allowed public ports: `443`, `8443`, `10000`** only (not just 443). `tailscale funnel 8000`
  uses 443 for HTTPS by default.
- **Names only in `*.ts.net`** — Funnel cannot serve your own domain (its custom-domain support is
  Tailscale-side and needs cooperating DNS, incompatible with keeping DNS at TransIP).
- **Non-configurable bandwidth cap** per funnel — built for sharing a service, not sustained high
  throughput. Field reports measure ~110 KB/s on fully-relayed paths — fine for this game (light
  API + SSE, small player count), not media-grade.
- **No authentication layer in front** by design — anyone with the URL reaches the app (players
  need public access anyway; the app's own safeguards apply).
- **SSE works**: Funnel reverse-proxies plain HTTP including streaming, and the app keeps its
  polling fallback. Relay adds tens of ms latency — negligible here.
- **Let's Encrypt rate limits**: churning certs can block new certs for ~34 h; don't reconfigure
  the `*.ts.net` name repeatedly before tests.
- **Jurisdiction note:** Tailscale is a **US company** (GDPR via SCC/DPA; optional EU data region
  for coordination). Accepted — see §6.
- **Plans:** Funnel is included in the free **Personal** plan (up to 6 users) — no cost for a
  single-Pi setup. (Business tiers are seat-based: Standard $8/user/mo, Premium $18/user/mo.)
- No TransIP involvement at all; the `.ts.net` link is shared with players.

## 6. EU-Based Options (verified jurisdictions)

Criteria accepted: *(a) data in EU datacenters* **or** *(b) EU company + GDPR*. Both satisfied
cleanly by these:

### 6.1 NetBird — Berlin, Germany 🇩🇪 (EU Tailscale-Funnel equivalent)
- **NetBird GmbH**, Rosenthaler Str. 36, 10178 Berlin; HRB 237529 B; WireGuard-based;
  open source (BSD-3); processes data in the **EU/EEA**.
- Funnel-equivalent: **"Expose"** publishes local services to the public internet with a stable
  HTTPS URL. **Dashboard services are persistent** (like Funnel); the CLI form (`netbird expose`)
  is ephemeral (90 s TTL, auto-renewed every 30 s).
- Custom domains supported; free tier exists for personal use.
- If the EU requirement ever becomes primary: drop-in Tailscale-Funnel replacement.

### 6.2 Expose — German developer (Beyond Code), EU datacenter 🇩🇪
- Open-source ngrok alternative (PHP) + managed SaaS. **Free tier runs on a single EU server
  (Germany)** but gives **time-limited random URLs** → *not* stable.
- **Pro** plan gives persistent URLs + custom domains + global edge network (paid; pricier than
  Pinggy). Its open core can also be **self-hosted** (PHP/node).

### 6.3 Self-hosted on a small EU VPS (fully EU, stable URL, own domain) — cleanest
- Rent a tiny EU VPS (Hetzner DE ~€4/mo, TransIP NL, Ionos DE) and run open-source tunnel
  software: **frp, chisel, sish, inlets, zrok** (or Expose core).
- Keep TransIP DNS: point one subdomain (`battle.<yourdomain>.nl`) via **A/CNAME** at the VPS —
  a record add, not a nameserver move. Stable HTTPS via Caddy/nginx + Let's Encrypt on the VPS.
- Data stays in the EU, software is free, full control, no per-month tunnel SaaS fees.
- Only real cost: the VPS (~€4/mo) + you operate it.

## 7. Recommendation & Decision Record

- **Decision: Option B — Tailscale Funnel (free, stable URL, zero DNS changes).**
- Accepted assumption: EU = *data in EU datacenters* OR *EU company/GDPR* — both acceptable.
  Tailscale (US, EU data-region option) is fine under that reading; use **NetBird** (Berlin)
  if a stricter *EU-managed* service is ever wanted, or §6.3 if you want the URL to be
  `battle.<yourdomain>.nl` again.
- The `windows.location.origin` link-building means the `.ts.net` URL is perfectly usable with
  zero app changes.

## 8. Next Steps & Verification

1. On the Pi: `tailscale up` + `tailscale funnel --bg 8000`; note the `https://<name>.ts.net` URL.
2. Check SSE through the tunnel: run the Playwright probe (cf. `verify_nl_toast.py`) against the
   public URL — verify events stream and polling fallback work.
3. If tunnel != ngrok later, update:
   - `README.md:81-119` (ngrok setup + diagram),
   - `scripts/get-public-url.sh` (currently queries `ngrok:4040/api/tunnels`),
   - `tests/conftest.py:5` (`NGROK_AUTHTOKEN` default),
   - `.env.example` / `.env` (ngrok vars).
4. Share the public URL with players (team board, GM panel, locations page).