# GojoShop.et Chatbot

A Flask shopping assistant for GojoShop.et. It supports product search, cart actions, order tracking, FAQ-style help, human-support handoff, and an optional Telegram bot.

## Features

- Web chat UI at `/`
- Chat API at `/api/chat`
- Product search from the `products` MySQL table
- Order lookup from `orders` and `order_items`
- In-memory cart per chat session
- Human support request logging
- Optional Telegram bot integration

## Local Setup

1. Create and activate a virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Create your environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Start MySQL in XAMPP, then import the sample order tables:

   ```powershell
   mysql -u root -p < setup_database.sql
   ```

5. Import your product catalog if needed:

   ```powershell
   mysql -u root -p gojoshop < products.sql
   ```

6. Run the app:

   ```powershell
   python app.py
   ```

Open `http://localhost:5000`.

## API Quick Test

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:5000/api/chat `
  -ContentType 'application/json' `
  -Body '{"user_id":"demo","message":"show me leather bags"}'
```

Useful endpoints:

- `GET /api/health`
- `POST /api/chat`
- `POST /api/session/reset`
- `GET /api/order/<order_id>`
- `GET /api/cart/<user_id>`
- `POST /api/cart/add`
- `GET /api/support/requests`

## Tests

```powershell
python -m pytest -q
```

The core chatbot tests use a fake database, so they do not require MySQL.

## Docker

```powershell
docker compose up --build
```

For Dockerized MySQL, update `DB_HOST` in the environment to point at your database service. The included compose file currently starts the Flask app and Redis.

## Telegram Bot

Set `TELEGRAM_BOT_TOKEN` in `.env`, then run:

```powershell
python telegram_bot.py
```
