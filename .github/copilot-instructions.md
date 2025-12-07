# 🔗 WakeLink Server — AI Coding Guide

> **Protocol v1.0** • Blind Relay • FastAPI + WebSocket + SQLite

---

## 📐 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         WakeLink Protocol v1.0                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────┐         ┌──────────────┐         ┌──────────────┐   │
│   │    Client    │◄───────►│    Server    │◄───────►│   Firmware   │   │
│   │   (Python)   │  HTTP/  │   (FastAPI)  │   WSS   │  (ESP8266)   │   │
│   │              │   WSS   │              │         │              │   │
│   └──────────────┘         └──────────────┘         └──────────────┘   │
│          │                        │                        │           │
│          │                        │                        │           │
│          └────────────────────────┼────────────────────────┘           │
│                                   │                                     │
│                        Local TCP (port 99)                              │
│                         Direct LAN Access                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### WakeLink Ecosystem

| Component | Repository | Purpose |
|-----------|------------|---------|
| **Relay Server** | `server/` (this) | FastAPI blind relay (never decrypts payload) |
| **Firmware** | [firmware](https://github.com/wakelink-repos/firmware) | ESP8266/ESP32 device running TCP server + WSS client |
| **CLI Client** | [client](https://github.com/wakelink-repos/client) | Python command-line interface for device management |
| **Android** | [android](https://github.com/wakelink-repos/android) | Kotlin mobile app |

### Server Role

**CRITICAL:** The server is a **blind relay**. It:
- ✅ Forwards encrypted packets between clients and devices
- ✅ Manages WebSocket connections
- ✅ Stores device registrations and user accounts
- ❌ **NEVER decrypts** packet payloads
- ❌ **NEVER stores** device tokens (only device_id + api_token)

---

## 🔐 Security Architecture

### What Server Sees

```json
{
  "device_id": "WL35080814",
  "payload": "<opaque hex blob>",
  "signature": "<opaque hex blob>",
  "request_counter": 42,
  "version": "1.0"
}
```

Server validates:
- `device_id` exists and belongs to authenticated user
- Packet structure is valid JSON
- Never inspects `payload` or `signature` content

### Authentication Flow

**User Authentication (JWT):**
```
POST /auth/login
{
  "username": "user",
  "password": "pass"
}
→ {"access_token": "eyJ...", "token_type": "bearer"}
```

**API Token (for devices/clients):**
```
Authorization: Bearer sk-xxxxxxxxxxxx
X-API-Token: sk-xxxxxxxxxxxx  (alternative header)
```

**WebSocket Authentication:**
```json
// First message after connection
{"type": "auth", "token": "sk-xxxxxxxxxxxx"}
// Response
{"type": "welcome", "status": "connected", "device_id": "WL35080814"}
```

---

## 🌐 Server Patterns

### File Structure
```
server/
├── main.py                  # FastAPI app entry point
├── requirements.txt         # Dependencies
├── gunicorn_conf.py         # Production WSGI config
├── core/
│   ├── __init__.py
│   ├── auth.py              # JWT + API token validation
│   ├── cleanup.py           # Background cleanup tasks
│   ├── config.py            # Environment configuration
│   ├── database.py          # SQLite via SQLAlchemy
│   ├── models.py            # User, Device, Message ORM models
│   ├── relay.py             # Message queue (blind forwarding)
│   ├── schemas.py           # Pydantic request/response schemas
│   └── utils.py             # Helper functions
├── routes/
│   ├── admin.py             # Dashboard routes (HTML)
│   ├── api.py               # REST API + long polling
│   ├── auth.py              # Login/register endpoints
│   ├── home.py              # Landing page
│   └── wss.py               # WebSocket relay handlers
├── templates/               # Jinja2 HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── home.html
│   ├── login.html
│   └── register.html
└── static/                  # CSS/JS assets
    ├── main.js
    └── style.css
```

### API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/health` | GET | No | Server health check |
| `/api/stats` | GET | JWT | Server statistics |
| `/api/push` | POST | API | Send command to device queue |
| `/api/pull` | POST | API | Get response (long polling, `?wait=30`) |
| `/api/register_device` | POST | JWT | Register new device |
| `/api/delete_device` | POST | JWT | Delete device |
| `/api/devices` | GET | JWT | List user's devices |

### WebSocket Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `/ws/{device_id}` | API Token | ESP device persistent connection |
| `/ws/client/{client_id}` | API Token | CLI/Android client connection |

### Relay Implementation

```python
# core/relay.py
class MessageRelay:
    """Blind message queue - never inspects payload content."""
    
    def __init__(self):
        self.device_queues: dict[str, asyncio.Queue] = {}
        self.response_queues: dict[str, asyncio.Queue] = {}
        self.connected_devices: dict[str, WebSocket] = {}
    
    async def send_to_device(self, device_id: str, packet: dict) -> None:
        """Forward packet to device via WSS or queue for polling."""
        if device_id in self.connected_devices:
            # Device connected via WebSocket - send immediately
            await self.connected_devices[device_id].send_json(packet)
        else:
            # Device polling - add to queue
            if device_id not in self.device_queues:
                self.device_queues[device_id] = asyncio.Queue()
            await self.device_queues[device_id].put(packet)
    
    async def wait_for_response(self, request_id: str, timeout: int = 30) -> dict:
        """Wait for device response with timeout."""
        queue = self.response_queues.setdefault(request_id, asyncio.Queue())
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return {"status": "error", "error": "TIMEOUT"}
```

### WebSocket Handler

```python
# routes/wss.py
@router.websocket("/ws/{device_id}")
async def device_websocket(websocket: WebSocket, device_id: str):
    await websocket.accept()
    
    # Wait for auth message
    auth_msg = await websocket.receive_json()
    if auth_msg.get("type") != "auth" or not validate_token(auth_msg.get("token")):
        await websocket.close(code=4001, reason="INVALID_TOKEN")
        return
    
    # Register device connection
    relay.connected_devices[device_id] = websocket
    await websocket.send_json({"type": "welcome", "status": "connected"})
    
    try:
        while True:
            # Receive response from device
            data = await websocket.receive_json()
            if "request_id" in data:
                # Forward response to waiting client
                await relay.deliver_response(data["request_id"], data)
    except WebSocketDisconnect:
        del relay.connected_devices[device_id]
```

### Database Models

```python
# core/models.py
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password_hash = Column(String)
    api_token = Column(String, unique=True)  # sk-xxx format
    devices = relationship("Device", back_populates="owner")

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True)
    device_id = Column(String, unique=True)  # WL35080814
    name = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="devices")
    # NOTE: device_token is NOT stored - only client/device know it
```

---

## 🐛 Debugging Guide

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_FILE` | SQLite database path | `wakelink_cloud.db` |
| `CLOUD_PORT` | Server port | `9009` |
| `API_ENV` | Environment mode | `development` |
| `SECRET_KEY` | JWT signing key | (generated) |

### Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Log levels per module
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("wakelink.relay").setLevel(logging.DEBUG)
logging.getLogger("wakelink.wss").setLevel(logging.DEBUG)
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| WSS disconnect | Cloudflare 100s timeout | Set `ws_ping_interval=30` |
| Long poll timeout | Client not receiving | Check queue delivery |
| 401 Unauthorized | Invalid/expired token | Refresh JWT or API token |
| Device not found | Wrong device_id | Check registration |

### Health Check

```bash
curl http://localhost:9009/api/health
# {"status": "ok", "devices_connected": 5, "uptime": 3600}
```

---

## 🐳 Deployment

### Docker (Recommended)

```yaml
# docker-compose.yml
version: '3.8'
services:
  wakelink:
    build: .
    ports:
      - "9009:9009"
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_FILE=/app/data/wakelink.db
      - API_ENV=production
      - SECRET_KEY=${SECRET_KEY}
    restart: unless-stopped
```

### Gunicorn (Production)

```python
# gunicorn_conf.py
bind = "0.0.0.0:9009"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 65
```

### Cloudflare Proxy

When behind Cloudflare:
- Set WebSocket ping interval to 15-30s (100s timeout)
- Use `wss://` protocol
- Enable WebSocket support in Cloudflare dashboard

---

## ⚠️ Version & Licensing

### Version Lock
Protocol, firmware, client, server, and Android are **all locked to v1.0**.

Any breaking change requires simultaneous updates across all components.

### Breaking Changes Include
- API endpoint changes
- WebSocket message format changes
- Authentication flow changes
- Database schema changes

### License
**NGC License v1.0** — Personal use only.
- ❌ Do not suggest GPL/commercial dependencies
- ✅ Keep existing license headers intact
- 📝 Commercial use requires written permission

---

## 🔗 Related Repositories

| Repository | Description |
|------------|-------------|
| [firmware](https://github.com/wakelink-repos/firmware) | ESP8266/ESP32 Firmware |
| [client](https://github.com/wakelink-repos/client) | Python CLI |
| [android](https://github.com/wakelink-repos/android) | Android App |
