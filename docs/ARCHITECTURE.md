# Headless Daemon Code Agent — Architecture Plan

## Overview
A **headless daemon** that executes code tasks in isolated environments, controlled via a **PWA dashboard** with **approval gates** (captcha/human-in-the-loop) for sensitive operations.

---

## Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        PWA Dashboard (Client)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Task Queue  │  │ Live Logs   │  │ Approval UI │             │
│  │  (IndexedDB)│  │  (SSE/WS)   │  │ (Captcha)   │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
└─────────┼────────────────┼────────────────┼────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway (Node/Go)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Auth / JWT  │  │ Rate Limit  │  │ WebSocket   │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
└─────────┼────────────────┼────────────────┼────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Daemon Controller (Systemd/Docker)           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Task Orchestrator (Redis/BullMQ)            │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐   │   │
│  │  │ Queue   │ │ Retry   │ │ Priority│ │ Approval    │   │   │
│  │  │ Manager │ │ Logic   │ │ Scheduler│ │ Gateway     │   │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └──────┬──────┘   │   │
│  └───────┼───────────┼───────────┼────────────┼────────────┘   │
└──────────┼───────────┼───────────┼────────────┼────────────────┘
           │           │           │            │
           ▼           ▼           ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Execution Runners (Isolated)                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │  Node.js     │ │  Python      │ │  Browser     │            │
│  │  (vm2/isolate)│ │  (subproc)   │ │  (Playwright)│            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │  Go          │ │  Rust        │ │  Shell       │            │
│  │  (yaegi)     │ │  (rust-script)│ │  (firejail)  │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Models

### Task
```typescript
interface Task {
  id: string;                    // UUID
  type: 'code' | 'browser' | 'shell' | 'composite';
  payload: CodePayload | BrowserPayload | ShellPayload;
  priority: 'low' | 'normal' | 'high' | 'critical';
  status: 'pending' | 'queued' | 'running' | 'awaiting_approval' | 'completed' | 'failed';
  approvalRequired: boolean;
  approvalToken?: string;        // For captcha/human approval
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  result?: TaskResult;
  error?: string;
  logs: LogEntry[];
  metadata: Record<string, any>;
}
```

### Approval Gate (Captcha/Human)
```typescript
interface ApprovalRequest {
  taskId: string;
  type: 'captcha' | 'human_review' | '2fa' | 'policy_check';
  challenge: string;             // Captcha sitekey, policy rule, etc.
  context: Record<string, any>;  // What the task wants to do
  expiresAt: Date;
  callbackUrl: string;           // Where to POST approval result
}
```

---

## PWA Features

| Feature | Implementation |
|---------|----------------|
| **Offline Queue** | IndexedDB + Background Sync API |
| **Push Notifications** | Web Push (VAPID) for task completion/approval needed |
| **Installable** | Web App Manifest + Service Worker |
| **Real-time Updates** | Server-Sent Events (SSE) or WebSocket |
| **Biometric Auth** | WebAuthn for sensitive approvals |

---

## Security Model

1. **Daemon runs as non-root user** in container/VM
2. **Each runner isolated**: gVisor / firejail / Docker --security-opt
3. **Network egress controlled**: allowlist only
4. **File system**: read-only root, tmpfs for workspace
5. **Approval gates**: No external network/action without approval
6. **Audit log**: Immutable append-only log (sqlite + WAL / CloudWatch)

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| **API** | Fastify (Node) / Go (Chi) | Low overhead, WebSocket native |
| **Queue** | BullMQ (Redis) | Priority, retries, delayed jobs |
| **Runners** | Node vm2, Python subprocess, Playwright, firejail | Mature isolation |
| **PWA** | Vite + React/Preact + TypeScript | Small bundle, fast HMR |
| **SW** | Workbox (GenerateSW) | Offline, caching strategies |
| **Auth** | JWT + WebAuthn | Stateless, hardware-backed |
| **Deploy** | Docker Compose / systemd | Simple, portable |

---

## Phase 1: MVP (Week 1-2)
- [ ] Daemon skeleton + task queue (Redis + BullMQ)
- [ ] Node.js runner (vm2) + Python runner (subprocess)
- [ ] REST API: submit task, get status, stream logs
- [ ] Basic approval gate (dummy captcha)
- [ ] PWA: task list, submit form, live logs (SSE)
- [ ] Manifest + Service Worker (offline queue)

## Phase 2: Hardening (Week 3)
- [ ] Browser runner (Playwright + CDP)
- [ ] Real captcha (hCaptcha/turnstile) + WebAuthn
- [ ] Policy engine (OPA/Rego) for auto-approval
- [ ] Resource limits (CPU, RAM, time, network)
- [ ] Audit logging + metrics (Prometheus)

## Phase 3: Scale (Week 4+)
- [ ] Multi-tenant / namespaces
- [ ] Runner autoscaling (K8s / nomad)
- [ ] Scheduled tasks / cron
- [ ] GitHub webhook → auto-deploy tasks
- [ ] Plugin system for custom runners

---

## File Structure (Monorepo)

```
headless-agent/
├── daemon/                 # Daemon controller (Node/Go)
│   ├── src/
│   │   ├── orchestrator.ts
│   │   ├── queue.ts
│   │   ├── runners/
│   │   │   ├── node.ts
│   │   │   ├── python.ts
│   │   │   ├── browser.ts
│   │   │   └── shell.ts
│   │   ├── approval/
│   │   │   ├── captcha.ts
│   │   │   ├── webauthn.ts
│   │   │   └── policy.ts
│   │   └── api/
│   │       ├── routes.ts
│   │       └── websocket.ts
│   └── Dockerfile
│
├── pwa/                    # PWA Dashboard
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── sw/
│   ├── public/
│   │   └── manifest.json
│   ├── index.html
│   ├── vite.config.ts
│   └── Dockerfile
│
├── shared/                 # Shared types (TypeScript)
│   └── types.ts
│
├── docker-compose.yml
├── README.md
└── package.json            # Root workspace
```

---

## Next Steps
1. **Create `manifest.json`** (PWA manifest)
2. **Scaffold PWA** (Vite + React + TS + Workbox)
3. **Scaffold Daemon** (Fastify + BullMQ + Runners)
4. **Wire approval flow** (captcha → webhook → resume task)
