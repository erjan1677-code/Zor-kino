import asyncio
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

# ==================== SOZLAMALAR ====================
ADMIN_ID = 5881411460  # Admin ID
BOT_TOKEN = "7359346098:AAHbIKAFWXCR8vDWu2_xxMQ8qKFcQRTPu5M"  # Botning tokeni
REQUIRED_CHANNELS = ["@zorkino_channel"]  # Majburiy kanallar

# Logging sozlamasi
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== BAZALAR ====================
def init_db():
    """Database inicialization"""
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    
    # Foydalanuvchilar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        status TEXT DEFAULT 'oddiy',
        registration_date TEXT,
        referrer_id INTEGER,
        referral_bonus INTEGER DEFAULT 0,
        daily_bonus_date TEXT
    )''')
    
    # Kinolar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS movies (
        movie_id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        title TEXT,
        description TEXT,
        category TEXT,
        video_file_id TEXT,
        rating REAL DEFAULT 0,
        views INTEGER DEFAULT 0,
        created_date TEXT
    )''')
    
    # Rating jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS ratings (
        user_id INTEGER,
        movie_id INTEGER,
        rating INTEGER,
        UNIQUE(user_id, movie_id)
    )''')
    
    conn.commit()
    conn.close()

# ==================== HOLAT MASHINALARI ====================
class MovieManagement(StatesGroup):
    waiting_for_code = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_category = State()
    waiting_for_video = State()
    waiting_for_delete_code = State()

# ==================== ASOSIY FUNKTSIYALAR ====================

def get_user_status(user_id):
    """Foydalanuvchining statusini olish"""
    conn = sqlite3.connect('kino_bot.db')
    c = conn.cursor()
    c.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def register_user(user_id, username, referrer_id=None):
    """Foydalanuvchini ro'yxatdan o'tkazish"""
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        now = datetime.now().isoformat()
        
        c.execute('''INSERT OR IGNORE INTO users 
                    (user_id, username, registration_date, referrer_id) 
                    VALUES (?, ?, ?, ?)''',
                 (user_id, username, now, referrer_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ro'yxatdan o'tkazish xatosi: {e}")
        return False

async def check_subscription(bot, user_id):
    """Kanalga obuna tekshirish"""
    try:
        for channel in REQUIRED_CHANNELS:
            member = await bot.get_chat_member(channel, user_id)
            if member.status == 'left':
                return False
        return True
    except Exception as e:
        logger.error(f"Obuna tekshirish xatosi: {e}")
        return False

def get_main_menu():
    """Asosiy menyu"""
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Kino qidirish")],
            [KeyboardButton(text="⭐ Eng mashhur"), KeyboardButton(text="🆕 Yangilar")],
            [KeyboardButton(text="👤 Profilim"), KeyboardButton(text="ℹ️ Ma'lumot")]
        ],
        resize_keyboard=True
    )
    return markup

def get_admin_menu():
    """Admin menyu"""
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Kino qo'shish"), KeyboardButton(text="❌ Kino o'chirish")],
            [KeyboardButton(text="👥 Foydalanuvchilar"), KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="👑 VIP berish"), KeyboardButton(text="📢 Broadcast")],
            [KeyboardButton(text="⚙️ Kanallar"), KeyboardButton(text="🏠 Asosiyga qaytish")]
        ],
        resize_keyboard=True
    )
    return markup

# ==================== KINO BAZASI ====================

def add_movie(code, title, description, category):
    """Kinoni bazaga qo'shish"""
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        now = datetime.now().isoformat()
        
        c.execute('''INSERT INTO movies (code, title, description, category, created_date)
                    VALUES (?, ?, ?, ?, ?)''',
                 (code, title, description, category, now))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Kino qo'shishda xato: {e}")
        return False

def get_movie_by_code(code):
    """Kodga ko'ra kinoni topish"""
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        c.execute("SELECT movie_id, code, title, description, category, rating, views FROM movies WHERE code = ?", (code,))
        result = c.fetchone()
        
        if result:
            c.execute("UPDATE movies SET views = views + 1 WHERE code = ?", (code,))
            conn.commit()
        
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Kino qidirish xatosi: {e}")
        return None

def delete_movie(code):
    """Kinoni o'chirish"""
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        c.execute("DELETE FROM movies WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Kino o'chirishda xato: {e}")
        return False

def get_popular_movies(limit=5):
    """Eng mashhur kinolarni olish"""
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        c.execute("SELECT code, title, rating, views FROM movies ORDER BY views DESC LIMIT ?", (limit,))
        results = c.fetchall()
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Eng mashhur kinolarni olishda xato: {e}")
        return []

def get_new_movies(limit=5):
    """Yangi kinolarni olish"""
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        c.execute("SELECT code, title, description, created_date FROM movies ORDER BY created_date DESC LIMIT ?", (limit,))
        results = c.fetchall()
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Yangi kinolarni olishda xato: {e}")
        return []

def get_user_count():
    """Foydalanuvchilar sonini olish"""
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Foydalanuvchilar sonini olishda xato: {e}")
        return 0

def set_user_status(user_id, status):
    """Foydalanuvchi statusini belgilash"""
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Status belgilashda xato: {e}")
        return False

# ==================== BOT KOMANDALAR ====================

async def start(message: types.Message, state: FSMContext):
    """Start komandasi"""
    user_id = message.from_user.id
    username = message.from_user.username or "No username"
    
    # Foydalanuvchini ro'yxatdan o'tkazish
    register_user(user_id, username)
    
    # Obuna tekshirish
    is_subscribed = await check_subscription(message.bot, user_id)
    
    if not is_subscribed:
        text = "🎬 <b>Salom! Kodli Kino Botga xush kelibsiz!</b>\n\n"
        text += "📺 Videolarni tomosha qilish uchun kanallarga obuna bo'lishingiz kerak:\n\n"
        
        for channel in REQUIRED_CHANNELS:
            text += f"✅ {channel}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga o'ting", url=f"https://t.me/{REQUIRED_CHANNELS[0].replace('@', '')}")],
            [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    # Obuna qilingan bo'lsa
    text = "🎬 <b>Salom! Kodli Kino Botga xush kelibsiz!</b>\n\n"
    text += "🎥 Kino kodini yozing va video olib chiqing!\n\n"
    text += "<i>Masalan: 101, 202, 303</i>\n\n"
    text += "💎 VIP va PREMIUM foydalanuvchilar reklamasiz foydalanadi!"
    
    await message.answer(text, reply_markup=get_main_menu(), parse_mode="HTML")
    await state.clear()

async def search_movie(message: types.Message, state: FSMContext):
    """Kino qidiruv"""
    user_id = message.from_user.id
    
    # Obuna tekshirish
    is_subscribed = await check_subscription(message.bot, user_id)
    if not is_subscribed:
        await message.answer("❌ Kanalga obuna bo'lmagansiz!")
        return
    
    # Foydalanuvchi kodini yozishini kutish
    await message.answer("📝 <b>Kino kodini kiriting:</b>\n\nMasalan: <code>101</code>", parse_mode="HTML")
    await state.set_state(StateFilter())

async def handle_movie_code(message: types.Message, state: FSMContext):
    """Kino kodini qayta ishlash"""
    user_id = message.from_user.id
    code = message.text.strip()
    
    # Obuna tekshirish
    is_subscribed = await check_subscription(message.bot, user_id)
    if not is_subscribed:
        await message.answer("❌ Avval kanalga obuna bo'ling!")
        return
    
    movie = get_movie_by_code(code)
    
    if movie:
        movie_id, code, title, description, category, rating, views = movie
        
        text = f"🎬 <b>{title}</b>\n\n"
        text += f"📖 <i>{description}</i>\n\n"
        text += f"📂 Kategoriya: {category}\n"
        text += f"⭐ Reyting: {rating:.1f}/5\n"
        text += f"👁 Ko'rildi: {views} marta\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Baholash", callback_data=f"rate_{movie_id}")]
        ])
        
        # Status tekshirish
        status = get_user_status(user_id)
        
        if status in ['vip', 'premium']:
            text += "\n✨ <i>VIP/PREMIUM foydalanuvchi sifatida reklamasiz!</i>"
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer("❌ <b>Kino topilmadi!</b>\n\n" + 
                           "Iltimos, to'g'ri kod kiriting yoki /start bosing.",
                           parse_mode="HTML")

async def show_popular(message: types.Message):
    """Eng mashhur kinolar"""
    movies = get_popular_movies(5)
    
    if not movies:
        await message.answer("📺 Hali kinolar qo'shilmagan!")
        return
    
    text = "🌟 <b>ENG MASHHUR KINOLAR</b>\n\n"
    
    for code, title, rating, views in movies:
        text += f"📺 <b>{title}</b>\n"
        text += f"   ⭐ {rating:.1f}/5 • 👁 {views} marta\n"
        text += f"   <code>Kod: {code}</code>\n\n"
    
    text += "💡 Kino kodini yozing va video olib chiqing!"
    await message.answer(text, parse_mode="HTML")

async def show_new_movies(message: types.Message):
    """Yangi kinolar"""
    movies = get_new_movies(5)
    
    if not movies:
        await message.answer("📺 Hali kinolar qo'shilmagan!")
        return
    
    text = "🆕 <b>YANGI QOSHILGAN KINOLAR</b>\n\n"
    
    for code, title, description, created_date in movies:
        text += f"📺 <b>{title}</b>\n"
        text += f"   {description}\n"
        text += f"   <code>Kod: {code}</code>\n\n"
    
    text += "💡 Kino kodini yozing!"
    await message.answer(text, parse_mode="HTML")

async def show_profile(message: types.Message):
    """Foydalanuvchi profili"""
    user_id = message.from_user.id
    
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        c.execute("SELECT status, registration_date FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        
        if user:
            status, reg_date = user
            status_emoji = {"oddiy": "👤", "vip": "👑", "premium": "💎"}.get(status, "👤")
            
            text = f"{status_emoji} <b>MENING PROFILIM</b>\n\n"
            text += f"👤 Foydalanuvchi ID: <code>{user_id}</code>\n"
            text += f"📊 Status: {status.upper()}\n"
            text += f"📅 Ro'yxatdan o'tish: {reg_date[:10]}\n\n"
            text += "💎 VIP olish uchun admin bilan bog'laning!"
        else:
            text = "❌ Profil topilmadi!"
        
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Profil ko'rsatishda xato: {e}")
        await message.answer("❌ Xato yuz berdi!")

async def show_info(message: types.Message):
    """Ma'lumot"""
    text = "ℹ️ <b>KODLi KINO BOT HAQIDA</b>\n\n"
    text += "🎬 Bot nomi: <b>Kodli Kino Bot</b>\n"
    text += "🌍 Til: <b>Uzbek</b>\n"
    text += "👨‍💻 Texnologiya: <b>Aiogram, Python, SQLite</b>\n\n"
    text += "<b>✨ Funksiyalar:</b>\n"
    text += "✅ Kino kodiga ko'ra qidirish\n"
    text += "✅ Eng mashhur va yangi kinolar\n"
    text += "✅ Baholash tizimi\n"
    text += "✅ VIP/PREMIUM status\n"
    text += "✅ Referal tizim\n"
    text += "✅ Admin panel\n\n"
    text += "📞 Muammosi bo'lsa: /help"
    
    await message.answer(text, parse_mode="HTML")

# ==================== ADMIN KOMANDALAR ====================

async def admin_menu(message: types.Message):
    """Admin menyu"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizga ruxsat yo'q!")
        return
    
    await message.answer("👑 <b>ADMIN PANEL</b>\n\n" +
                        "Quyidagi variantlardan birini tanlang:",
                        reply_markup=get_admin_menu(),
                        parse_mode="HTML")

async def add_movie_start(message: types.Message, state: FSMContext):
    """Kino qo'shishni boshlash"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizga ruxsat yo'q!")
        return
    
    await message.answer("📝 <b>Kino kodini kiriting:</b>\n\nMasalan: <code>101</code>",
                        parse_mode="HTML")
    await state.set_state(MovieManagement.waiting_for_code)

async def get_code(message: types.Message, state: FSMContext):
    """Kino kodini olish"""
    await state.update_data(code=message.text.strip())
    await message.answer("📛 <b>Kino nomini kiriting:</b>\n\nMasalan: <i>Titanic</i>",
                        parse_mode="HTML")
    await state.set_state(MovieManagement.waiting_for_title)

async def get_title(message: types.Message, state: FSMContext):
    """Kino nomini olish"""
    await state.update_data(title=message.text.strip())
    await message.answer("📖 <b>Kino tavsifini kiriting:</b>",
                        parse_mode="HTML")
    await state.set_state(MovieManagement.waiting_for_description)

async def get_description(message: types.Message, state: FSMContext):
    """Tavsifni olish"""
    await state.update_data(description=message.text.strip())
    await message.answer("📂 <b>Kategoriyani kiriting:</b>\n\nMasalan: <i>Drama, Komediya, Aksiyon</i>",
                        parse_mode="HTML")
    await state.set_state(MovieManagement.waiting_for_category)

async def get_category(message: types.Message, state: FSMContext):
    """Kategoriyani olish"""
    await state.update_data(category=message.text.strip())
    await message.answer("🎥 <b>Endi videoni yuboring:</b>\n\nVideo faylini yuklang.",
                        parse_mode="HTML")
    await state.set_state(MovieManagement.waiting_for_video)

async def get_video(message: types.Message, state: FSMContext):
    """Videoni olish va bazaga qo'shish"""
    if not message.video and not message.document:
        await message.answer("❌ Video kerak!")
        return
    
    data = await state.get_data()
    
    video_id = message.video.file_id if message.video else message.document.file_id
    
    if add_movie(data['code'], data['title'], data['description'], data['category']):
        # Video file_id ni bazaga saqlash
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        c.execute("UPDATE movies SET video_file_id = ? WHERE code = ?",
                 (video_id, data['code']))
        conn.commit()
        conn.close()
        
        await message.answer("✅ <b>Kino muvaffaqiyatli qo'shildi!</b>\n\n" +
                            f"📺 Nom: {data['title']}\n" +
                            f"🔐 Kod: {data['code']}",
                            parse_mode="HTML")
    else:
        await message.answer("❌ Xato! Shunaqa kod mavjud yoki boshqa xato!")
    
    await state.clear()

async def delete_movie_start(message: types.Message, state: FSMContext):
    """Kinoni o'chirishni boshlash"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizga ruxsat yo'q!")
        return
    
    await message.answer("🔍 <b>O'chiriladigan kino kodini kiriting:</b>",
                        parse_mode="HTML")
    await state.set_state(MovieManagement.waiting_for_delete_code)

async def delete_movie_execute(message: types.Message, state: FSMContext):
    """Kinoni o'chirish"""
    code = message.text.strip()
    
    if delete_movie(code):
        await message.answer(f"✅ <b>Kod: {code} o'chirildi!</b>", parse_mode="HTML")
    else:
        await message.answer("❌ Shunaqa kod topilmadi!", parse_mode="HTML")
    
    await state.clear()

async def show_users_count(message: types.Message):
    """Foydalanuvchilar sonini ko'rsatish"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizga ruxsat yo'q!")
        return
    
    count = get_user_count()
    await message.answer(f"👥 <b>Jami foydalanuvchilar: {count}</b>", parse_mode="HTML")

async def give_vip(message: types.Message):
    """VIP berish"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizga ruxsat yo'q!")
        return
    
    await message.answer("👑 <b>VIP berish uchun foydalanuvchi ID kiriting:</b>\n\n" +
                        "Yoki PREMIUM uchun 'premium' deb yozing.",
                        parse_mode="HTML")

async def broadcast_start(message: types.Message, state: FSMContext):
    """Broadcast boshlash"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizga ruxsat yo'q!")
        return
    
    await message.answer("📢 <b>Hamma userlarga yuborish uchun xabarni kiriting:</b>",
                        parse_mode="HTML")

async def statistics(message: types.Message):
    """Statistika"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizga ruxsat yo'q!")
        return
    
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM movies")
        movies_count = c.fetchone()[0]
        
        c.execute("SELECT SUM(views) FROM movies")
        total_views = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM users WHERE status = 'vip'")
        vip_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users WHERE status = 'premium'")
        premium_count = c.fetchone()[0]
        
        conn.close()
        
        text = "📊 <b>STATISTIKA</b>\n\n"
        text += f"👥 Foydalanuvchilar: {users_count}\n"
        text += f"🎬 Kinolar: {movies_count}\n"
        text += f"👁 Umumiy ko'rildi: {total_views}\n"
        text += f"👑 VIP foydalanuvchilar: {vip_count}\n"
        text += f"💎 PREMIUM foydalanuvchilar: {premium_count}\n"
        
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Statistika ko'rsatishda xato: {e}")
        await message.answer("❌ Xato!")

# ==================== CALLBACK QUERY HANDLER ====================

async def rate_movie(callback: types.CallbackQuery):
    """Kinoni baholash"""
    data = callback.data.split("_")
    movie_id = int(data[1])
    
    # Rating tugmalari
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1⭐", callback_data=f"rating_{movie_id}_1"),
         InlineKeyboardButton(text="2⭐", callback_data=f"rating_{movie_id}_2"),
         InlineKeyboardButton(text="3⭐", callback_data=f"rating_{movie_id}_3")],
        [InlineKeyboardButton(text="4⭐", callback_data=f"rating_{movie_id}_4"),
         InlineKeyboardButton(text="5⭐", callback_data=f"rating_{movie_id}_5")]
    ])
    
    await callback.message.edit_text("⭐ <b>Kinoni baholang:</b>",
                                     reply_markup=keyboard,
                                     parse_mode="HTML")

async def save_rating(callback: types.CallbackQuery):
    """Baholashni saqlash"""
    user_id = callback.from_user.id
    data = callback.data.split("_")
    movie_id = int(data[1])
    rating = int(data[2])
    
    try:
        conn = sqlite3.connect('kino_bot.db')
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO ratings (user_id, movie_id, rating)
                    VALUES (?, ?, ?)''', (user_id, movie_id, rating))
        
        # O'rtacha baholashni hisoblash
        c.execute("SELECT AVG(rating) FROM ratings WHERE movie_id = ?", (movie_id,))
        avg_rating = c.fetchone()[0]
        
        c.execute("UPDATE movies SET rating = ? WHERE movie_id = ?", (avg_rating, movie_id))
        
        conn.commit()
        conn.close()
        
        await callback.answer(f"✅ {rating} ⭐ baholama tabriklaymiz!", show_alert=True)
    except Exception as e:
        logger.error(f"Baholashni saqlashda xato: {e}")
        await callback.answer("❌ Xato!", show_alert=True)

async def check_sub(callback: types.CallbackQuery):
    """Obunani tekshirish"""
    user_id = callback.from_user.id
    is_subscribed = await check_subscription(callback.bot, user_id)
    
    if is_subscribed:
        await callback.answer("✅ Obuna tekshirildi! Startni bosing: /start", show_alert=True)
    else:
        await callback.answer("❌ Hali kanalga obuna bo'lmagansiz!", show_alert=True)

# ==================== BOT SOZLAMASI ====================

async def main():
    """Bot ishga tushirish"""
    # Database sozlash
    init_db()
    
    # Bot va Dispatcher sozlash
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Ro'yxat
    dp.message.register(start, Command("start"))
    dp.message.register(admin_menu, Command("admin"))
    
    # Text xabarlar
    dp.message.register(search_movie, lambda msg: msg.text == "🎬 Kino qidirish")
    dp.message.register(show_popular, lambda msg: msg.text == "⭐ Eng mashhur")
    dp.message.register(show_new_movies, lambda msg: msg.text == "🆕 Yangilar")
    dp.message.register(show_profile, lambda msg: msg.text == "👤 Profilim")
    dp.message.register(show_info, lambda msg: msg.text == "ℹ️ Ma'lumot")
    
    # Admin komandalar
    dp.message.register(add_movie_start, lambda msg: msg.text == "➕ Kino qo'shish")
    dp.message.register(delete_movie_start, lambda msg: msg.text == "❌ Kino o'chirish")
    dp.message.register(show_users_count, lambda msg: msg.text == "👥 Foydalanuvchilar")
    dp.message.register(statistics, lambda msg: msg.text == "📊 Statistika")
    dp.message.register(give_vip, lambda msg: msg.text == "👑 VIP berish")
    dp.message.register(broadcast_start, lambda msg: msg.text == "📢 Broadcast")
    
    # FSM states
    dp.message.register(get_code, MovieManagement.waiting_for_code)
    dp.message.register(get_title, MovieManagement.waiting_for_title)
    dp.message.register(get_description, MovieManagement.waiting_for_description)
    dp.message.register(get_category, MovieManagement.waiting_for_category)
    dp.message.register(get_video, MovieManagement.waiting_for_video)
    dp.message.register(delete_movie_execute, MovieManagement.waiting_for_delete_code)
    
    # Default handler - kino kodini o'qish
    dp.message.register(handle_movie_code, lambda msg: True)
    
    # Callback queries
    dp.callback_query.register(rate_movie, lambda cbq: cbq.data.startswith("rate_"))
    dp.callback_query.register(save_rating, lambda cbq: cbq.data.startswith("rating_"))
    dp.callback_query.register(check_sub, lambda cbq: cbq.data == "check_subscription")
    
    # Botni boshlash
    try:
        logger.info("Bot ishga tushmoqda...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
