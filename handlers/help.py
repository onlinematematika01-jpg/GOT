"""
Yordam va qo'llanma handler — /yordam, /qollanma
Boshqa fayllarga hech qanday o'zgarish kiritilmaydi
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

# ── Qo'llanma bo'limlari ──────────────────────────────────────────────────────

HELP_SECTIONS = {
    "help_about": {
        "title": "🌍 O'yin haqida",
        "text": (
            "⚔️ <b>TAXTLAR O'YINI</b>\n\n"
            "Bu Telegram orqali o'ynaladigan ko'p foydalanuvchili "
            "strategik o'yin. Siz real odamlar bilan birga:\n\n"
            "🏰 Qirolliklar qurasiz\n"
            "⚔️ Urushlar olib borasiz\n"
            "🤝 Diplomatiya qilasiz\n"
            "🗡️ Suiqasdlar uyushtirasiz\n"
            "👑 Taxtga intilasiz\n\n"
            "<i>Qish kelmoqda. Taxt uchun kurash shafqatsizdir...</i>"
        )
    },
    "help_roles": {
        "title": "👥 Rollar",
        "text": (
            "👥 <b>O'YIN ROLLARI</b>\n\n"
            "🔮 <b>Uch Ko'zli Qarg'a (Admin)</b>\n"
            "O'yin kuzatuvchisi va boshqaruvchisi. "
            "Qirolliklarni qo'shadi, Qirollarni tayinlaydi.\n\n"
            "👑 <b>Qirol</b>\n"
            "Yetti qirollikdan birining rahbari.\n"
            "Admin tomonidan tayinlanadi.\n"
            "• Vassallarga farmon beradi\n"
            "• Urush e'lon qiladi\n"
            "• Diplomatiya qiladi\n"
            "• Resurs talab qiladi\n\n"
            "🛡️ <b>Lord (Vassal)</b>\n"
            "Vassal oila boshlig'i. 4+ a'zo bo'lganda saylanadi.\n"
            "• Qirol buyruqlarini bajaradi yoki rad etadi\n"
            "• Oila resurslarini boshqaradi\n"
            "• Urushda qirolga yordam yuboradi\n\n"
            "⚔️ <b>Oddiy A'zo</b>\n"
            "Yangi o'yinchi.\n"
            "• Kunlik tanga ishlaydi\n"
            "• Ovoz beradi\n"
            "• Artefakt sotib oladi"
        )
    },
    "help_start": {
        "title": "🚀 Qanday boshlanadi",
        "text": (
            "🚀 <b>QANDAY BOSHLANADI</b>\n\n"
            "/start bosing → Bot sizni avtomatik joylashtiradi:\n\n"
            "<b>1-bosqich:</b> 7 ta Qirollikka 7 kishidan (49 kishi)\n"
            "<b>2-bosqich:</b> Vassal oilalarga 4 kishidan\n"
            "<b>3-bosqich:</b> Vassallar 7 kishigacha to'ldiriladi\n\n"
            "⚠️ <b>Qirol va Lord hech qachon avtomatik tayinlanmaydi!</b>\n\n"
            "⛏️ <b>Kunlik Farm</b>\n"
            "Har kuni 1 marta <b>⛏️ Kunlik Farm</b> bosing\n"
            "→ +1 oltin olasiz\n\n"
            "🗳️ <b>Lord Saylovi</b>\n"
            "Vassal oilada 4 ta a'zo to'plangach saylov boshlanadi.\n"
            "Ko'pchilik ovoz olgan kishi Lord bo'ladi."
        )
    },
    "help_bank": {
        "title": "🏦 Temir Bank",
        "text": (
            "🏦 <b>TEMIR BANK (IRON BANK)</b>\n\n"
            "🗡️ Valeriya Po'lati — <b>70💰</b>\n"
            "🔥 Yovvoyi Olov — <b>65💰</b>\n"
            "🐉 Ajdar A — <b>150💰</b> (100 askar kuchi)\n"
            "🐉 Ajdar B — <b>100💰</b> (50 askar kuchi)\n"
            "🐉 Ajdar C — <b>60💰</b> (25 askar kuchi)\n"
            "🦂 Chayon — <b>25💰</b> (Ajdarga qarshi)\n"
            "💱 Ayirboshlash — <b>100💰 → 100 askar</b>\n\n"
            "🦂 <b>Chayon effekti:</b>\n"
            "3 ta 🦂 → Ajdar A ni o'ldiradi\n"
            "2 ta 🦂 → Ajdar A ni 1 raund o'tkazib yuboradi\n"
            "1 ta 🦂 → Ajdar C ni o'ldiradi"
        )
    },
    "help_war": {
        "title": "⚔️ Urush tizimi",
        "text": (
            "⚔️ <b>URUSH TIZIMI</b>\n\n"
            "⏰ Faqat <b>20:00 — 00:00</b> oralig'ida e'lon qilinadi\n\n"
            "<b>Urush oqimi:</b>\n"
            "1️⃣ Qirol A urush e'lon qiladi\n"
            "2️⃣ B qirolligi barcha a'zolariga ogohlantirish\n"
            "3️⃣ 1 soat tayyorgarlik:\n"
            "   — Vassallar yordam yuboradi (💰 ⚔️ 🦂)\n"
            "   — Qirol ittifoqchilardan yordam so'raydi\n"
            "   — Qirol B: ✅ Qabul | 🏳️ Taslim | ⏳ Kutish\n\n"
            "<b>3 Raundli urush:</b>\n"
            "🥊 Raund 1: 🦂 Chayonlar → 🐉 Ajdarlarga\n"
            "🥊 Raund 2: 🐉 Ajdarlar + ⚔️ Askarlar\n"
            "🥊 Raund 3: Yakuniy jang\n\n"
            "<b>Natija:</b>\n"
            "🏆 G'olib → 50% resurs oladi\n"
            "💀 Yutqazgan Qirol → taxtdan tushadi\n\n"
            "<b>Taslim bo'lsa:</b>\n"
            "💰 50% resurs darhol o'tadi\n"
            "📅 Har shanba 10% tribute o'tadi\n"
            "👑 Qirol ag'dariladi"
        )
    },
    "help_assassination": {
        "title": "🗡️ Suiqasd tizimi",
        "text": (
            "🗡️ <b>SUIQASD TIZIMI</b>\n\n"
            "Faqat <b>Lord</b> va <b>Qirollarga</b> suiqasd mumkin!\n\n"
            "🛡️ Lord → <b>3 ta</b> suiqasddan keyin o'ladi\n"
            "👑 Qirol → <b>15 ta</b> umumiy YOKI <b>5 ta</b> Lord suiqasdi\n"
            "🐉 Targaryen → <b>3 ta</b> Qirol YOKI <b>50 ta</b> Lord suiqasdi\n\n"
            "❌ <b>Muvaffaqiyatsiz:</b>\n"
            "Xronikada <b>ismingiz oshkor</b> bo'ladi!\n\n"
            "✅ <b>Muvaffaqiyatli (o'lim):</b>\n"
            "Xronikada faqat <b>lavozim</b> ko'rinadi\n"
            "Suiqasdchi yashirin qoladi\n\n"
            "📊 Har bir nishonda hit progressi ko'rinadi"
        )
    },
    "help_tips": {
        "title": "💡 Maslahatlar",
        "text": (
            "💡 <b>FOYDALI MASLAHATLAR</b>\n\n"
            "1️⃣ <b>Kunlik farm</b> unutmang — oltin asosiy resurs\n\n"
            "2️⃣ <b>Vassal oilaga</b> qo'shiling — Lord bo'lish imkoniyati\n\n"
            "3️⃣ <b>Ajdar</b> sotib oling — urushda hal qiluvchi kuch\n\n"
            "4️⃣ <b>Chayon</b> — dushmanning ajdarini yo'q qilish uchun\n\n"
            "5️⃣ <b>Ittifoq</b> tuzing — yolg'iz qirollik zaif\n\n"
            "6️⃣ <b>Suiqasd</b> — kuchli dushmanni ichkaridan zaiflashtirish\n\n"
            "7️⃣ <b>Taslim bo'lmang</b> — urushda yutqazsangiz tribute yo'q!\n\n"
            "8️⃣ <b>Vassallar</b> — urushda qirolga yordam yuboring\n\n"
            "9️⃣ <b>Xronikani</b> kuzating — voqealardan xabardor bo'ling"
        )
    },
}


def help_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🌍 O'yin haqida", callback_data="help_about"))
    builder.row(InlineKeyboardButton(text="👥 Rollar", callback_data="help_roles"))
    builder.row(InlineKeyboardButton(text="🚀 Qanday boshlanadi", callback_data="help_start"))
    builder.row(InlineKeyboardButton(text="🏦 Temir Bank", callback_data="help_bank"))
    builder.row(InlineKeyboardButton(text="⚔️ Urush tizimi", callback_data="help_war"))
    builder.row(InlineKeyboardButton(text="🗡️ Suiqasd tizimi", callback_data="help_assassination"))
    builder.row(InlineKeyboardButton(text="💡 Maslahatlar", callback_data="help_tips"))
    return builder.as_markup()


def help_back_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Qo'llanmaga qaytish", callback_data="help_main"))
    return builder.as_markup()


# ── Handlerlar ────────────────────────────────────────────────────────────────

@router.message(Command("yordam"))
@router.message(Command("qollanma"))
@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 <b>O'YIN QO'LLANMASI</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=help_main_kb()
    )


@router.callback_query(F.data == "help_main")
async def cb_help_main(call: CallbackQuery):
    await call.message.edit_text(
        "📖 <b>O'YIN QO'LLANMASI</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=help_main_kb()
    )


@router.callback_query(F.data.startswith("help_"))
async def cb_help_section(call: CallbackQuery):
    section_key = call.data
    section = HELP_SECTIONS.get(section_key)
    if not section:
        await call.answer("❌ Bo'lim topilmadi!")
        return
    await call.message.edit_text(
        section["text"],
        reply_markup=help_back_kb()
    )
