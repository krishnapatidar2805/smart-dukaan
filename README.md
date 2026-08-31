# Smart Dukaan — Retail Billing, Inventory & Udhaar Manager

Full-stack web app for small shopkeepers built with **Django, MySQL, HTML, CSS, JavaScript** — plus an AI business assistant and WhatsApp bill/reminder integration.

Tested end-to-end and confirmed working: signup → login → add product → create bill (auto GST/discount calculation, auto stock deduction) → PDF bill → AI assistant → udhaar tracking.

---

## Features

- **Auth** — Shop owner signup, staff accounts with limited access
- **Inventory** — Add/edit/delete products, low-stock alerts, search & filter
- **Billing** — Live cart with JS-calculated totals, GST %, discount, PDF bill download
- **Udhaar (Credit)** — Track what each customer owes, record payments, balance history
- **Dashboard** — 7-day sales chart (Chart.js), low stock list, best sellers, recent bills
- **AI Assistant** — Chat-based Q&A about your shop's sales/stock/udhaar. Works out of the box with a rule-based fallback; add an `ANTHROPIC_API_KEY` for full AI-powered answers
- **WhatsApp Integration** — Send bills and udhaar reminders via Twilio's WhatsApp API (optional; app works fully without it)
- **Dark / Light mode** — Toggle in the top bar, saved across visits

---

## 1. Setup

### Prerequisites
- Python 3.10+
- MySQL Server installed and running (or skip this and use SQLite — see step 3)

### Install dependencies

```bash
cd smart_dukaan
python -m venv venv

# Activate virtual environment
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

## 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your MySQL details:

```
DB_NAME=smart_dukaan
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306
```

Create the database in MySQL first:

```sql
CREATE DATABASE smart_dukaan CHARACTER SET utf8mb4;
```

### Don't have MySQL installed yet? Test with SQLite instead

In `.env`, set:
```
USE_SQLITE=True
```
This skips MySQL entirely and creates a local `db.sqlite3` file — good for quickly trying the app. Switch back to `USE_SQLITE=False` once MySQL is ready (your data won't carry over between the two).

## 3. Run the app

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin access
python manage.py runserver
```

Open **http://127.0.0.1:8000/** in your browser. You'll land on the signup page — create your shop account and you're in.

---

## 4. Optional: Enable the AI Assistant fully

Without any setup, the AI Assistant already answers common questions (low stock, best seller, today's sales, udhaar due) using your real data.

To make it answer open-ended questions with full AI reasoning:

1. Get an API key from https://console.anthropic.com
2. Add it to `.env`:
   ```
   ANTHROPIC_API_KEY=your-key-here
   ```
3. Restart the server.

## 5. Optional: Enable WhatsApp bills & reminders

1. Create a free account at https://www.twilio.com
2. Go to Messaging → Try it out → Send a WhatsApp message, and activate the Sandbox
3. Copy your Account SID, Auth Token, and Sandbox number into `.env`:
   ```
   TWILIO_ACCOUNT_SID=xxxx
   TWILIO_AUTH_TOKEN=xxxx
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   ```
4. Whenever you enter a customer's phone number on the billing page, the bill will be sent to their WhatsApp automatically.
5. To send udhaar reminders (run manually, or schedule daily with cron/Task Scheduler):
   ```bash
   python manage.py send_udhaar_reminders
   ```

The app works completely fine without Twilio — this step is optional.

---

## Project Structure

```
smart_dukaan/
├── accounts/       # signup, login, staff management
├── inventory/       # product CRUD, stock tracking
├── billing/          # cart, bill creation, PDF, WhatsApp send
├── udhaar/            # customer credit tracking
├── dashboard/          # charts, AI assistant, home page
├── templates/            # all HTML templates
├── static/css/style.css   # dark/light theme, all styling
├── static/js/               # billing cart logic, theme toggle, AI chat
└── requirements.txt
```

## Database Schema (MySQL tables Django creates)

`accounts_shop`, `accounts_profile`, `inventory_product`, `billing_bill`, `billing_billitem`, `udhaar_customer`, `udhaar_udhaartransaction` — all linked by foreign keys, all managed through Django's ORM (no manual SQL needed, `migrate` creates everything).

## Resume bullet points (once you've explored the code)

- Built a full-stack retail management system (Django, MySQL, JS) handling inventory, billing, and customer credit tracking
- Implemented a live billing cart with client-side calculation and server-side validation, with automatic stock deduction on sale
- Integrated an AI assistant (Anthropic API) that answers business questions using live shop data, with a rule-based offline fallback
- Integrated Twilio's WhatsApp API to automatically deliver bills and payment reminders to customers
- Designed a themeable UI (dark/light mode) using CSS custom properties across 15+ templates

## Troubleshooting

- **`ModuleNotFoundError: No module named 'pymysql'`** → run `pip install -r requirements.txt` again inside your activated venv.
- **MySQL connection refused** → make sure MySQL server is running (`mysql.server start` on Mac, `sudo service mysql start` on Linux, or check Services on Windows).
- **PDF download shows plain HTML instead of a PDF** → `xhtml2pdf` didn't install correctly; run `pip install xhtml2pdf` again.
- **AI assistant gives only basic answers** → that's the offline fallback; add `ANTHROPIC_API_KEY` in `.env` for full AI answers.
