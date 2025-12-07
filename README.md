# 🔗 WakeLink Server

<div align="center">

[![Protocol](https://img.shields.io/badge/Protocol-v1.0-blue.svg)](https://github.com/wakelink-repos)
[![License](https://img.shields.io/badge/License-NGC%20v1.0-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

**FastAPI Cloud Relay Server for WakeLink Protocol**

English | [Українська](README_UA.md) | [Русский](README_RU.md)

</div>

---

## 📖 Description

WakeLink Server is a blind relay server that forwards encrypted packets between clients and ESP devices. It **never decrypts** the payload — only the client and device share the encryption key.

### Features

- 🔐 **Blind relay** — never sees decrypted data
- 🌐 **WebSocket** — real-time device connections
- 📡 **HTTP API** — REST endpoints with long polling
- 🔑 **JWT Auth** — user authentication
- 📊 **Dashboard** — web management interface
- 🐳 **Docker** — containerized deployment

---

## 🚀 Quick Start

### Docker (Recommended)

```bash
docker-compose up -d
```

Server will be available at `http://localhost:9009`

### Manual Installation

```bash
git clone https://github.com/wakelink-repos/server.git
cd server
pip install -r requirements.txt
python main.py
```

---

## 🔧 API Endpoints

### REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Server health check |
| `/api/stats` | GET | Server statistics |
| `/api/push` | POST | Send command to device |
| `/api/pull` | POST | Get response (long polling) |
| `/api/register_device` | POST | Register new device |
| `/api/delete_device` | POST | Delete device |
| `/api/devices` | GET | List user's devices |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `/ws/{device_id}` | ESP device connection |
| `/ws/client/{client_id}` | CLI client connection |

#### WebSocket Authentication

```json
{"type": "auth", "token": "<api_token>"}
```

---

## ⚙️ Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_FILE` | SQLite database path | `wakelink_cloud.db` |
| `CLOUD_PORT` | Server port | `9009` |
| `API_ENV` | Environment mode | `development` |

---

## 📁 Project Structure

```
wakelink-server/
├── main.py              # FastAPI entry point
├── requirements.txt     # Dependencies
├── gunicorn_conf.py     # Production config
├── core/
│   ├── auth.py          # JWT + API token validation
│   ├── database.py      # SQLite via SQLAlchemy
│   ├── models.py        # User, Device, Message
│   ├── relay.py         # Message queue (blind)
│   └── schemas.py       # Pydantic validation
├── routes/
│   ├── api.py           # REST API + long polling
│   ├── wss.py           # WebSocket relay
│   ├── auth.py          # Login/register
│   └── admin.py         # Dashboard routes
├── templates/           # Jinja2 HTML
└── static/              # CSS/JS
```

---

## 🐳 Docker Deployment

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
```

---

## 🔗 Related Projects

- [firmware](https://github.com/wakelink-repos/firmware) — ESP8266/ESP32 Firmware
- [client](https://github.com/wakelink-repos/client) — Python CLI
- [android](https://github.com/wakelink-repos/android) — Android App

---

## 📄 License

**NGC License v1.0** — Personal use allowed. Commercial use requires written permission.

See [LICENSE](LICENSE) for details.

---

<div align="center">

**Made with ❤️ for the IoT community**

</div>
