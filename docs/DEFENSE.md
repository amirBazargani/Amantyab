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

### P1-02 Create apps + custom user setting
1. **سوال: چرا مدل کاربر سفارشی (`AUTH_USER_MODEL`) را دقیقاً در این مرحله و قبل از اجرای هرگونه مایگریشن تنظیم کردی؟**
   - **پاسخ برای استاد:** مستندات رسمی جنگو اکیداً توصیه می‌کنند حتی اگر مدل پیش‌فرض کاربر در ابتدا کافی به نظر برسد، از همان ابتدای پروژه یک مدل سفارشی تعریف و با `AUTH_USER_MODEL` ست شود. اگر اولین دستور `migrate` با مدل پیش‌فرض جنگو (`auth.User`) اجرا شود، کلیدهای خارجی و جداول سیستمی جنگو به آن جدول گره می‌خورند و تغییر آن در مراحل بعد مستلزم دستکاری دستی و پیچیده دیتابیس و تاریخچه مایگریشن‌ها خواهد بود. به همین دلیل دیتابیس را ریست کرده و این تنظیم را قبل از اولین مایگریشن ست کردیم.
2. **سوال: فلسفه تفکیک پروژه به ۶ اپلیکیشن (`accounts`, `catalog`, `rentals`, `reviews`, `chat`, `core`) چیست؟**
   - **پاسخ برای استاد:** طبق اصل تفکیک دغدغه‌ها (Separation of Concerns) و معماری ماژولار جنگو، هر حوزه منطقی کسب‌وکار درون یک اپلیکیشن مستقل قرار می‌گیرد: `accounts` برای احراز هویت و پروفایل، `catalog` برای دسته‌بندی و کالاهای امانتی، `rentals` برای فرآیند اجاره و وضعیت‌ها و پرداخت‌ها، `reviews` برای سیستم امتیازدهی و بازخورد دوطرفه، `chat` برای پیام‌رسانی بین موجر و مستأجر، و `core` برای مؤلفه‌های عمومی مانند میدل‌ورهای لاگین و قالب‌های مشترک.
3. **سوال: چرا کلاس `User` در این تسک به شکل اولیه از `AbstractUser` ارث‌بری کرد و فیلدهای اضافی در تسک بعدی اضافه می‌شوند؟**
   - **پاسخ برای استاد:** با تنظیم `AUTH_USER_MODEL = "accounts.User"`، سیستم اعتبارسنجی جنگو (`manage.py check`) بررسی می‌کند که مدل ارجاع داده شده حتماً در اپلیکیشن وجود داشته باشد و شرایط کاربری را دارا باشد. ارث‌بری از `AbstractUser` تمامی قابلیت‌های پیش‌فرض ورود، نام کاربری و دسترسی‌های ادمین جنگو را حفظ می‌کند و به ما اجازه می‌دهد فیلدهای اختصاصی دامنه پروژه (مانند تلفن، محله، شهر و بیوگرافی) را در تسک P1-04 بدون ایجاد تعارض پیاده‌سازی کنیم.

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
