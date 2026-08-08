# GojoShop.et Chatbot

A Flask shopping assistant for GojoShop.et. It supports product search, cart actions, order tracking, in-chat checkout, promotions, FAQ-style help, human-support handoff, an optional Telegram bot, and a floating chat-bubble UI with unread-message notifications.

## Features

- Web chat UI at `/` with floating launcher bubble, unread count, and notification sound
- Bilingual UI (English / Amharic) with live translation switching
- Product search from the `products` MySQL table
- In-chat checkout (name, phone, address, payment method → creates `orders` / `order_details` rows)
- Order lookup from `orders` and `order_details`
- Promotions with admin CRUD API
- Human support request logging + admin dashboard at `/admin/support`
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

   The app connects to the `gojoshopchat` database (the live GojoShop e-commerce DB).

4. Start MySQL in XAMPP, then create the tables (safe to run against a fresh server):

   ```powershell
   mysql -u root < setup_database.sql
   ```

   This mirrors the live `gojoshopchat` schema: `users`, `user_sessions`, `products`, `carts`, `orders`, `order_details`, `support_requests`. If you already have the live DB, skip this step.

5. Import your product catalog if needed:

   ```powershell
   mysql -u root -p gojoshopchat < products.sql
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
- `GET /api/translations/<lang>` (`en`, `am`)
- `POST /api/session/reset`
- `GET /api/order/<order_id>`
- `GET /api/cart/<user_id>` · `GET /api/cart/details/<user_id>` · `POST /api/cart/add` · `POST /api/cart/clear`
- `POST /api/checkout` (programmatic checkout fallback)
- `GET /api/products` · `GET /api/faq`
- `GET /api/promotions` · `POST /api/promotions` · `PATCH /api/promotions/<id>` · `DELETE /api/promotions/<id>`
- `GET /api/promotions/products` · `GET /api/promotions/featured`
- `GET /api/support/requests` · `POST /api/support/request` · `PATCH /api/support/requests/<id>`
- `GET/POST /api/support/requests/<id>/messages` · `GET /api/support/requests/active/<user_id>`

## Tests

```powershell
python -m pytest -q
```

The core chatbot and checkout tests use a fake database, so they do not require MySQL.

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

The bot shares the same `DatabaseManager` as the web app, so carts, sessions, and
orders persist to MySQL. It renders in-chat `[CART]` and `[CHECKOUT]` cards as
readable plain text and strips the card markers/`**bold**` syntax meant for the
web renderer. Commands: `/start`, `/help`, `/cart`, `/lang en|am`.

## Project Layout

- `app.py` — Flask app (web UI + REST API)
- `database.py` — MySQL access (products, sessions, cart, orders, support)
- `chatbot/` — chatbot core, intents, session model, services (product, FAQ, promotion, translation, personality, conversation)
- `telegram_bot.py` — optional Telegram interface
- `templates/` — `support_admin.html` (support dashboard)
- `index.html` — chat UI (single canonical page, served at `/`)
- `static/` — CSS and JS for the chat UI
- `setup_database.sql` — creates the `gojoshopchat` schema
