# Amanat-yab (امانت یاب) — project + agent kit

## Install the kit (once, before P1-01)
1. Create an empty GitHub repo `amanatyab`, clone it locally.
2. Copy ALL contents of this kit into the repo root (keep the hidden `.agent/` folder).
3. `git add . && git commit -m "chore: add agent kit and project docs" && git push`
   (this is commit #1; it explains the project to the instructor too).
4. Open the repo folder in Antigravity. Workflows are the slash commands in `.agent/workflows/`; rules load from `.agent/rules/` and `AGENTS.md`.
5. In Antigravity settings set terminal command policy to "request review" (or equivalent) so `git push` always asks you.
6. Fill `repo_url` and deadlines in `docs/STATE.md`; email the repo link to the instructor.
7. New agent chat → type `/resume`, then `/start-task P1-01`.

## The loop for every task
`/start-task <ID>` → you approve the plan → `/implement` → `/verify` → `/commit` → `/explain` (answer the 3 questions) → `/finish-task` (you approve the push).
End of each phase: `/phase-review`.

## Folder map
- `AGENTS.md`, `.agent/` — agent instructions (rules + workflows)
- `docs/` — STATE, DOMAIN, PROCESSES, DECISIONS, COMMIT-LOG, DEFENSE, REPORT
- `tasks/phase-1..4.md` — every task with files, acceptance, commits
- `backend/`, `frontend/`, `db_backup/` — created by the agent during the tasks

## Quickstart (اجرای سریع پروژه از صفر)

### ۱. راه‌اندازی پایگاه داده (PostgreSQL via Docker)
```bash
docker compose up -d
```

### ۲. آماده‌سازی پایتون، متغیرهای محیطی و اعمال مایگریشن‌ها
```bash
# ایجاد و فعال‌سازی محیط مجازی پایتون
python3 -m venv .venv
source .venv/bin/activate  # در ویندوز: .venv\Scripts\activate

# نصب وابستگی‌ها
cd backend
pip install -r requirements.txt

# تنظیم فایل متغیرهای محیطی
cp .env.example .env

# اجرای مایگریشن‌های دیتابیس
python manage.py migrate
```

### ۳. بارگذاری داده‌های نمایشی (Seed Demo Data) یا بازگردانی پشتیبان
```bash
# روش اول: اجرای سیدر خودکار (شامل کاربران، کالاها، اجاره‌ها، نظرات و چت‌ها)
python manage.py seed_demo

# روش دوم: بازگردانی مستقیم فایل پشتیبان فاز ۴ با داکر
docker compose exec -T db psql -U amanatyab -d amanatyab < ../db_backup/phase-4.sql
```
کلیه داده‌های تستی شامل ۹ کاربر، ۶ دسته‌بندی، ۲۵ کالا با موقعیت مکانی، ۱۱ اجاره در تمامی وضعیت‌ها، پرداخت‌ها، نظرات، چت‌ها و اختلافات با رمز عبور **`demo1234`** آماده استفاده خواهند بود (حساب مدیر: `admin` / `demo1234` و کاربران فعال: `sara`, `reza`, `ali`).

### ۴. کامپایل فرانت‌اند (React Islands & Tailwind CSS)
فایل‌های بیلد شده از قبل در مسیر `backend/static/dist/` کامیت شده‌اند و برای اجرای عادی نیازی به بیلد مجدد نیست. در صورت تمایل به کامپایل مجدد یا اعمال تغییر در کدهای ری‌اکت:
```bash
cd ../frontend
npm install
npm run build
```

### ۵. اجرای سرور توسعه
```bash
cd ../backend
python manage.py runserver
```
سامانه در آدرس `http://127.0.0.1:8000` در دسترس است.

---

## 🎬 راهنمای ارائه دمو ۱۰ دقیقه‌ای به استاد
سناریوی گام‌به‌گام و زمان‌بندی‌شده‌ی ارائه حضوری سامane همراه با نقش‌ها، آدرس‌های URL، سناریوهای تستی و پاسخ به سوالات فنی استاد در فایل مستندات زیر تدوین شده است:
👉 **[docs/DEMO.md](docs/DEMO.md)**

همچنین مجموعه کامل سوالات و پاسخ‌های احتمالی استاد برای تمام فازها و تسک‌ها در فایل زیر گردآوری شده است:
👉 **[docs/DEFENSE.md](docs/DEFENSE.md)**

---

## Scheduling Background Commands

### Rental Ending Reminder (`send_rental_reminders`)
The platform includes an automated reminder command to notify renters via email and SMS before their rental period expires:

```bash
# Run once with default hours (from RENTAL_REMINDER_HOURS in settings, default: 3):
python manage.py send_rental_reminders

# Run once checking up to 5 hours ahead:
python manage.py send_rental_reminders --hours 5

# Run continuously as a background daemon (polls every 60 seconds):
python manage.py send_rental_reminders --loop --interval 60
```

#### Linux / macOS (cron)
Add an entry to crontab (`crontab -e`) to run periodically (e.g. every 15 minutes):
```cron
*/15 * * * * cd /path/to/project/backend && /path/to/project/.venv/bin/python manage.py send_rental_reminders >> /path/to/project/logs/reminders.log 2>&1
```

#### Windows (Task Scheduler)
Create a scheduled task via Command Prompt or PowerShell:
```cmd
schtasks /create /tn "AmanatyabReminder" /tr "C:\path\to\project\.venv\Scripts\python.exe C:\path\to\project\backend\manage.py send_rental_reminders" /sc minute /mo 15
```
Or run as a persistent background service using the `--loop` flag:
```cmd
C:\path\to\project\.venv\Scripts\python.exe C:\path\to\project\backend\manage.py send_rental_reminders --loop --interval 60
```

### Session Cleanup (`clearsessions`)
Since Django uses database-backed sessions (`django.contrib.sessions.backends.db`), expired session records accumulate in the database over time. Run `clearsessions` periodically to clean them up:

```bash
python manage.py clearsessions
```

#### Scheduled Cleanup (cron / Task Scheduler)
- **Linux / macOS (cron — daily at 03:00)**:
  ```cron
  0 3 * * * cd /path/to/project/backend && /path/to/project/.venv/bin/python manage.py clearsessions >> /path/to/project/logs/clearsessions.log 2>&1
  ```
- **Windows (Task Scheduler — daily at 03:00)**:
  ```cmd
  schtasks /create /tn "AmanatyabClearSessions" /tr "C:\path\to\project\.venv\Scripts\python.exe C:\path\to\project\backend\manage.py clearsessions" /sc daily /st 03:00
  ```

## Running Automated Tests (اجرای تست‌های خودکار)

The test suite covers models, constraints, pricing, state machine transitions, form validation, permission checks, dispute handling, cookies, notifications, React JSON endpoints, and scheduled commands across all applications (237 tests).

```bash
# Activate your virtual environment and navigate to the backend directory:
cd backend

# Run the complete test suite:
python manage.py test

# Run tests with increased verbosity:
python manage.py test -v 2

# Run tests for a specific application:
python manage.py test accounts
python manage.py test catalog
python manage.py test rentals
python manage.py test reviews
python manage.py test chat
python manage.py test core

# Run a specific test module or test case:
python manage.py test rentals.tests.test_services
python manage.py test core.tests.test_cookies
```

