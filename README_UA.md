# 🔗 WakeLink Server

<div align="center">

[![Protocol](https://img.shields.io/badge/Protocol-v1.0-blue.svg)](https://github.com/wakelink-repos)
[![License](https://img.shields.io/badge/License-NGC%20v1.0-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

**FastAPI хмарний релей-сервер для протоколу WakeLink**

[English](README.md) | Українська | [Русский](README_RU.md)

</div>

---

## 📖 Опис

WakeLink Server — це сліпий релей-сервер, що пересилає зашифровані пакети між клієнтами та ESP пристроями. Він **ніколи не розшифровує** payload — тільки клієнт і пристрій мають спільний ключ.

### Можливості

- 🔐 **Сліпий релей** — не бачить розшифрованих даних
- 🌐 **WebSocket** — з'єднання з пристроями в реальному часі
- 📡 **HTTP API** — REST ендпоінти з long polling
- 🔑 **JWT Auth** — автентифікація користувачів
- 📊 **Dashboard** — веб-інтерфейс керування
- 🐳 **Docker** — контейнеризований деплой

---

## 🚀 Швидкий старт

### Docker (Рекомендовано)

```bash
docker-compose up -d
```

Сервер буде доступний за адресою `http://localhost:9009`

### Ручна установка

```bash
git clone https://github.com/wakelink-repos/server.git
cd server
pip install -r requirements.txt
python main.py
```

---

## 🔧 API Ендпоінти

### REST API

| Ендпоінт | Метод | Опис |
|----------|-------|------|
| `/api/health` | GET | Перевірка стану сервера |
| `/api/stats` | GET | Статистика сервера |
| `/api/push` | POST | Надіслати команду на пристрій |
| `/api/pull` | POST | Отримати відповідь (long polling) |
| `/api/register_device` | POST | Зареєструвати новий пристрій |
| `/api/delete_device` | POST | Видалити пристрій |
| `/api/devices` | GET | Список пристроїв користувача |

### WebSocket

| Ендпоінт | Опис |
|----------|------|
| `/ws/{device_id}` | З'єднання ESP пристрою |
| `/ws/client/{client_id}` | З'єднання CLI клієнта |

#### WebSocket Автентифікація

```json
{"type": "auth", "token": "<api_token>"}
```

---

## ⚙️ Змінні середовища

| Змінна | Опис | За замовчуванням |
|--------|------|------------------|
| `DATABASE_FILE` | Шлях до SQLite бази | `wakelink_cloud.db` |
| `CLOUD_PORT` | Порт сервера | `9009` |
| `API_ENV` | Режим середовища | `development` |

---

## 📁 Структура проекту

```
wakelink-server/
├── main.py              # FastAPI точка входу
├── requirements.txt     # Залежності
├── gunicorn_conf.py     # Конфіг для продакшену
├── core/
│   ├── auth.py          # JWT + валідація API токенів
│   ├── database.py      # SQLite через SQLAlchemy
│   ├── models.py        # User, Device, Message
│   ├── relay.py         # Черга повідомлень (сліпа)
│   └── schemas.py       # Pydantic валідація
├── routes/
│   ├── api.py           # REST API + long polling
│   ├── wss.py           # WebSocket релей
│   ├── auth.py          # Login/register
│   └── admin.py         # Dashboard маршрути
├── templates/           # Jinja2 HTML
└── static/              # CSS/JS
```

---

## 🐳 Docker деплой

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

## 🔗 Пов'язані проекти

- [firmware](https://github.com/wakelink-repos/firmware) — Прошивка ESP8266/ESP32
- [client](https://github.com/wakelink-repos/client) — Python CLI
- [android](https://github.com/wakelink-repos/android) — Android додаток

---

## 📄 Ліцензія

**NGC License v1.0** — Дозволено особисте використання. Комерційне використання вимагає письмового дозволу.

Дивіться [LICENSE](LICENSE) для деталей.

---

<div align="center">

**Зроблено з ❤️ для IoT спільноти**

</div>
