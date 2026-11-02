# DEFENSE — سوال و جواب‌های احتمالی استاد
The agent appends 3 Q&A per task during /explain, grouped by phase.

## Phase 1

### P1-01 Repo and environment
1. **سوال: چرا پایگاه داده PostgreSQL را با Docker Compose اجرا کردی و چگونه تنظیمات اتصال جنگو را به آن متصل کردی؟**
   - **پاسخ برای استاد:** طبق الزامات پروژه و تصمیم D-03، تمام مراحل روی PostgreSQL اجرا می‌شوند. برای راه‌اندازی سریع، ایزوله و یکدست محیط توسعه در سیستم‌های مختلف، از `docker-compose.yml` برای سرویس PostgreSQL 16 استفاده کردیم. جنگو با درایور مدرن `psycopg` (نسخه ۳) و متغیرهای تعریف‌شده در `backend/config/settings.py` به پورت ۵۴۳۲ متصل می‌شود.
2. **سوال: متغیرهای محیطی (Environment Variables) چگونه مدیریت شده‌اند و چرا فایل `.env` در Git نیست؟**
   - **پاسخ برای استاد:** بر اساس متدولوژی استاندارد ۱۲-فاکتور (Twelve-Factor App)، اطلاعات حساس پروژه مانند `SECRET_KEY` و کلمات عبور پایگاه داده نباید در مخزن عمومی قرار گیرند. ما از پکیج `python-dotenv` استفاده کردیم. فایل `.env` در `.gitignore` تعریف شد تا هرگز کامیت نشود، و فایل نمونه `backend/.env.example` برای راهنمای راه‌اندازی در مخزن قرار داده شد.
3. **سوال: تنظیمات بومی‌سازی (فارسی/تهران) و فایل‌های Static و Media چگونه پیکربندی شده‌اند؟**
   - **پاسخ برای استاد:** در `settings.py`، متغیر `LANGUAGE_CODE = 'fa'` و `TIME_ZONE = 'Asia/Tehran'` تنظیم شد تا زبان پیش‌فرض پنل و خطاها فارسی و ساعت‌ها مطابق زمان ایران باشد. همچنین `STATIC_URL`, `STATICFILES_DIRS`, `STATIC_ROOT` برای فایل‌های استاتیک قالب‌ها و `MEDIA_URL`, `MEDIA_ROOT` برای تصاویر ابزارها و کالاهای امانتی در سطح مسیر پروژه ست شده‌اند.

## Phase 2
## Phase 3
## Phase 4

## General questions to prepare (answer in your own words)
- Why PostgreSQL and how did you configure it? Where is the backup?
- Why a custom User model and why before the first migrate?
- What is a ForeignKey / related_name / on_delete PROTECT vs CASCADE? Where did you use each?
- How do you prevent double booking? (overlap query + constraint)
- What is a Manager / QuerySet and why did you define yours?
- How do session and cookie differ? Where do you use each?
- What does the logging middleware record?
- How does email verification work (token, expiry)?
- How are templates organised (inheritance, includes)?
