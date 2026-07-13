"""
Headless Agent Swarm Backend
FastAPI + WebSocket + Redis + OpenCode integration
"""
import os
import asyncio
import json
import uuid
import time
import subprocess
import signal
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set, Callable
from enum import Enum
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings
import redis.asyncio as redis
import logging
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    ws_heartbeat_interval: int = 30
    task_timeout: int = 300
    max_concurrent_tasks: int = 10
    opencode_bin: str = "opencode"
    log_level: str = "INFO"
    static_dir: str = "../pwa/dist"
    
    model_config = ConfigDict(env_file=".env", extra="ignore")

settings = Settings()
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(int(settings.log_level) if isinstance(settings.log_level, str) and settings.log_level.isdigit() else getattr(logging, settings.log_level.upper(), 20)),
    processors=[structlog.processors.JSONRenderer()]
)
log = structlog.get_logger()

# ──────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────
TASKS_CREATED = Counter("tasks_created_total", "Total tasks created", ["type"])
TASKS_COMPLETED = Counter("tasks_completed_total", "Total tasks completed", ["status"])
TASK_DURATION = Histogram("task_duration_seconds", "Task execution time")
ACTIVE_AGENTS = Gauge("active_agents", "Number of connected agents")
WS_CONNECTIONS = Gauge("ws_connections", "Active WebSocket connections")

# ──────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────
class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskType(str, Enum):
    SHELL = "shell"
    OPENCODE = "opencode"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    GIT = "git"
    HTTP = "http"
    CUSTOM = "custom"

class ApprovalType(str, Enum):
    COMMAND = "command"
    FILE_WRITE = "file_write"
    NETWORK = "network"
    SENSITIVE = "sensitive"
    DEPLOY = "deploy"

class TaskBase(BaseModel):
    type: TaskType
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    timeout: int = 300
    requires_approval: bool = False
    approval_type: Optional[ApprovalType] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TaskCreate(TaskBase):
    pass

class Task(TaskBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = Field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    assigned_agent: Optional[str] = None
    approval_request_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    child_task_ids: List[str] = Field(default_factory=list)

class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    type: ApprovalType
    title: str
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending, approved, rejected, expired
    created_at: float = Field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolver: Optional[str] = None  # "human" | "auto"

class AgentInfo(BaseModel):
    id: str
    name: str
    capabilities: List[str] = Field(default_factory=list)
    status: str = "idle"  # idle, busy, offline
    current_task: Optional[str] = None
    connected_at: float = Field(default_factory=time.time)
    last_heartbeat: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class WSMessage(BaseModel):
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None

# ──────────────────────────────────────────────
# State Management
# ──────────────────────────────────────────────
class SwarmState:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.approvals: Dict[str, ApprovalRequest] = {}
        self.agents: Dict[str, AgentInfo] = {}
        self.ws_connections: Dict[str, Set[WebSocket]] = {}  # agent_id -> {ws}
        self.subscriptions: Dict[str, Set[WebSocket]] = {}  # topic -> {ws}
        self.redis: Optional[redis.Redis] = None
        self._lock = asyncio.Lock()

    async def init_redis(self):
        self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        await self.redis.ping()
        log.info("redis_connected", url=settings.redis_url)

    async def close_redis(self):
        if self.redis:
            await self.redis.close()

state = SwarmState()

# ──────────────────────────────────────────────
# WebSocket Manager
# ──────────────────────────────────────────────
class WSManager:
    def __init__(self):
        self.agent_ws: Dict[str, WebSocket] = {}
        self.client_ws: Set[WebSocket] = set()
        
    async def connect_agent(self, agent_id: str, ws: WebSocket):
        await ws.accept()
        self.agent_ws[agent_id] = ws
        WS_CONNECTIONS.inc()
        log.info("agent_connected", agent_id=agent_id)
        
    async def connect_client(self, ws: WebSocket):
        await ws.accept()
        self.client_ws.add(ws)
        WS_CONNECTIONS.inc()
        
    def disconnect_agent(self, agent_id: str):
        if agent_id in self.agent_ws:
            del self.agent_ws[agent_id]
            WS_CONNECTIONS.dec()
            
    def disconnect_client(self, ws: WebSocket):
        self.client_ws.discard(ws)
        WS_CONNECTIONS.dec()
        
    async def send_to_agent(self, agent_id: str, msg: WSMessage):
        if ws := self.agent_ws.get(agent_id):
            try:
                await ws.send_json(msg.model_dump())
            except Exception as e:
                log.error("ws_send_failed", agent_id=agent_id, error=str(e))
                
    async def broadcast_clients(self, msg: WSMessage):
        dead = set()
        for ws in self.client_ws:
            try:
                await ws.send_json(msg.model_dump())
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.client_ws.discard(ws)
            
    async def broadcast_agents(self, msg: WSMessage, exclude: Optional[str] = None):
        for agent_id, ws in self.agent_ws.items():
            if agent_id != exclude:
                try:
                    await ws.send_json(msg.model_dump())
                except Exception:
                    pass

ws_manager = WSManager()

# ──────────────────────────────────────────────
# Task Queue & Execution
# ──────────────────────────────────────────────
class TaskQueue:
    def __init__(self):
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running: Dict[str, asyncio.Task] = {}
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_tasks)
        
    async def enqueue(self, task: Task):
        await self.queue.put((-task.priority, task.created_at, task))
        TASKS_CREATED.labels(type=task.type.value).inc()
        log.info("task_queued", task_id=task.id, type=task.type.value)
        
    async def dequeue(self) -> Optional[Task]:
        try:
            _, _, task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            return task
        except asyncio.TimeoutError:
            return None
            
    async def execute(self, task: Task):
        async with self.semaphore:
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            TASK_DURATION.observe(0)  # placeholder
            
            try:
                if task.type == TaskType.OPENCODE:
                    result = await self._run_opencode(task)
                elif task.type == TaskType.SHELL:
                    result = await self._run_shell(task)
                elif task.type == TaskType.FILE_READ:
                    result = await self._read_file(task)
                elif task.type == TaskType.FILE_WRITE:
                    result = await self._write_file(task)
                elif task.type == TaskType.GIT:
                    result = await self._run_git(task)
                elif task.type == TaskType.HTTP:
                    result = await self._run_http(task)
                else:
                    result = await self._run_custom(task)
                    
                task.status = TaskStatus.COMPLETED
                task.result = result
                TASKS_COMPLETED.labels(status="success").inc()
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                TASKS_COMPLETED.labels(status="error").inc()
                log.error("task_failed", task_id=task.id, error=str(e))
            finally:
                task.completed_at = time.time()
                duration = task.completed_at - (task.started_at or task.completed_at)
                TASK_DURATION.observe(duration)
                await self._notify_completion(task)
                
    async def _run_opencode(self, task: Task) -> Dict[str, Any]:
        """Execute opencode CLI with task payload"""
        prompt = task.payload.get("prompt", "")
        work_dir = task.payload.get("work_dir", "/workspace")
        model = task.payload.get("model", "gpt-4")
        
        cmd = [
            settings.opencode_bin,
            "run",
            "--model", model,
            "--dir", work_dir,
            prompt
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=task.timeout
        )
        
        return {
            "exit_code": proc.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "command": " ".join(cmd)
        }
        
    async def _run_shell(self, task: Task) -> Dict[str, Any]:
        cmd = task.payload.get("command", "")
        work_dir = task.payload.get("work_dir", "/workspace")
        shell = task.payload.get("shell", "/bin/bash")
        
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
            executable=shell
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=task.timeout
        )
        
        return {
            "exit_code": proc.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "command": cmd
        }
        
    async def _read_file(self, task: Task) -> Dict[str, Any]:
        path = task.payload.get("path", "")
        async with aiofiles.open(path, "r") as f:
            content = await f.read()
        return {"path": path, "content": content, "size": len(content)}
        
    async def _write_file(self, task: Task) -> Dict[str, Any]:
        path = task.payload.get("path", "")
        content = task.payload.get("content", "")
        mode = task.payload.get("mode", "w")
        
        async with aiofiles.open(path, mode) as f:
            await f.write(content)
            
        return {"path": path, "bytes_written": len(content.encode())}
        
    async def _run_git(self, task: Task) -> Dict[str, Any]:
        args = task.payload.get("args", [])
        work_dir = task.payload.get("work_dir", "/workspace")
        
        cmd = ["git"] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=task.timeout)
        
        return {
            "exit_code": proc.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "command": " ".join(cmd)
        }
        
    async def _run_http(self, task: Task) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=task.timeout) as client:
            method = task.payload.get("method", "GET")
            url = task.payload.get("url", "")
            headers = task.payload.get("headers", {})
            data = task.payload.get("data")
            
            resp = await client.request(method, url, headers=headers, json=data)
            return {
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text,
                "url": str(resp.url)
            }
            
    async def _run_custom(self, task: Task) -> Dict[str, Any]:
        # Plugin point for custom task types
        return {"message": f"Custom task {task.type} not implemented"}
        
    async def _notify_completion(self, task: Task):
        msg = WSMessage(type="task.completed", payload=task.model_dump())
        await ws_manager.broadcast_clients(msg)

task_queue = TaskQueue()

# ──────────────────────────────────────────────
# Approval System
# ──────────────────────────────────────────────
class ApprovalManager:
    def __init__(self):
        self.pending: Dict[str, ApprovalRequest] = {}
        self.auto_approve_rules: List[Callable[[ApprovalRequest], bool]] = []
        
    async def request(self, task: Task, approval_type: ApprovalType, title: str, 
                      description: str, details: Dict[str, Any]) -> ApprovalRequest:
        approval = ApprovalRequest(
            task_id=task.id,
            type=approval_type,
            title=title,
            description=description,
            details=details
        )
        self.pending[approval.id] = approval
        task.approval_request_id = approval.id
        task.status = TaskStatus.WAITING_APPROVAL
        
        # Notify clients
        msg = WSMessage(type="approval.requested", payload=approval.model_dump())
        await ws_manager.broadcast_clients(msg)
        
        return approval
        
    async def resolve(self, approval_id: str, approved: bool, resolver: str = "human"):
        if approval_id not in self.pending:
            raise ValueError("Approval not found")
            
        approval = self.pending[approval_id]
        approval.status = "approved" if approved else "rejected"
        approval.resolved_at = time.time()
        approval.resolver = resolver
        
        # Update task
        if task := state.tasks.get(approval.task_id):
            if approved:
                task.status = TaskStatus.APPROVED
                await task_queue.enqueue(task)
            else:
                task.status = TaskStatus.REJECTED
                task.error = "Approval rejected"
                
        # Notify
        msg = WSMessage(type="approval.resolved", payload=approval.model_dump())
        await ws_manager.broadcast_clients(msg)
        
        del self.pending[approval_id]
        
    async def check_auto_approve(self, approval: ApprovalRequest) -> bool:
        for rule in self.auto_approve_rules:
            try:
                if rule(approval):
                    return True
            except Exception:
                pass
        return False

approval_mgr = ApprovalManager()

# ──────────────────────────────────────────────
# Agent Registry
# ──────────────────────────────────────────────
class AgentRegistry:
    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        
    async def register(self, agent_id: str, info: AgentInfo):
        self.agents[agent_id] = info
        state.agents[agent_id] = info
        ACTIVE_AGENTS.inc()
        log.info("agent_registered", agent_id=agent_id, name=info.name)
        
    async def unregister(self, agent_id: str):
        if agent_id in self.agents:
            del self.agents[agent_id]
            state.agents.pop(agent_id, None)
            ACTIVE_AGENTS.dec()
            
    async def heartbeat(self, agent_id: str):
        if agent_id in self.agents:
            self.agents[agent_id].last_heartbeat = time.time()
            
    def get_available(self, capability: Optional[str] = None) -> List[AgentInfo]:
        agents = [a for a in self.agents.values() if a.status == "idle"]
        if capability:
            agents = [a for a in agents if capability in a.capabilities]
        return agents

agent_registry = AgentRegistry()

# ──────────────────────────────────────────────
# Background Workers
# ──────────────────────────────────────────────
async def task_worker():
    """Main task processing loop"""
    while True:
        task = await task_queue.dequeue()
        if task:
            # Find available agent or execute locally
            agents = agent_registry.get_available()
            if agents:
                agent = agents[0]
                task.assigned_agent = agent.id
                agent.status = "busy"
                agent.current_task = task.id
                
                await ws_manager.send_to_agent(agent.id, WSMessage(
                    type="task.assign",
                    payload=task.model_dump()
                ))
            else:
                # Execute locally
                asyncio.create_task(task_queue.execute(task))
        await asyncio.sleep(0.1)

async def heartbeat_monitor():
    """Monitor agent heartbeats"""
    while True:
        now = time.time()
        for agent_id, agent in list(agent_registry.agents.items()):
            if now - agent.last_heartbeat > settings.ws_heartbeat_interval * 2:
                log.warning("agent_timeout", agent_id=agent_id)
                await agent_registry.unregister(agent_id)
                ws_manager.disconnect_agent(agent_id)
        await asyncio.sleep(settings.ws_heartbeat_interval)

# ──────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await state.init_redis()
    asyncio.create_task(task_worker())
    asyncio.create_task(heartbeat_monitor())
    log.info("server_started")
    yield
    # Shutdown
    await state.close_redis()
    log.info("server_stopped")

# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────
app = FastAPI(
    title="Headless Agent Swarm",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# REST API
# ──────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "agents": len(agent_registry.agents),
        "tasks_pending": task_queue.queue.qsize(),
        "tasks_running": len(task_queue.running),
        "approvals_pending": len(approval_mgr.pending)
    }

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")

# Tasks
@app.post("/api/tasks", response_model=Task)
async def create_task(task_data: TaskCreate, background_tasks: BackgroundTasks):
    task = Task(**task_data.model_dump())
    state.tasks[task.id] = task
    
    # Check if needs approval
    if task.requires_approval and task.approval_type:
        await approval_mgr.request(
            task, task.approval_type,
            f"Approval required for {task.type.value}",
            f"Task {task.id} requires human approval",
            {"task": task.model_dump()}
        )
    else:
        background_tasks.add_task(task_queue.enqueue, task)
        
    return task

@app.get("/api/tasks", response_model=List[Task])
async def list_tasks(status: Optional[TaskStatus] = None, limit: int = 100):
    tasks = list(state.tasks.values())
    if status:
        tasks = [t for t in tasks if t.status == status]
    return sorted(tasks, key=lambda t: t.created_at, reverse=True)[:limit]

@app.get("/api/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str):
    if task := state.tasks.get(task_id):
        return task
    raise HTTPException(404, "Task not found")

@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    if task := state.tasks.get(task_id):
        if task.status in [TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING]:
            task.status = TaskStatus.CANCELLED
            return {"status": "cancelled"}
    raise HTTPException(400, "Cannot cancel task")

# Approvals
@app.get("/api/approvals", response_model=List[ApprovalRequest])
async def list_approvals(status: Optional[str] = None):
    approvals = list(approval_mgr.pending.values())
    if status:
        approvals = [a for a in approvals if a.status == status]
    return approvals

@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: str):
    await approval_mgr.resolve(approval_id, True)
    return {"status": "approved"}

@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: str):
    await approval_mgr.resolve(approval_id, False)
    return {"status": "rejected"}

# Agents
@app.get("/api/agents", response_model=List[AgentInfo])
async def list_agents():
    return list(agent_registry.agents.values())

@app.get("/api/agents/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    if agent := agent_registry.agents.get(agent_id):
        return agent
    raise HTTPException(404, "Agent not found")

# Debug / Swarm
@app.post("/api/swarm/spawn")
async def spawn_agent(name: str, capabilities: List[str] = None, count: int = 1):
    """Spawn new agent processes (for debugging)"""
    spawned = []
    for i in range(count):
        agent_id = f"{name}-{uuid.uuid4().hex[:8]}"
        info = AgentInfo(
            id=agent_id,
            name=f"{name}-{i+1}",
            capabilities=capabilities or ["shell", "opencode"],
            metadata={"spawned": True, "parent": "api"}
        )
        await agent_registry.register(agent_id, info)
        spawned.append(info)
    return {"spawned": spawned}

@app.post("/api/swarm/broadcast")
async def broadcast_to_swarm(message: Dict[str, Any]):
    """Send message to all connected agents"""
    msg = WSMessage(type="swarm.broadcast", payload=message)
    await ws_manager.broadcast_agents(msg)
    return {"sent_to": len(ws_manager.agent_ws)}

@app.get("/api/debug/state")
async def debug_state():
    return {
        "tasks": {k: v.model_dump() for k, v in state.tasks.items()},
        "agents": {k: v.model_dump() for k, v in agent_registry.agents.items()},
        "approvals": {k: v.model_dump() for k, v in approval_mgr.pending.items()},
        "ws_agents": list(ws_manager.agent_ws.keys()),
        "ws_clients": len(ws_manager.client_ws),
        "queue_size": task_queue.queue.qsize(),
    }

# ──────────────────────────────────────────────
# WebSocket Endpoints
# ──────────────────────────────────────────────
@app.websocket("/ws/agent/{agent_id}")
async def agent_websocket(ws: WebSocket, agent_id: str):
    await ws_manager.connect_agent(agent_id, ws)
    
    # Register agent
    info = AgentInfo(
        id=agent_id,
        name=agent_id,
        capabilities=["shell", "opencode", "file_read", "file_write"],
        metadata={"connected_via": "ws"}
    )
    await agent_registry.register(agent_id, info)
    
    try:
        while True:
            data = await ws.receive_json()
            msg = WSMessage(**data)
            
            if msg.type == "heartbeat":
                await agent_registry.heartbeat(agent_id)
                await ws.send_json(WSMessage(type="heartbeat_ack", payload={"ts": time.time()}).model_dump())
                
            elif msg.type == "task.result":
                task_id = msg.payload.get("task_id")
                if task := state.tasks.get(task_id):
                    task.status = TaskStatus.COMPLETED if msg.payload.get("success") else TaskStatus.FAILED
                    task.result = msg.payload.get("result")
                    task.error = msg.payload.get("error")
                    task.completed_at = time.time()
                    
                    # Free agent
                    if agent := agent_registry.agents.get(agent_id):
                        agent.status = "idle"
                        agent.current_task = None
                        
                    await ws_manager.broadcast_clients(WSMessage(
                        type="task.completed", payload=task.model_dump()
                    ))
                    
            elif msg.type == "task.log":
                # Forward logs to clients
                await ws_manager.broadcast_clients(WSMessage(
                    type="task.log",
                    payload={"task_id": msg.payload.get("task_id"), "log": msg.payload.get("log")}
                ))
                
            elif msg.type == "approval.response":
                approval_id = msg.payload.get("approval_id")
                approved = msg.payload.get("approved", False)
                await approval_mgr.resolve(approval_id, approved, "agent")
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("agent_ws_error", agent_id=agent_id, error=str(e))
    finally:
        ws_manager.disconnect_agent(agent_id)
        await agent_registry.unregister(agent_id)

@app.websocket("/ws/client")
async def client_websocket(ws: WebSocket):
    await ws_manager.connect_client(ws)
    try:
        # Send initial state
        await ws.send_json(WSMessage(type="init", payload={
            "tasks": [t.model_dump() for t in state.tasks.values()],
            "agents": [a.model_dump() for a in agent_registry.agents.values()],
            "approvals": [a.model_dump() for a in approval_mgr.pending.values()]
        }).model_dump())
        
        while True:
            data = await ws.receive_json()
            # Handle client messages if needed
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect_client(ws)

# ──────────────────────────────────────────────
# Static Files (PWA)
# ──────────────────────────────────────────────
static_dir = Path(settings.static_dir)
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept API/WS paths
        if full_path.startswith(("api/", "ws/", "health", "metrics")):
            raise HTTPException(404)
            
        file_path = static_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(static_dir / "index.html")

# ──────────────────────────────────────────────
# CLI Entry
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level=settings.log_level.lower()
    )
