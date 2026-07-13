# Headless Agent Swarm 🤖

**Autonomous code agent platform with approval-gated execution, real-time WebSocket UI, and OpenCode integration.**

Deploy to your own infrastructure via **Coolify + GitHub** in minutes.

---

## 🚀 Quick Deploy (Coolify + GitHub)

### 1. Fork this repo to your GitHub account

### 2. In Coolify:
- **New Resource → Application → Docker Compose**
- **Repository**: `your-username/headless-agent`
- **Branch**: `main`
- **Docker Compose File**: `docker-compose.yml`
- **Build Pack**: `Dockerfile`
- **Port**: `8000` (API) + `3000` (PWA)

### 3. Add Environment Variables in Coolify:
```env
REDIS_URL=redis://redis:6379/0
LOG_LEVEL=INFO
MAX_CONCURRENT_TASKS=10
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Deploy! 🎉

---

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PWA UI    │────▶│   FastAPI   │────▶│   Redis     │
│  (React/TS) │◀───│  + WebSocket│◀───│  (Queue)    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  Agent Pool │
                    │  (OpenCode) │
                    └─────────────┘
```

| Component | Tech | Purpose |
|-----------|------|---------|
| **PWA** | Vite + React + TS + Workbox | Offline-capable dashboard |
| **API** | FastAPI + Uvicorn | REST + WebSocket server |
| **Queue** | Redis Streams | Task distribution |
| **Agents** | OpenCode CLI | Autonomous code execution |
| **Auth** | JWT + WebSocket | Secure agent/client auth |

---

## 🔌 API Endpoints

### Tasks
```bash
# Create task
curl -X POST http://your-server:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"type": "opencode", "payload": {"prompt": "Fix auth bug"}, "requires_approval": true}'

# List tasks
curl http://your-server:8000/api/tasks

# Get task details
curl http://your-server:8000/api/tasks/{task_id}
```

### Approvals
```bash
# List pending
curl http://your-server:8000/api/approvals

# Approve
curl -X POST http://your-server:8000/api/approvals/{id}/approve

# Reject
curl -X POST http://your-server:8000/api/approvals/{id}/reject
```

### Agents
```bash
# Register agent
curl -X POST http://your-server:8000/api/agents/register \
  -d '{"id": "agent-1", "capabilities": ["shell", "git", "opencode"]}'

# WebSocket: ws://your-server:8000/ws/agent/{agent_id}
```

### WebSocket (Client)
```javascript
const ws = new WebSocket('ws://your-server:8000/ws/client');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
// Receives: task updates, approval requests, logs, agent status
```

---

## 🤖 Agent Types

| Type | Capabilities | Use Case |
|------|-------------|----------|
| `shell` | Command execution | Scripts, builds, deploys |
| `opencode` | AI code generation | Feature dev, refactoring |
| `git` | Git operations | Commits, merges, PRs |
| `file_read/write` | FS access | Config, code edits |
| `http` | API calls | Webhooks, integrations |

---

## 🔐 Approval Gates

Tasks with `requires_approval: true` pause at `WAITING_APPROVAL` status.
PWA shows captcha-style challenges for sensitive operations:

- **Command execution** → Show command + args, require confirmation
- **File write** → Show diff preview
- **Network call** → Show URL + payload
- **Deploy** → Require 2FA-style confirmation

Auto-approve rules configurable via API.

---

## 📦 Local Development

```bash
# Prereqs: Docker, Node 20, Python 3.12

# 1. Start infrastructure
docker compose up -d redis

# 2. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd ../pwa
npm install
npm run dev  # http://localhost:5173
```

---

## 🐳 Docker Compose Profiles

```bash
# Core only (API + Redis + PWA)
docker compose up -d

# With OpenCode agent sidecar
docker compose --profile agents up -d

# With monitoring
docker compose --profile monitoring up -d
```

---

## 📊 Monitoring

- **Prometheus**: `:9090` (metrics)
- **Grafana**: `:3001` (dashboards)
- **Health**: `GET /health`
- **Metrics**: `GET /metrics` (Prometheus format)

---

## 🛡️ Security

- All WebSocket connections require JWT auth
- Agents register with capability tokens
- Approvals logged with resolver identity
- Rate limiting on REST endpoints
- CORS configurable via env

---

## 📁 Project Structure

```
headless-agent/
├── .github/workflows/     # CI/CD
├── backend/
│   ├── app/
│   │   ├── main.py        # FastAPI app
│   │   ├── models.py      # Pydantic models
│   │   ├── ws.py          # WebSocket handlers
│   │   ├── queue.py       # Task queue
│   │   ├── approvals.py   # Approval engine
│   │   └── agents.py      # Agent registry
│   ├── requirements.txt
│   └── Dockerfile
├── pwa/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Dashboard, Tasks, Approvals, Logs
│   │   ├── hooks/         # useWebSocket, useToast
│   │   ├── store/         # Zustand state
│   │   └── types/         # TypeScript types
│   ├── public/manifest.json
│   ├── vite.config.ts
│   └── package.json
├── docker-compose.yml
├── deploy.sh              # One-shot deploy
└── README.md
```

---

## 🤝 Contributing

```bash
git clone https://github.com/your-username/headless-agent.git
cd headless-agent
# Make changes
git commit -am "feat: amazing feature"
git push origin main
# Coolify auto-deploys on push to main
```

---

## 📄 License

MIT — Use freely, contribute back.

---

## 🆘 Support

- **Issues**: GitHub Issues
- **Discord**: [Join Community](https://discord.gg/your-invite)
- **Docs**: `/docs` folder (WIP)
