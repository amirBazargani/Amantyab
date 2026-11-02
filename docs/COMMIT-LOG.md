# COMMIT LOG (توضیح فارسی هر کامیت برای دفاع از پروژه)

### 35427f1 — chore: add agent kit and project docs
- تسک: Setup
- چه چیزی تغییر کرد: افزودن ساختار مستندات، راهنماها، تعاریف فازها و تسک‌های پروژه امانت‌یاب.
- چرا لازم بود: ایجاد نظم مهندسی نرم‌افزار، تعیین دامنه و متدولوژی اجرای کار.
- فایل‌های مهم: `AGENTS.md`, `README.md`, `docs/*`, `tasks/*`
- مفهوم جنگو/پایتون که استفاده شد: مستندسازی معماری سیستم و فرآیند‌های نرم‌افزاری.
- اگر استاد بپرسد: هدف این فایل‌ها، تعریف نقشه راه پروژه و ساختار فازهای چهارگانه مطابق دستورالعمل پروژه پایانی است.

---

### adfda1c — chore: add docker-compose, env example and gitignore
- تسک: P1-01
- چه چیزی تغییر کرد: اضافه شدن فایل `.gitignore`، سرویس PostgreSQL 16 در `docker-compose.yml` و الگوی متغیرهای محیطی در `backend/.env.example`.
- چرا لازم بود: رعایت استانداردهای امنیتی (عدم کامیت اطلاعات حساس)، اجرای کانتینری و یکپارچه PostgreSQL و سهولت راه‌اندازی برای سایر توسعه‌دهندگان.
- فایل‌های مهم: `.gitignore`, `docker-compose.yml`, `backend/.env.example`
- مفهوم جنگو/پایتون که استفاده شد: اصل 12-Factor App برای جداسازی تنظیمات محیطی از کد منبع و کانتینرسازی با Docker Compose.
- اگر استاد بپرسد: چرا `.env` در گیت نیست؟ اطلاعات اتصال به دیتابیس و SECRET_KEY امنیتی هستند و نباید وارد مخزن عمومی شوند.

---

### b3494e1 — chore: initialize Django project with PostgreSQL settings
- تسک: P1-01
- چه چیزی تغییر کرد: ساختار اولیه پروژه جنگو (پروژه `config`)، تنظیم اتصال به دیتابیس PostgreSQL از طریق `psycopg` و `python-dotenv`، پیکربندی زبان فارسی، زمان محلی تهران و تنظیمات فایل‌های استاتیک و مدیا.
- چرا لازم بود: هسته اصلی بک‌اند پروژه برای فازهای بعدی آماده شد.
- فایل‌های مهم: `backend/requirements.txt`, `backend/config/settings.py`, `backend/manage.py`
- مفهوم جنگو/پایتون که استفاده شد: تنظیمات `DATABASES` با انجین `django.db.backends.postgresql`، متغیرهای `LANGUAGE_CODE = 'fa'` و `TIME_ZONE = 'Asia/Tehran'`، و بارگذاری متغیرها با `python-dotenv`.
- اگر استاد بپرسد: چرا از PostgreSQL استفاده شد؟ طبق الزامات پروژه و تصمیم D-03، تمام فازها صرفاً روی دیتابیس رابطه‌ای PostgreSQL اجرا می‌شوند.

---

### 7b1031f — chore: create accounts, catalog, rentals, reviews, chat, core apps
- تسک: P1-02
- چه چیزی تغییر کرد: ساخت ۶ اپلیکیشن جنگو (`accounts`, `catalog`, `rentals`, `reviews`, `chat`, `core`)، افزودن آن‌ها به `INSTALLED_APPS`، تعریف اولیه مدل سفارشی کاربر (`User`) با ارث‌بری از `AbstractUser` در اپلیکیشن `accounts`، تنظیم `AUTH_USER_MODEL = "accounts.User"` در `settings.py` و ریست تمیز دیتابیس PostgreSQL جهت جلوگیری از ایجاد یا تداخل جداول پیش‌فرض `auth_user`.
- چرا لازم بود: طبق مستندات و بهترین شیوه‌های جنگو (Django Best Practices)، مدل کاربر سفارشی حتماً باید قبل از اولین مایگریشن در پروژه تنظیم شود. همچنین معماری ماژولار نیازمند تفکیک حوزه‌های کاری (حساب کاربری، کاتالوگ کالاها، اجاره و پرداخت، نظرات، چت و هسته مشترک) به اپلیکیشن‌های مستقل است.
- فایل‌های مهم: `backend/accounts/*`, `backend/catalog/*`, `backend/rentals/*`, `backend/reviews/*`, `backend/chat/*`, `backend/core/*`, `backend/config/settings.py`
- مفهوم جنگو/پایتون که استفاده شد: ساختار ماژولار جنگو با `startapp`، متغیر `INSTALLED_APPS`، مدل سفارشی کاربر با `AUTH_USER_MODEL` و کلاس پایه `AbstractUser`.
- اگر استاد بپرسد: چرا در همین ابتدا ۶ اپ ایجاد شدند و چرا `AUTH_USER_MODEL` از همین مرحله ست شد؟ پاسخ: جنگو تغییر مدل کاربر را پس از اعمال اولین مایگریشن‌ها بسیار سخت و پیچیده می‌کند. طبق طراحی دامنه در `DOMAIN.md`، معماری سیستم بر پایه ۶ دامنه مجزا است و تعریف اولیه `accounts.User` از هرگونه وابستگی نامطلوب به مدل پیش‌فرض جنگو جلوگیری می‌کند.

---

### 796ac63 — docs: add process diagrams and process descriptions
- تسک: P1-03
- چه چیزی تغییر کرد: تکمیل و مستندسازی ۴ نمودار فرآیندی استاندارد Mermaid (جریان کل وب‌سایت، ماشین وضعیت سفارش اجاره، فرآیند جستجو تا ثبت و پرداخت، و فرآیند داوری و حل اختلاف) در `docs/PROCESSES.md` و بخش ۱ `docs/REPORT.md`. همچنین نگارش تشریحی و فنی فرآیندها به تفکیک وب‌سایت و هر ۶ اپلیکیشن پروژه به زبان فارسی در بخش ۲ `docs/REPORT.md`.
- چرا لازم بود: مطابق سرفصل‌های فاز ۱ پروژه درسی (طراحی فرآیندهای وب و اپلیکیشن‌ها) و اصول مهندسی نرم‌افزار، پیش از پیاده‌سازی مدل‌ها و منطق تراکنشی، باید نقشه راه جریان داده، ماشین وضعیت چرخه اجاره و مرزهای کاری هر اپلیکیشن دقیقاً مدل‌سازی و مستند شوند.
- فایل‌های مهم: `docs/PROCESSES.md`, `docs/REPORT.md`
- مفهوم جنگو/پایتون که استفاده شد: مدل‌سازی فرآیندی سیستم‌های وب (State Machine & Flowcharting)، تفکیک معماری ماژولار بر پایه دامنه‌های ۶ اپلیکیشن جنگو، رعایت استانداردهای مستندسازی مهندسی نرم‌افزار با Mermaid در مخزن گیت.
- اگر استاد بپرسد: چرا ماشین وضعیت اجاره به این شکل طراحی شد و وضعیت `disputed` در کجای چرخه قرار می‌گیرد؟ پاسخ: چرخه اجاره دارای مراحل خطی (رزرو -> پرداخت -> تحویل -> بازگشت -> اتمام و آزادسازی ودیعه) است. اما در معاملات همتابه‌همتا احتمال بروز خسارت یا نقص کالا وجود دارد؛ بنابراین حالت `disputed` طراحی شد تا در صورت بروز اختلاف، تسویه مالی و عودت ودیعه متوقف شده و تعیین تکلیف توسط مدیر (`is_staff`) صورت پذیرد.

---

### 1679587 — feat(accounts): add custom User model
- تسک: P1-04
- چه چیزی تغییر کرد: بازتعریف و تکمیل مدل سفارشی `User` در `backend/accounts/models.py` با ارث‌بری از `AbstractUser`؛ بازتعریف فیلد `email` به‌صورت یکتا و اجباری (`unique=True`)؛ افزودن فیلدهای `phone`, `city`, `neighborhood`, `bio`, `is_email_verified`؛ سفارشی‌سازی کلاس `UserAdmin` در `backend/accounts/admin.py` با الحاق فیلدهای جدید به `fieldsets` و `add_fieldsets`؛ تولید مایگریشن اولیه `0001_initial.py` و اعمال موفق آن روی پایگاه داده PostgreSQL.
- چرا لازم بود: طبق طراحی دامنه (`docs/DOMAIN.md`)، پلتفرم امانت‌یاب یک سامانه همسایگی P2P است و نیازمند نگهداری اطلاعات مکانی (شهر و محله) و اطلاعات تماسی کاربران برای ایجاد ارتباط مطمئن است. همچنین یکتا بودن ایمیل مانع ثبت‌نام‌های تکراری شده و پیش‌نیاز احراز هویت است.
- فایل‌های مهم: `backend/accounts/models.py`, `backend/accounts/admin.py`, `backend/accounts/migrations/0001_initial.py`
- مفهوم جنگو/پایتون که استفاده شد: ارث‌بری از `AbstractUser`، قید یکتایی در فیلد (`unique=True`)، متادیتا با `verbose_name` و `verbose_name_plural`، سفارشی‌سازی `django.contrib.auth.admin.UserAdmin`، سیستم مایگریشن جنگو در تعامل با PostgreSQL.
- اگر استاد بپرسد: چرا برای موجر و مستأجر دو مدل جدا یا فیلد `role` نساختی؟ پاسخ: در یک پلتفرم همتابه‌همتا، هر کاربر می‌تواند همزمان هم کالای خود را امانت دهد (موجر) و هم کالای همسایگان را به امانت بگیرد (مستأجر). بنابراین تفکیک نقش‌ها در سطح مدل کاربر اشتباه طراحی است؛ نقش در کانتکست هر تراکنش (مدل `Item` و مدل `Rental`) مشخص می‌شود.

---

### b84365d — feat(catalog): add Category, Item and ItemImage models
- تسک: P1-05
- چه چیزی تغییر کرد: پیاده‌سازی مدل‌های `Category`, `Item` و `ItemImage` در `backend/catalog/models.py`؛ افزودن قیود کنترلی دیتابیس (`item_daily_price_positive` و `item_at_least_one_delivery_method`) و ایندکس ترکیبی روی `(city, is_active)`؛ ثبت پنل مدیریت در `backend/catalog/admin.py` با `ItemImageInline`؛ تولید و اجرای مایگریشن `0001_initial.py` روی PostgreSQL.
- چرا لازم بود: کاتالوگ کالاهای قابل امانت و دسته‌بندی موضوعی آن‌ها هسته مرکزی پلتفرم امانت‌یاب است. اعمال شروط منطقی (قیمت مثبت و الزام به حداقل یک روش تحویل) در سطح پایگاه داده، تمامیت و یکپارچگی داده‌ها را تضمین می‌کند.
- فایل‌های مهم: `backend/catalog/models.py`, `backend/catalog/admin.py`, `backend/catalog/migrations/0001_initial.py`
- مفهوم جنگو/پایتون که استفاده شد: کلیدهای خارجی بازگشتی (`parent = ForeignKey("self")`)، `PROTECT` در برابر `CASCADE`، انتخاب‌های متنی (`TextChoices`)، قیدهای شرطی پایگاه داده (`models.CheckConstraint`)، ایندکس‌های پایگاه داده (`models.Index`)، و فرم‌های درون‌خطی در ادمین (`admin.TabularInline`).
- اگر استاد بپرسد: تفاوت `on_delete=models.PROTECT` و `CASCADE` در این اپ چیست؟ حذف کاربر باعث حذف کالاهای او می‌شود (`CASCADE`)، اما حذف دسته تا زمانی که کالایی در آن وجود دارد مسدود می‌شود (`PROTECT`) تا کالایی بدون دسته‌بندی در دیتابیس باقی نماند.

---

### 0fa1a60 — feat(rentals): add Rental, Payment and Dispute models
- تسک: P1-06
- چه چیزی تغییر کرد: پیاده‌سازی مدل‌های `Rental`, `Payment`, `Dispute` در `backend/rentals/models.py`؛ افزودن قید پایگاه داده `rental_end_after_start` برای تضمین `end_at > start_at`؛ پیاده‌سازی منطق اعتبارسنجی در متد `clean()` شامل ممنوعیت اجاره کالای خود توسط مالک و جلوگیری از تداخل زمانی با سفارش‌های غیرلغوشده (Double-Booking Prevention)؛ پیکربندی پنل مدیریت در `backend/rentals/admin.py` با اینلاین‌های پرداخت و اختلاف؛ تولید و اجرای مایگریشن `0001_initial.py` روی PostgreSQL.
- چرا لازم بود: هسته تراکنشی و تعاملی پلتفرم امانت‌یاب فرآیند ثبت اجاره، پرداخت مبالغ و ودیعه و رسیدگی به اختلافات است. ایجاد مدل‌های دقیق همراه با قیود پایگاه داده و اعتبارسنجی‌های نرم‌افزاری مانع از خطاهای مالی و رزرو متداخل می‌شود.
- فایل‌های مهم: `backend/rentals/models.py`, `backend/rentals/admin.py`, `backend/rentals/migrations/0001_initial.py`
- مفهوم جنگو/پایتون که استفاده شد: ارتباطات رابطه‌ای چند به یک (`ForeignKey`) با سیاست‌های حذف `PROTECT`, `CASCADE`, `SET_NULL`؛ انتخاب‌های متنی مدل (`models.TextChoices`)؛ فیلدهای مبالغ مالی (`DecimalField`)؛ ارجاع پویا به فیلدهای مدل در قید دیتابیس با `models.F` در `models.CheckConstraint`؛ اعتبارسنجی مدل در لایه اپلیکیشن با متد `clean()` و خطای `ValidationError`؛ پنل مدیریت با `TabularInline` و `StackedInline`.
- اگر استاد بپرسد: چرا برای جلوگیری از تداخل رزرو (Double-Booking) از متد `clean()` استفاده کردی و کوئری آن چگونه کار می‌کند؟ پاسخ: دو بازه زمانی $[A, B]$ و $[C, D]$ در صورتی با یکدیگر تداخل دارند که $A < D$ و $B > C$ برقرار باشد. در متد `clean()` با فیلتر روی `start_at__lt=self.end_at` و `end_at__gt=self.start_at` روی اجاره‌های غیرلغوشده همان کالا بررسی می‌کنیم که هم‌پوشانی وجود نداشته باشد و در صورت وجود، خطای `ValidationError` برگردانده شود.

---

### 49add6b — feat(reviews): add Review model
- تسک: P1-07
- چه چیزی تغییر کرد: پیاده‌سازی مدل `Review` در `backend/reviews/models.py`؛ افزودن قید پایگاه داده `review_rating_range_1_to_5` و قید یکتایی `unique_rental_reviewer_review`؛ پیاده‌سازی متد `clean()` برای کنترل ثبت نظر فقط در وضعیت `completed`، ممنوعیت نظر به خود، و انطباق طرفین با قرارداد اجاره؛ پیکربندی پنل مدیریت در `backend/reviews/admin.py`؛ تولید و اجرای مایگریشن `0001_initial.py` روی PostgreSQL.
- چرا لازم بود: ایجاد اعتماد و شفافیت در سامانه‌های همتابه‌همتا (P2P) وابسته به سیستم امتیازدهی و بازخورد دوطرفه است. تضمین این که هر طرف قرارداد حداکثر یک بار نظر می‌دهد و امتیاز همواره در بازه معتبر ۱ تا ۵ قرار دارد در سطح پایگاه داده الزامی است.
- فایل‌های مهم: `backend/reviews/models.py`, `backend/reviews/admin.py`, `backend/reviews/migrations/0001_initial.py`
- مفهوم جنگو/پایتون که استفاده شد: ارتباطات کلید خارجی (`ForeignKey`) با `CASCADE`، قیدهای پیشرفته پایگاه داده (`models.CheckConstraint` و `models.UniqueConstraint`)، انتخاب‌های متنی (`models.TextChoices`)، متد اعتبارسنجی مدل (`clean`) و کلاس مدیریت ادمین (`admin.ModelAdmin`).
- اگر استاد بپرسد: چرا اعتبارسنجی امتیاز ۱ تا ۵ را هم در دیتابیس با `CheckConstraint` و هم با فیلد `PositiveSmallIntegerField` گذاشتی؟ پاسخ: فیلد `PositiveSmallIntegerField` در فرم‌ها کمک می‌کند، اما در سطح PostgreSQL صرفاً یک ستون عدد صحیح مثبت است؛ برای جلوگیری قطعی از ورود مقادیر غیرمجاز مانند ۰ یا ۶ در تراکنش‌ها و اسکریپت‌ها، قید صریح `CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5))` تعریف شد تا در بنیادی‌ترین سطح دیتابیس `IntegrityError` تولید شود.

---

### b9996f5 — feat(chat): add Conversation and Message models
- تسک: P1-07
- چه چیزی تغییر کرد: پیاده‌سازی مدل‌های `Conversation` و `Message` در `backend/chat/models.py`؛ ایجاد قید یکتایی پایگاه داده `unique_item_renter_conversation` روی `(item, renter)`؛ ایجاد متد اعتبارسنجی `clean()` برای ممانعت از شروع گفتگوی مالک با کالای خودش و اطمینان از مجاز بودن فرستنده پیام؛ پیکربندی پنل مدیریت در `backend/chat/admin.py` با `MessageInline` و کلاس مجزای `MessageAdmin`؛ تولید و اجرای مایگریشن `0001_initial.py` روی PostgreSQL.
- چرا لازم بود: کاربران قبل از اجاره نیازمند هماهنگی درباره زمان تحویل، بررسی سلامت کالا و پرسش و پاسخ با مالک هستند. ایزوله کردن گفتگوها به ازای هر کالا و متقاضی مانع از سردرگمی پیام‌ها و ایجاد چت‌های تکراری و موازی می‌شود.
- فایل‌های مهم: `backend/chat/models.py`, `backend/chat/admin.py`, `backend/chat/migrations/0001_initial.py`
- مفهوم جنگو/پایتون که استفاده شد: ارتباطات رابطه‌ای والد-فرزند (`Conversation` و `Message`)، قید یکتایی ترکیبی (`models.UniqueConstraint`)، پراپرتی پایتون (`@property def owner(self): return self.item.owner`)، اعتبارسنجی فرستنده با `clean()` و اینلاین فرم‌ها در پنل ادمین (`admin.TabularInline`).
- اگر استاد بپرسد: چرا در مدل `Conversation` فیلد مستقلی برای `owner` ذخیره نکردی و به صورت پراپرتی از `item.owner` خواندی؟ پاسخ: رعایت اصل نرمال‌سازی داده‌ها (Normalization). مالک کالا قبلاً در مدل `Item` مشخص شده است؛ اگر فیلد دیگری برای مالک در `Conversation` ذخیره می‌کردیم افزونگی داده (Data Redundancy) ایجاد می‌شد و در صورت هرگونه تغییر کالا احتمال عدم هماهنگی داده‌ها وجود داشت.

