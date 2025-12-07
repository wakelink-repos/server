# 🔗 WakeLink Server

<div align="center">

[![Protocol](https://img.shields.io/badge/Protocol-v1.0-blue.svg)](https://github.com/wakelink-repos)
[![License](https://img.shields.io/badge/License-NGC%20v1.0-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

**FastAPI облачный релей-сервер для протокола WakeLink**

[English](README.md) | [Українська](README_UA.md) | Русский

</div>

---

## 📖 Описание

WakeLink Server — это слепой релей-сервер, пересылающий зашифрованные пакеты между клиентами и ESP устройствами. Он **никогда не расшифровывает** payload — только клиент и устройство имеют общий ключ.

### Возможности

- 🔐 **Слепой релей** — не видит расшифрованных данных
- 🌐 **WebSocket** — соединения с устройствами в реальном времени
- 📡 **HTTP API** — REST эндпоинты с long polling
- 🔑 **JWT Auth** — аутентификация пользователей
- 📊 **Dashboard** — веб-интерфейс управления
- 🐳 **Docker** — контейнеризированный деплой

---

## 🚀 Быстрый старт

### Docker (Рекомендуется)

```bash
docker-compose up -d
```

Сервер будет доступен по адресу `http://localhost:9009`

### Ручная установка

```bash
git clone https://github.com/wakelink-repos/server.git
cd server
pip install -r requirements.txt
python main.py
```

---

## 🔧 API Эндпоинты

### REST API

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/api/health` | GET | Проверка состояния сервера |
| `/api/stats` | GET | Статистика сервера |
| `/api/push` | POST | Отправить команду на устройство |
| `/api/pull` | POST | Получить ответ (long polling) |
| `/api/register_device` | POST | Зарегистрировать новое устройство |
| `/api/delete_device` | POST | Удалить устройство |
| `/api/devices` | GET | Список устройств пользователя |

### WebSocket

| Эндпоинт | Описание |
|----------|----------|
| `/ws/{device_id}` | Соединение ESP устройства |
| `/ws/client/{client_id}` | Соединение CLI клиента |

#### WebSocket Аутентификация

```json
{"type": "auth", "token": "<api_token>"}
```

---

## ⚙️ Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_FILE` | Путь к SQLite базе | `wakelink_cloud.db` |
| `CLOUD_PORT` | Порт сервера | `9009` |
| `API_ENV` | Режим окружения | `development` |

---

## 📁 Структура проекта

```
wakelink-server/
├── main.py              # FastAPI точка входа
├── requirements.txt     # Зависимости
├── gunicorn_conf.py     # Конфиг для продакшена
├── core/
│   ├── auth.py          # JWT + валидация API токенов
│   ├── database.py      # SQLite через SQLAlchemy
│   ├── models.py        # User, Device, Message
│   ├── relay.py         # Очередь сообщений (слепая)
│   └── schemas.py       # Pydantic валидация
├── routes/
│   ├── api.py           # REST API + long polling
│   ├── wss.py           # WebSocket релей
│   ├── auth.py          # Login/register
│   └── admin.py         # Dashboard маршруты
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

## 🔗 Связанные проекты

- [firmware](https://github.com/wakelink-repos/firmware) — Прошивка ESP8266/ESP32
- [client](https://github.com/wakelink-repos/client) — Python CLI
- [android](https://github.com/wakelink-repos/android) — Android приложение

---

## 📄 Лицензия

**NGC License v1.0** — Разрешено личное использование. Коммерческое использование требует письменного разрешения.

Смотрите [LICENSE](LICENSE) для деталей.

---

<div align="center">

**Сделано с ❤️ для IoT сообщества**

</div>
