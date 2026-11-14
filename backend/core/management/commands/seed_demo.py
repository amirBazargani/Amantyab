import io
import math
import uuid
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from accounts.models import User
from catalog.models import Category, Item, ItemImage
from chat.models import Conversation, Message
from rentals.models import Dispute, Payment, Rental
from reviews.models import Review


def generate_placeholder_image(text, bg_color, size=(800, 600)):
    """Generate a placeholder image with PIL for an item."""
    img = Image.new("RGB", size, color=bg_color)
    draw = ImageDraw.Draw(img)

    # Outer decorative frame
    draw.rectangle([(24, 24), (size[0] - 24, size[1] - 24)], outline=(255, 255, 255), width=3)
    draw.rectangle([(34, 34), (size[0] - 34, size[1] - 34)], outline=(255, 255, 255, 120), width=1)

    # Inner badge
    center_x, center_y = size[0] // 2, size[1] // 2
    badge_w, badge_h = 420, 140
    badge_box = [
        (center_x - badge_w // 2, center_y - badge_h // 2),
        (center_x + badge_w // 2, center_y + badge_h // 2),
    ]
    draw.rounded_rectangle(badge_box, radius=16, fill=(255, 255, 255))

    font = ImageFont.load_default()
    # Draw simple title label in badge
    draw.text((center_x - 120, center_y - 20), "AMANATYAB - DEMO ITEM", fill=(30, 41, 59), font=font)
    draw.text((center_x - 120, center_y + 10), text[:32], fill=(71, 85, 105), font=font)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


class Command(BaseCommand):
    help = "Seed demo data for Amanat-yab: users, categories, items, rentals, reviews, chat, disputes."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🌱 Starting seed_demo data population..."))

        demo_password = "demo1234"

        # ---------------------------------------------------------------------
        # 1. Admin & Users
        # ---------------------------------------------------------------------
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@amanatyab.ir",
                "first_name": "مدیر",
                "last_name": "سامانه",
                "phone": "09120000001",
                "city": "تهران",
                "neighborhood": "ونک",
                "bio": "مدیر ارشد سامانه امانت‌یاب.",
                "is_staff": True,
                "is_superuser": True,
                "is_email_verified": True,
            },
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password(demo_password)
        admin_user.save()

        users_data = [
            {
                "username": "reza",
                "email": "reza@amanatyab.ir",
                "first_name": "رضا",
                "last_name": "محمدی",
                "phone": "09121111111",
                "city": "تهران",
                "neighborhood": "سعادت‌آباد",
                "bio": "علاقه‌مند به ابزارآلات برقی کارگاهی و پروژه‌های نوسازی خانگی.",
            },
            {
                "username": "sara",
                "email": "sara@amanatyab.ir",
                "first_name": "سارا",
                "last_name": "رضایی",
                "phone": "09122222222",
                "city": "تهران",
                "neighborhood": "صادقیه",
                "bio": "عکاس آزاد و علاقه‌مند به سفر و طبیعت‌گردی.",
            },
            {
                "username": "ali",
                "email": "ali@amanatyab.ir",
                "first_name": "علی",
                "last_name": "حسینی",
                "phone": "09123333333",
                "city": "اصفهان",
                "neighborhood": "چهارباغ",
                "bio": "نجار و طراح دکوراسیون داخلی در اصفهان.",
            },
            {
                "username": "maryam",
                "email": "maryam@amanatyab.ir",
                "first_name": "مریم",
                "last_name": "احمدی",
                "phone": "09124444444",
                "city": "اصفهان",
                "neighborhood": "جلفا",
                "bio": "مهندس کشاورزی و متخصص باغبانی و فضای سبز خانگی.",
            },
            {
                "username": "mehdi",
                "email": "mehdi@amanatyab.ir",
                "first_name": "مهدی",
                "last_name": "کریمی",
                "phone": "09125555555",
                "city": "تبریز",
                "neighborhood": "ائل‌گلی",
                "bio": "پیمانکار پروژه‌های ساختمانی در تبریز.",
            },
            {
                "username": "neda",
                "email": "neda@amanatyab.ir",
                "first_name": "ندا",
                "last_name": "صادقی",
                "phone": "09126666666",
                "city": "تبریز",
                "neighborhood": "ولیعصر",
                "bio": "مربی کوهنوردی و علاقه‌مند به کمپینگ در طبیعت آذربایجان.",
            },
            {
                "username": "babak",
                "email": "babak@amanatyab.ir",
                "first_name": "بابک",
                "last_name": "امینی",
                "phone": "09127777777",
                "city": "شیراز",
                "neighborhood": "ارم",
                "bio": "علاقه‌مند به ساخت ساز و کارهای چوبی و تجهیزات صوتی و تصویری.",
            },
            {
                "username": "zahra",
                "email": "zahra@amanatyab.ir",
                "first_name": "زهرا",
                "last_name": "مرادی",
                "phone": "09128888888",
                "city": "مشهد",
                "neighborhood": "احمدآباد",
                "bio": "مستندساز و معمار، ساکن مشهد.",
            },
        ]

        users = {}
        for u in users_data:
            user_obj, _ = User.objects.get_or_create(
                username=u["username"],
                defaults={
                    "email": u["email"],
                    "first_name": u["first_name"],
                    "last_name": u["last_name"],
                    "phone": u["phone"],
                    "city": u["city"],
                    "neighborhood": u["neighborhood"],
                    "bio": u["bio"],
                    "is_email_verified": True,
                },
            )
            user_obj.phone = u["phone"]
            user_obj.set_password(demo_password)
            user_obj.save()
            users[u["username"]] = user_obj

        # ---------------------------------------------------------------------
        # 2. Categories
        # ---------------------------------------------------------------------
        categories_data = [
            ("ابزارآلات برقی و شارژی", "power-tools"),
            ("تجهیزات نظافت و شستشو", "cleaning"),
            ("تجهیزات کمپینگ و سفر", "camping"),
            ("ابزار باغبانی و فضای سبز", "gardening"),
            ("تجهیزات عکاسی و تصویربرداری", "photography"),
            ("ابزار ساختمانی و کارگاهی", "construction"),
        ]

        categories = {}
        for name, slug in categories_data:
            cat_obj, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name},
            )
            categories[slug] = cat_obj

        # ---------------------------------------------------------------------
        # 3. Items (25 items with variety, at least 10 with geo coordinates)
        # ---------------------------------------------------------------------
        items_spec = [
            # 1
            {
                "owner": "reza",
                "cat": "power-tools",
                "title": "دریل بتن‌کن ۴ شیار بوش مدل GBH 2-26 DRE",
                "desc": "دریل بتن‌کن پرقدرت بوش با سه حالت سوراخ‌کاری، چکشی و تخریب سبک. مناسب برای سوراخ‌کاری در بتن و آجر.",
                "brand": "Bosch",
                "cond": Item.Condition.GOOD,
                "hourly": Decimal("30000"),
                "daily": Decimal("180000"),
                "deposit": Decimal("1000000"),
                "city": "تهران",
                "neigh": "سعادت‌آباد",
                "pickup": True,
                "courier": True,
                "lat": Decimal("35.783300"),
                "lng": Decimal("51.366700"),
                "addr": "تهران، سعادت‌آباد، میدان کاج، خیابان مروارید، پلاک ۱۲",
                "color": (37, 99, 235),
            },
            # 2
            {
                "owner": "reza",
                "cat": "cleaning",
                "title": "دستگاه کارواش دینامی ۲۰۰ بار کرچر K5",
                "desc": "کارواش قدرتمند خانگی و صنعتی کرچر ملموس با موتور القایی آب‌خنک و لنس تنظیمی به همراه شلنگ ۸ متری فشار قوی.",
                "brand": "Karcher",
                "cond": Item.Condition.LIKE_NEW,
                "hourly": None,
                "daily": Decimal("250000"),
                "deposit": Decimal("1500000"),
                "city": "تهران",
                "neigh": "سعادت‌آباد",
                "pickup": True,
                "courier": True,
                "lat": Decimal("35.785000"),
                "lng": Decimal("51.369000"),
                "addr": "تهران، سعادت‌آباد، بلوار سرو غربی، پلاک ۴۴",
                "color": (234, 179, 8),
            },
            # 3
            {
                "owner": "sara",
                "cat": "construction",
                "title": "تراز لیزری ۳۶۰ درجه دیوالت مدل DCE089D1G",
                "desc": "تراز لیزری نور سبز فوق‌العاده با دید عالی در روز و برد ۳۰ متر. دارای پایه مگنتی اتصال به سطوح فلزی.",
                "brand": "DeWalt",
                "cond": Item.Condition.NEW,
                "hourly": Decimal("25000"),
                "daily": Decimal("150000"),
                "deposit": Decimal("800000"),
                "city": "تهران",
                "neigh": "صادقیه",
                "pickup": True,
                "courier": True,
                "lat": Decimal("35.720800"),
                "lng": Decimal("51.341400"),
                "addr": "تهران، فلکه دوم صادقیه، ابتدای خیابان کاشانی، مجتمع طلا",
                "color": (245, 158, 11),
            },
            # 4
            {
                "owner": "sara",
                "cat": "photography",
                "title": "دوربین سونی Alpha A7 III با لنز ۲۴-۷۰ میلی‌متر",
                "desc": "دوربین فول‌فریم حرفه‌ای با سنسور ۲۴ مگاپیکسل، فیلم‌برداری 4K، فوکوس خودکار بسیار سریع به همراه لنز همه‌کاره.",
                "brand": "Sony",
                "cond": Item.Condition.LIKE_NEW,
                "hourly": Decimal("90000"),
                "daily": Decimal("650000"),
                "deposit": Decimal("5000000"),
                "city": "تهران",
                "neigh": "صادقیه",
                "pickup": True,
                "courier": False,
                "lat": Decimal("35.722000"),
                "lng": Decimal("51.338000"),
                "addr": "تهران، صادقیه، بلوار فردوس شرق، پلاک ۱۰",
                "color": (99, 102, 241),
            },
            # 5
            {
                "owner": "ali",
                "cat": "camping",
                "title": "چادر ۴ نفره دوپوش ضدآب کلمن مدل Sundome",
                "desc": "چادر مقاوم در برابر باد و باران شدید، مجهز به پوش دوم ضد باران، پنجره‌های تهویه هوا و کفی ضخیم عایق رطوبت.",
                "brand": "Coleman",
                "cond": Item.Condition.GOOD,
                "hourly": None,
                "daily": Decimal("120000"),
                "deposit": Decimal("600000"),
                "city": "اصفهان",
                "neigh": "چهارباغ",
                "pickup": True,
                "courier": True,
                "lat": Decimal("32.654600"),
                "lng": Decimal("51.668000"),
                "addr": "اصفهان، خیابان چهارباغ عباسی، جنب مجتمع پارک",
                "color": (16, 185, 129),
            },
            # 6
            {
                "owner": "ali",
                "cat": "power-tools",
                "title": "اره فارسی‌بر کشویی ماکیتا مدل LS1018L",
                "desc": "اره فارسی‌بر دقیق نجاری با خط لیزری هدایت برش و زاویه‌زن دوطرفه. مجهز به تیغ مخصوص برش چوب و ام‌دی‌اف.",
                "brand": "Makita",
                "cond": Item.Condition.GOOD,
                "hourly": Decimal("40000"),
                "daily": Decimal("220000"),
                "deposit": Decimal("1200000"),
                "city": "اصفهان",
                "neigh": "چهارباغ",
                "pickup": True,
                "courier": False,
                "lat": Decimal("32.656000"),
                "lng": Decimal("51.665000"),
                "addr": "اصفهان، خیابان شیخ بهایی، کوچه بهار، پلاک ۵",
                "color": (6, 182, 212),
            },
            # 7
            {
                "owner": "maryam",
                "cat": "gardening",
                "title": "قیچی و شمشادزن موتوری هوندا مدل HHH25D",
                "desc": "شمشادزن سبک بنزینی با تیغه دوبل ۶۰ سانتی‌متری ساخت ژاپن، ایده‌آل برای شکل‌دهی به پرچین‌ها و بوته‌های ویلا.",
                "brand": "Honda",
                "cond": Item.Condition.LIKE_NEW,
                "hourly": Decimal("35000"),
                "daily": Decimal("200000"),
                "deposit": Decimal("1000000"),
                "city": "اصفهان",
                "neigh": "جلفا",
                "pickup": True,
                "courier": True,
                "lat": Decimal("32.635800"),
                "lng": Decimal("51.654700"),
                "addr": "اصفهان، محله جلفا، کوچه کلیسا وانک، پلاک ۲۳",
                "color": (239, 68, 68),
            },
            # 8
            {
                "owner": "maryam",
                "cat": "cleaning",
                "title": "بخارشوی صنعتی کارچر مدل SV7 چندکاره",
                "desc": "دستگاه بخارشو و جاروبرقی همزمان بدون نیاز به مواد شیمیایی با قدرت ضدعفونی ۹۹.۹ درصد سطوح سخت و سرامیک.",
                "brand": "Karcher",
                "cond": Item.Condition.NEW,
                "hourly": None,
                "daily": Decimal("280000"),
                "deposit": Decimal("2000000"),
                "city": "اصفهان",
                "neigh": "جلفا",
                "pickup": True,
                "courier": True,
                "lat": Decimal("32.638000"),
                "lng": Decimal("51.652000"),
                "addr": "اصفهان، خیابان خاقانی، روبروی خواجه پطرس",
                "color": (234, 179, 8),
            },
            # 9
            {
                "owner": "mehdi",
                "cat": "construction",
                "title": "اینورتر جوشکاری ۲۰۰ آمپر دیجیتال رونیکس مدل RH-4602",
                "desc": "دستگاه جوش اینورتر سبک با سیستم ضد چسبندگی Anti-Stick و فیش‌های برنجی صنعتی به همراه کابل و انبر جوش.",
                "brand": "Ronix",
                "cond": Item.Condition.GOOD,
                "hourly": Decimal("30000"),
                "daily": Decimal("160000"),
                "deposit": Decimal("900000"),
                "city": "تبریز",
                "neigh": "ائل‌گلی",
                "pickup": True,
                "courier": True,
                "lat": Decimal("38.026400"),
                "lng": Decimal("46.368300"),
                "addr": "تبریز، بلوار ائل گلی، روبروی هتل پارس",
                "color": (220, 38, 38),
            },
            # 10
            {
                "owner": "mehdi",
                "cat": "construction",
                "title": "چکش تخریب ۱۱ کیلویی نک (NEK) مدل 1640DB",
                "desc": "پیکور صنعتی پرقدرت با انرژی ضربه‌ای ۲۵ ژول، مناسب برای تخریب بتن‌های مقاوم، کف‌سازی و عملیات عمرانی.",
                "brand": "NEK",
                "cond": Item.Condition.FAIR,
                "hourly": Decimal("45000"),
                "daily": Decimal("260000"),
                "deposit": Decimal("1500000"),
                "city": "تبریز",
                "neigh": "ائل‌گلی",
                "pickup": True,
                "courier": False,
                "lat": Decimal("38.029000"),
                "lng": Decimal("46.365000"),
                "addr": "تبریز، ائل گلی، گلشهر، خیابان فردوس",
                "color": (107, 114, 128),
            },
            # 11
            {
                "owner": "neda",
                "cat": "camping",
                "title": "کیسه خواب پر منفی ۱۰ درجه فرینو مدل Lightec",
                "desc": "کیسه خواب سبک با عایق پر غاز با تراکم ۸۰۰ و پارچه ضد پارگی ریپ‌استاپ. دمای آسایش منفی ۶ درجه سانتی‌گراد.",
                "brand": "Ferrino",
                "cond": Item.Condition.LIKE_NEW,
                "hourly": None,
                "daily": Decimal("95000"),
                "deposit": Decimal("500000"),
                "city": "تبریز",
                "neigh": "ولیعصر",
                "pickup": True,
                "courier": True,
                "lat": Decimal("38.069100"),
                "lng": Decimal("46.353300"),
                "addr": "تبریز، ولیعصر، خیابان مخابرات، پلاک ۱۷",
                "color": (59, 130, 246),
            },
            # 12
            {
                "owner": "neda",
                "cat": "gardening",
                "title": "علف‌زن دوشی بنزینی کناپ دو زمانه",
                "desc": "دستگاه علف‌تراش موتوری به همراه تیغه فولادی ۴۰ پره الماسه و توپی نخ نایلونی جهت پاکسازی علف‌های هرز باغ.",
                "brand": "Knap",
                "cond": Item.Condition.GOOD,
                "hourly": Decimal("25000"),
                "daily": Decimal("140000"),
                "deposit": Decimal("700000"),
                "city": "تبریز",
                "neigh": "ولیعصر",
                "pickup": True,
                "courier": True,
                "lat": Decimal("38.071000"),
                "lng": Decimal("46.351000"),
                "addr": "تبریز، ولیعصر، خیابان همام تبریزی، کوچه آذر",
                "color": (16, 185, 129),
            },
            # 13
            {
                "owner": "babak",
                "cat": "photography",
                "title": "سه‌پایه دوربین فیبر کربن مانفروتو مدل Befree Advanced",
                "desc": "سه‌پایه سبک و فوق‌العاده مقاوم مسافرتی با بال‌هد حرفه‌ای مانفروتو، تحمل وزن تا ۹ کیلوگرم تجهیزات فیلم‌برداری.",
                "brand": "Manfrotto",
                "cond": Item.Condition.LIKE_NEW,
                "hourly": Decimal("20000"),
                "daily": Decimal("110000"),
                "deposit": Decimal("800000"),
                "city": "شیراز",
                "neigh": "ارم",
                "pickup": True,
                "courier": True,
                "lat": Decimal("29.636000"),
                "lng": Decimal("52.528400"),
                "addr": "شیراز، میدان ارم، ابتدای بلوار دانشجو",
                "color": (75, 85, 99),
            },
            # 14
            {
                "owner": "babak",
                "cat": "power-tools",
                "title": "پیچ‌گوشتی ضربه‌ای شارژی میلواکی مدل M18 Fuel",
                "desc": "ایمپکت درایور براشلس با گشتاور ۲۲۶ نیوتن‌متر و باتری ۵ آمپرساعت، مناسب باز و بستن پیچ‌های سنگین سازه.",
                "brand": "Milwaukee",
                "cond": Item.Condition.NEW,
                "hourly": Decimal("35000"),
                "daily": Decimal("190000"),
                "deposit": Decimal("1100000"),
                "city": "شیراز",
                "neigh": "ارم",
                "pickup": True,
                "courier": True,
                "lat": Decimal("29.639000"),
                "lng": Decimal("52.525000"),
                "addr": "شیراز، خیابان ارم، کوچه ۱۲، ساختمان گل‌ها",
                "color": (220, 38, 38),
            },
            # 15
            {
                "owner": "zahra",
                "cat": "photography",
                "title": "کیت نورپردازی استودیویی گودکس دو شاخه با سافت‌باکس",
                "desc": "دو عدد شاخه نور فلاش استودیویی ۳۰۰ ژول گودکس به همراه ریموت تریگر، پایه‌های بادی و سافت‌باکس‌های زنبوری.",
                "brand": "Godox",
                "cond": Item.Condition.GOOD,
                "hourly": Decimal("50000"),
                "daily": Decimal("320000"),
                "deposit": Decimal("1800000"),
                "city": "مشهد",
                "neigh": "احمدآباد",
                "pickup": True,
                "courier": True,
                "lat": None,
                "lng": None,
                "addr": "مشهد، بلوار احمدآباد، خیابان عدالت",
                "color": (147, 51, 234),
            },
            # 16
            {
                "owner": "zahra",
                "cat": "power-tools",
                "title": "فرز آهنگری رونیکس مدل ۳۱۵۰ پرقدرت ۲۲۰۰ وات",
                "desc": "دستگاه سنگ فرز با صفحه ۲۳۰ میلی‌متری و دسته جانبی ضد لرزش برای برش انواع مقاطع فلزی و پروفیل‌های ساختمانی.",
                "brand": "Ronix",
                "cond": Item.Condition.GOOD,
                "hourly": Decimal("20000"),
                "daily": Decimal("130000"),
                "deposit": Decimal("600000"),
                "city": "مشهد",
                "neigh": "احمدآباد",
                "pickup": True,
                "courier": False,
                "lat": None,
                "lng": None,
                "addr": "مشهد، احمدآباد، خیابان ملاصدرا",
                "color": (220, 38, 38),
            },
            # 17
            {
                "owner": "reza",
                "cat": "cleaning",
                "title": "مینی‌واش و تورنادوگان صفرشویی خودرو",
                "desc": "گان تورنادو نظافت داخل کابین خودرو با مخزن ترکیب شوینده و تنظیم پاشش کف متراکم برای شستشوی سقف و صندلی‌ها.",
                "brand": "Tornado",
                "cond": Item.Condition.LIKE_NEW,
                "hourly": Decimal("15000"),
                "daily": Decimal("90000"),
                "deposit": Decimal("400000"),
                "city": "تهران",
                "neigh": "ونک",
                "pickup": True,
                "courier": True,
                "lat": None,
                "lng": None,
                "addr": "",
                "color": (14, 165, 233),
            },
            # 18
            {
                "owner": "ali",
                "cat": "gardening",
                "title": "اره زنجیری بنزینی اشتیل MS250 تیغه ۴۵ سانتی‌متر",
                "desc": "اره موتوری پرقدرت و خوش‌دست آلمانی مناسب هرس سنگین درختان و برش کنده‌های چوبی قطور در باغات و کارگاه‌ها.",
                "brand": "Stihl",
                "cond": Item.Condition.FAIR,
                "hourly": Decimal("40000"),
                "daily": Decimal("230000"),
                "deposit": Decimal("1200000"),
                "city": "اصفهان",
                "neigh": "پل خواجو",
                "pickup": True,
                "courier": False,
                "lat": None,
                "lng": None,
                "addr": "",
                "color": (249, 115, 22),
            },
            # 19
            {
                "owner": "sara",
                "cat": "camping",
                "title": "ست اجاق و ظروف پخت‌وپز کوهنوردی استنلی",
                "desc": "مجموعه کمپینگ تمام استیل ضد زنگ شامل کتری، قابلمه، ماهی‌تابه نچسب و کاسه‌ها برای پخت غذای گرم در طبیعت.",
                "brand": "Stanley",
                "cond": Item.Condition.LIKE_NEW,
                "hourly": None,
                "daily": Decimal("75000"),
                "deposit": Decimal("400000"),
                "city": "تهران",
                "neigh": "تجریش",
                "pickup": True,
                "courier": True,
                "lat": None,
                "lng": None,
                "addr": "",
                "color": (5, 150, 105),
            },
            # 20
            {
                "owner": "mehdi",
                "cat": "construction",
                "title": "میکسر رنگ و ملات رونیکس دو سرعته",
                "desc": "همزن برقی ۱۴۰۰ وات صنعتی برای آماده‌سازی یکدست رنگ‌های پلاستیک و اکریلیک، چسب کاشی و ملات‌های سبک ساختمانی.",
                "brand": "Ronix",
                "cond": Item.Condition.GOOD,
                "hourly": Decimal("20000"),
                "daily": Decimal("110000"),
                "deposit": Decimal("500000"),
                "city": "تبریز",
                "neigh": "آبرسان",
                "pickup": True,
                "courier": True,
                "lat": None,
                "lng": None,
                "addr": "",
                "color": (185, 28, 28),
            },
            # 21
            {
                "owner": "babak",
                "cat": "cleaning",
                "title": "دستگاه پولیشر چرخشی زنتول مدل R21",
                "desc": "دستگاه پولیش اوربیتال با پد ۱۵۰ میلی‌متری و کنترل سرعت ۶ حالته جهت برطرف کردن خط و خش و احیای رنگ خودرو.",
                "brand": "Zentool",
                "cond": Item.Condition.GOOD,
                "hourly": Decimal("30000"),
                "daily": Decimal("170000"),
                "deposit": Decimal("900000"),
                "city": "شیراز",
                "neigh": "معالی‌آباد",
                "pickup": True,
                "courier": True,
                "lat": None,
                "lng": None,
                "addr": "",
                "color": (13, 148, 136),
            },
            # 22
            {
                "owner": "neda",
                "cat": "camping",
                "title": "کوله‌پشتی ۶۵ لیتری دیوتر مدل Aircontact Pro",
                "desc": "کوله فنی کوهنوردی با سیستم تقسیم وزن ارگونومیک، بندهای ضدتعریق و کاور ضدباران مناسب برنامه‌های چندروزه.",
                "brand": "Deuter",
                "cond": Item.Condition.GOOD,
                "hourly": None,
                "daily": Decimal("85000"),
                "deposit": Decimal("600000"),
                "city": "تبریز",
                "neigh": "ائل‌گلی",
                "pickup": True,
                "courier": True,
                "lat": None,
                "lng": None,
                "addr": "",
                "color": (30, 64, 175),
            },
            # 23
            {
                "owner": "zahra",
                "cat": "photography",
                "title": "لنز پرایم ۵۰ میلی‌متر اف ۱.۴ سیگما آرت",
                "desc": "لنز پرتره فوق‌العاده شارپ سری Art سیگما با دیافراگم بسیار باز f/1.4 برای بوکه‌های جذاب و عکاسی در نور کم.",
                "brand": "Sigma",
                "cond": Item.Condition.LIKE_NEW,
                "hourly": Decimal("40000"),
                "daily": Decimal("240000"),
                "deposit": Decimal("1500000"),
                "city": "مشهد",
                "neigh": "وکیل‌آباد",
                "pickup": True,
                "courier": False,
                "lat": None,
                "lng": None,
                "addr": "",
                "color": (55, 65, 81),
            },
            # 24
            {
                "owner": "maryam",
                "cat": "gardening",
                "title": "دستگاه چمن‌زن برقی بوش مدل Rotak 32",
                "desc": "چمن‌زن سبک خانگی با سبد جمع‌آوری ۳۱ لیتری و قابلیت تنظیم ارتفاع برش ۳ حالته برای محوطه و حیاط ویلا.",
                "brand": "Bosch",
                "cond": Item.Condition.GOOD,
                "hourly": None,
                "daily": Decimal("160000"),
                "deposit": Decimal("800000"),
                "city": "اصفهان",
                "neigh": "بزرگمهر",
                "pickup": True,
                "courier": True,
                "lat": None,
                "lng": None,
                "addr": "",
                "color": (22, 163, 74),
            },
            # 25
            {
                "owner": "reza",
                "cat": "power-tools",
                "title": "سنباده لرزان بوش مدل GSS 140 گردان",
                "desc": "سنباده اوربیتال با سیستم فیلتر گرد و غبار میکرو و تعویض آسان کاغذ سنباده مناسب پرداخت ظریف چوب و بتونه.",
                "brand": "Bosch",
                "cond": Item.Condition.LIKE_NEW,
                "hourly": Decimal("20000"),
                "daily": Decimal("110000"),
                "deposit": Decimal("500000"),
                "city": "تهران",
                "neigh": "سعادت‌آباد",
                "pickup": True,
                "courier": True,
                "lat": None,
                "lng": None,
                "addr": "",
                "color": (30, 58, 138),
            },
        ]

        items = []
        for spec in items_spec:
            owner_user = users[spec["owner"]]
            cat_obj = categories[spec["cat"]]

            item_obj = Item.objects.filter(owner=owner_user, title=spec["title"]).first()
            if not item_obj:
                item_obj = Item.objects.create(
                    owner=owner_user,
                    category=cat_obj,
                    title=spec["title"],
                    description=spec["desc"],
                    brand=spec["brand"],
                    condition=spec["cond"],
                    hourly_price=spec["hourly"],
                    daily_price=spec["daily"],
                    deposit_amount=spec["deposit"],
                    city=spec["city"],
                    neighborhood=spec["neigh"],
                    allow_pickup=spec["pickup"],
                    allow_courier=spec["courier"],
                    is_active=True,
                    latitude=spec["lat"],
                    longitude=spec["lng"],
                    address_text=spec["addr"],
                )
            else:
                # Keep fields aligned
                item_obj.latitude = spec["lat"]
                item_obj.longitude = spec["lng"]
                item_obj.address_text = spec["addr"]
                item_obj.save(update_fields=["latitude", "longitude", "address_text"])

            # Ensure placeholder image
            if not item_obj.images.exists():
                img_bytes = generate_placeholder_image(spec["title"], spec["color"])
                img_file = ContentFile(img_bytes, name=f"item_{item_obj.pk}.jpg")
                ItemImage.objects.create(
                    item=item_obj,
                    image=img_file,
                    is_primary=True,
                    order=0,
                )

            items.append(item_obj)

        now = timezone.now()

        # Helper to compute pricing
        def calc_amounts(item, start_at, end_at):
            duration = end_at - start_at
            total_seconds = Decimal(str(duration.total_seconds()))
            hours_float = float(total_seconds / Decimal("3600"))
            days_float = float(total_seconds / Decimal("86400"))
            if duration < timedelta(hours=24) and item.hourly_price is not None:
                units = max(1, math.ceil(hours_float))
                rent = (Decimal(units) * item.hourly_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            else:
                units = max(1, math.ceil(days_float))
                rent = (Decimal(units) * item.daily_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            comm_rate = Decimal("0.15")
            comm_amount = (rent * comm_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            payout = rent - comm_amount
            deposit = (item.deposit_amount or Decimal(0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            return rent, deposit, comm_rate, comm_amount, payout

        # ---------------------------------------------------------------------
        # 4. Rentals across EVERY status
        # ---------------------------------------------------------------------
        rentals_spec = [
            # 1: PENDING_PAYMENT
            {
                "item_idx": 0,  # Item 1 (owner: reza)
                "renter": "sara",
                "start": now + timedelta(days=2),
                "end": now + timedelta(days=4),
                "method": Rental.DeliveryMethod.PICKUP,
                "status": Rental.Status.PENDING_PAYMENT,
                "tracking": "AMN-DEMO-001-PEND",
                "del_addr": "",
                "del_lat": None,
                "del_lng": None,
                "reminder_at": None,
            },
            # 2: CONFIRMED
            {
                "item_idx": 2,  # Item 3 (owner: sara)
                "renter": "ali",
                "start": now + timedelta(days=1),
                "end": now + timedelta(days=3),
                "method": Rental.DeliveryMethod.PICKUP,
                "status": Rental.Status.CONFIRMED,
                "tracking": "AMN-DEMO-002-CONF",
                "del_addr": "",
                "del_lat": None,
                "del_lng": None,
                "reminder_at": None,
            },
            # 3: HANDED_OVER - ends in ~2 hours (Reminder Window Demo)
            {
                "item_idx": 4,  # Item 5 (owner: ali)
                "renter": "maryam",
                "start": now - timedelta(days=2),
                "end": now + timedelta(hours=2),
                "method": Rental.DeliveryMethod.PICKUP,
                "status": Rental.Status.HANDED_OVER,
                "tracking": "AMN-DEMO-003-REM2H",
                "del_addr": "",
                "del_lat": None,
                "del_lng": None,
                "reminder_at": None,  # Not sent yet: ready for reminder command test
            },
            # 4: HANDED_OVER - ends in 3 days
            {
                "item_idx": 8,  # Item 9 (owner: mehdi)
                "renter": "babak",
                "start": now - timedelta(days=1),
                "end": now + timedelta(days=3),
                "method": Rental.DeliveryMethod.PICKUP,
                "status": Rental.Status.HANDED_OVER,
                "tracking": "AMN-DEMO-004-HO3D",
                "del_addr": "",
                "del_lat": None,
                "del_lng": None,
                "reminder_at": None,
            },
            # 5: HANDED_OVER - COURIER with delivery point
            {
                "item_idx": 1,  # Item 2 (owner: reza)
                "renter": "neda",
                "start": now - timedelta(days=1),
                "end": now + timedelta(days=2),
                "method": Rental.DeliveryMethod.COURIER,
                "status": Rental.Status.HANDED_OVER,
                "tracking": "AMN-DEMO-005-COUR",
                "del_addr": "تهران، میدان پونک، بلوار میرزابابایی، کوچه گلستان، پلاک ۱۸",
                "del_lat": Decimal("35.768000"),
                "del_lng": Decimal("51.343000"),
                "reminder_at": None,
            },
            # 6: RETURNED
            {
                "item_idx": 6,  # Item 7 (owner: maryam)
                "renter": "zahra",
                "start": now - timedelta(days=3),
                "end": now - timedelta(hours=4),
                "method": Rental.DeliveryMethod.PICKUP,
                "status": Rental.Status.RETURNED,
                "tracking": "AMN-DEMO-006-RET",
                "del_addr": "",
                "del_lat": None,
                "del_lng": None,
                "reminder_at": None,
            },
            # 7: COMPLETED (with full 2-way reviews)
            {
                "item_idx": 5,  # Item 6 (owner: ali)
                "renter": "mehdi",
                "start": now - timedelta(days=7),
                "end": now - timedelta(days=5),
                "method": Rental.DeliveryMethod.PICKUP,
                "status": Rental.Status.COMPLETED,
                "tracking": "AMN-DEMO-007-COMP1",
                "del_addr": "",
                "del_lat": None,
                "del_lng": None,
                "reminder_at": None,
            },
            # 8: COMPLETED (with 1 review)
            {
                "item_idx": 10,  # Item 11 (owner: neda)
                "renter": "babak",
                "start": now - timedelta(days=10),
                "end": now - timedelta(days=8),
                "method": Rental.DeliveryMethod.PICKUP,
                "status": Rental.Status.COMPLETED,
                "tracking": "AMN-DEMO-008-COMP2",
                "del_addr": "",
                "del_lat": None,
                "del_lng": None,
                "reminder_at": None,
            },
            # 9: CANCELLED
            {
                "item_idx": 12,  # Item 13 (owner: babak)
                "renter": "sara",
                "start": now + timedelta(days=5),
                "end": now + timedelta(days=7),
                "method": Rental.DeliveryMethod.PICKUP,
                "status": Rental.Status.CANCELLED,
                "tracking": "AMN-DEMO-009-CANC",
                "del_addr": "",
                "del_lat": None,
                "del_lng": None,
                "reminder_at": None,
            },
            # 10: DISPUTED - OPEN dispute
            {
                "item_idx": 3,  # Item 4 (owner: sara)
                "renter": "reza",
                "start": now - timedelta(days=3),
                "end": now - timedelta(days=1),
                "method": Rental.DeliveryMethod.PICKUP,
                "status": Rental.Status.DISPUTED,
                "tracking": "AMN-DEMO-010-DISPOPEN",
                "del_addr": "",
                "del_lat": None,
                "del_lng": None,
                "reminder_at": None,
            },
            # 11: COMPLETED - RESOLVED dispute
            {
                "item_idx": 9,  # Item 10 (owner: mehdi)
                "renter": "zahra",
                "start": now - timedelta(days=6),
                "end": now - timedelta(days=4),
                "method": Rental.DeliveryMethod.PICKUP,
                "status": Rental.Status.COMPLETED,
                "tracking": "AMN-DEMO-011-DISPRES",
                "del_addr": "",
                "del_lat": None,
                "del_lng": None,
                "reminder_at": None,
            },
        ]

        created_rentals = {}
        for r_spec in rentals_spec:
            item_obj = items[r_spec["item_idx"]]
            renter_user = users[r_spec["renter"]]
            rent_amt, dep_amt, comm_rate, comm_amt, payout_amt = calc_amounts(
                item_obj, r_spec["start"], r_spec["end"]
            )

            rental_obj = Rental.objects.filter(tracking_code=r_spec["tracking"]).first()
            if not rental_obj:
                rental_obj = Rental.objects.create(
                    item=item_obj,
                    renter=renter_user,
                    start_at=r_spec["start"],
                    end_at=r_spec["end"],
                    delivery_method=r_spec["method"],
                    status=r_spec["status"],
                    rent_amount=rent_amt,
                    deposit_amount=dep_amt,
                    commission_rate=comm_rate,
                    commission_amount=comm_amt,
                    owner_payout=payout_amt,
                    tracking_code=r_spec["tracking"],
                    delivery_address=r_spec["del_addr"],
                    delivery_latitude=r_spec["del_lat"],
                    delivery_longitude=r_spec["del_lng"],
                    reminder_sent_at=r_spec["reminder_at"],
                )
            else:
                rental_obj.status = r_spec["status"]
                rental_obj.start_at = r_spec["start"]
                rental_obj.end_at = r_spec["end"]
                rental_obj.delivery_address = r_spec["del_addr"]
                rental_obj.delivery_latitude = r_spec["del_lat"]
                rental_obj.delivery_longitude = r_spec["del_lng"]
                rental_obj.reminder_sent_at = r_spec["reminder_at"]
                rental_obj.save()

            created_rentals[r_spec["tracking"]] = rental_obj

        # ---------------------------------------------------------------------
        # 5. Payments for rentals
        # ---------------------------------------------------------------------
        def ensure_payment(rental, kind, amount, receipt_no, status=Payment.Status.SUCCESS):
            if amount <= 0:
                return None
            payment_obj, _ = Payment.objects.get_or_create(
                receipt_no=receipt_no,
                defaults={
                    "rental": rental,
                    "kind": kind,
                    "amount": amount,
                    "status": status,
                },
            )
            return payment_obj

        # Confirmed, Handed Over, Returned, Completed, Disputed have initial rent & deposit payments
        paid_statuses = [
            Rental.Status.CONFIRMED,
            Rental.Status.HANDED_OVER,
            Rental.Status.RETURNED,
            Rental.Status.COMPLETED,
            Rental.Status.DISPUTED,
        ]

        for r_spec in rentals_spec:
            tracking = r_spec["tracking"]
            rental = created_rentals[tracking]
            if rental.status in paid_statuses or tracking == "AMN-DEMO-011-DISPRES":
                ensure_payment(rental, Payment.Kind.RENT, rental.rent_amount, f"RCP-RENT-{rental.pk}")
                if rental.deposit_amount > 0:
                    ensure_payment(rental, Payment.Kind.DEPOSIT, rental.deposit_amount, f"RCP-DEP-{rental.pk}")

        # Completed rentals have deposit refund and owner payout
        for comp_tracking in ["AMN-DEMO-007-COMP1", "AMN-DEMO-008-COMP2"]:
            comp_rental = created_rentals[comp_tracking]
            if comp_rental.deposit_amount > 0:
                ensure_payment(
                    comp_rental,
                    Payment.Kind.DEPOSIT_REFUND,
                    comp_rental.deposit_amount,
                    f"RCP-DEPREF-{comp_rental.pk}",
                )
            if comp_rental.owner_payout > 0:
                ensure_payment(
                    comp_rental,
                    Payment.Kind.PAYOUT,
                    comp_rental.owner_payout,
                    f"RCP-PAYOUT-{comp_rental.pk}",
                )

        # ---------------------------------------------------------------------
        # 6. Reviews (on completed rentals)
        # ---------------------------------------------------------------------
        rental_comp1 = created_rentals["AMN-DEMO-007-COMP1"]
        # Reviewer: mehdi (renter), Reviewee: ali (owner)
        Review.objects.get_or_create(
            rental=rental_comp1,
            reviewer=rental_comp1.renter,
            defaults={
                "reviewee": rental_comp1.item.owner,
                "reviewee_role": Review.Role.OWNER,
                "rating": 5,
                "comment": "اره فارسی‌بر ماکیتا بسیار باکیفیت و دقیق بود. آقای حسینی هم ابزار را کاملاً تمیز و سر وقت تحویل دادند.",
            },
        )
        # Reviewer: ali (owner), Reviewee: mehdi (renter)
        Review.objects.get_or_create(
            rental=rental_comp1,
            reviewer=rental_comp1.item.owner,
            defaults={
                "reviewee": rental_comp1.renter,
                "reviewee_role": Review.Role.RENTER,
                "rating": 5,
                "comment": "مشتری بسیار محترم و خوش‌حساب. کالا در نهایت سلامت و سر موقع عودت داده شد. با تشکر.",
            },
        )

        rental_comp2 = created_rentals["AMN-DEMO-008-COMP2"]
        # Reviewer: babak (renter), Reviewee: neda (owner)
        Review.objects.get_or_create(
            rental=rental_comp2,
            reviewer=rental_comp2.renter,
            defaults={
                "reviewee": rental_comp2.item.owner,
                "reviewee_role": Review.Role.OWNER,
                "rating": 4,
                "comment": "کیسه خواب در شب‌های سرد کوهستان بسیار گرم و عالی بود. کاملاً از اجاره رضایت داشتم.",
            },
        )

        # ---------------------------------------------------------------------
        # 7. Chat (2 Conversations with Messages)
        # ---------------------------------------------------------------------
        # Conv 1: Item 1 (owner: reza), renter: sara
        conv1_item = items[0]
        conv1_renter = users["sara"]
        conv1, _ = Conversation.objects.get_or_create(item=conv1_item, renter=conv1_renter)
        if not conv1.messages.exists():
            Message.objects.create(
                conversation=conv1,
                sender=conv1_renter,
                body="سلام وقت بخیر جناب محمدی، آیا مته‌های سایز ۸ و ۱۰ هم همراه دریل هست؟",
                is_read=True,
            )
            Message.objects.create(
                conversation=conv1,
                sender=conv1_item.owner,
                body="سلام خانم رضایی، بله ۴ سایز مته پرکاربرد ۴ شیار همراه با خط‌کش تنظیم عمق داخل جعبه قرار دارد.",
                is_read=True,
            )
            Message.objects.create(
                conversation=conv1,
                sender=conv1_renter,
                body="بسیار عالی، درخواست اجاره رو برای دو روز دیگر ثبت کردم. ممنون از پاسخگویی سریع شما.",
                is_read=False,
            )

        # Conv 2: Item 5 (owner: ali), renter: maryam
        conv2_item = items[4]
        conv2_renter = users["maryam"]
        conv2, _ = Conversation.objects.get_or_create(item=conv2_item, renter=conv2_renter)
        if not conv2.messages.exists():
            Message.objects.create(
                conversation=conv2,
                sender=conv2_renter,
                body="درود آقای حسینی، چادر کلمن در برابر بارندگی شدید چقدر مقاومه؟ آیا کفی هم عایق رطوبت داره؟",
                is_read=True,
            )
            Message.objects.create(
                conversation=conv2,
                sender=conv2_item.owner,
                body="سلام، بله پوش دوم چادر تا ۳۰۰۰ میلی‌متر ضدآبه و کفی ضخیم تارب پلی‌اتیلن داره، خیالتون کاملاً راحت باشه.",
                is_read=True,
            )
            Message.objects.create(
                conversation=conv2,
                sender=conv2_renter,
                body="خیلی ممنون از راهنماییتون، با تشکر.",
                is_read=True,
            )

        # ---------------------------------------------------------------------
        # 8. Disputes (1 Open, 1 Resolved)
        # ---------------------------------------------------------------------
        # 1 Open Dispute on rental AMN-DEMO-010-DISPOPEN (Item 4: Camera Sony)
        rental_disp_open = created_rentals["AMN-DEMO-010-DISPOPEN"]
        dispute_open = Dispute.objects.filter(rental=rental_disp_open).first()
        if not dispute_open:
            Dispute.objects.create(
                rental=rental_disp_open,
                opened_by=rental_disp_open.item.owner,
                reason="لنز دوربین در هنگام عودت دارای خط و خش روی عدسی جلویی بود و درپوش اصلی لنز تحویل داده نشد.",
                status=Dispute.Status.OPEN,
            )

        # 1 Resolved Dispute on rental AMN-DEMO-011-DISPRES (Item 10: Demolition Hammer)
        rental_disp_res = created_rentals["AMN-DEMO-011-DISPRES"]
        dispute_res = Dispute.objects.filter(rental=rental_disp_res).first()
        if not dispute_res:
            dispute_res = Dispute.objects.create(
                rental=rental_disp_res,
                opened_by=rental_disp_res.renter,
                reason="دستگاه چکش تخریب در بدو تحویل روشن نشد و سیم‌پیچ داخلی آن سوخته بود.",
                status=Dispute.Status.RESOLVED,
                deposit_decision=Dispute.DepositDecision.RETURN_TO_RENTER,
                resolution_note="پس از بررسی تصاویر ارسالی و گزارش کارشناس، ایراد فنی کابل قبلی تایید شد و ودیعه به طور کامل به اجاره‌کننده عودت یافت.",
                resolved_by=admin_user,
                resolved_at=now - timedelta(days=3),
            )
            # Create refund and payout records for resolved dispute
            if rental_disp_res.deposit_amount > 0:
                ensure_payment(
                    rental_disp_res,
                    Payment.Kind.DEPOSIT_REFUND,
                    rental_disp_res.deposit_amount,
                    f"RCP-DEP-REF-DISP-{rental_disp_res.pk}",
                )
            if rental_disp_res.owner_payout > 0:
                ensure_payment(
                    rental_disp_res,
                    Payment.Kind.PAYOUT,
                    rental_disp_res.owner_payout,
                    f"RCP-PAYOUT-DISP-{rental_disp_res.pk}",
                )

        # ---------------------------------------------------------------------
        # 9. Summary and Credentials Output
        # ---------------------------------------------------------------------
        total_users = User.objects.count()
        total_categories = Category.objects.count()
        total_items = Item.objects.count()
        total_rentals = Rental.objects.count()
        total_payments = Payment.objects.count()
        total_reviews = Review.objects.count()
        total_conversations = Conversation.objects.count()
        total_disputes = Dispute.objects.count()

        self.stdout.write(self.style.SUCCESS("\n✅ Demo data seeded successfully!"))
        self.stdout.write(
            f"📊 Statistics: {total_users} Users | {total_categories} Categories | {total_items} Items | "
            f"{total_rentals} Rentals | {total_payments} Payments | {total_reviews} Reviews | "
            f"{total_conversations} Conversations | {total_disputes} Disputes"
        )

        credentials_box = f"""
======================================================================
🔑 DEMO CREDENTIALS (همه رمزها یکسان است: {demo_password})
======================================================================
1. مدیر سامانه (Admin):
   - نام کاربری: admin
   - رمز عبور:   {demo_password}
   - ایمیل:       admin@amanatyab.ir
   - نقش:        مدیر سیستم (دسترسی به داشبورد و داوری اختلافات)

2. کاربران عادی نمونه (Owner / Renter):
   - reza   / {demo_password}  (تهران - مالک دریل، کارواش، سنباده)
   - sara   / {demo_password}  (تهران - مالک تراز لیزری، دوربین، اجاق)
   - ali    / {demo_password}  (اصفهان - مالک چادر، فارسی‌بر، اره زنجیری)
   - maryam / {demo_password}  (اصفهان - مالک شمشادزن، بخارشوی، چمن‌زن)
   - mehdi  / {demo_password}  (تبریز - مالک اینورتر جوش، چکش تخریب، میکسر)
   - neda   / {demo_password}  (تبریز - مالک کیسه خواب، علف‌زن، کوله)
   - babak  / {demo_password}  (شیراز - مالک سه‌پایه، ایمپکت درایور، پولیشر)
   - zahra  / {demo_password}  (مشهد - مالک کیت نور، فرز آهنگری، لنز سیگما)
======================================================================
"""
        self.stdout.write(credentials_box)
