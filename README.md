# ⚔️ Game of Thrones: Telegram Battle

**Ko'p foydalanuvchili strategik o'yin — Telegram bot orqali**

---

## 📁 Loyiha strukturasi

```
got_bot/
├── main.py                  # Bot ishga tushirish
├── config.py                # Sozlamalar va konstantalar
├── requirements.txt         # Python kutubxonalar
├── Dockerfile
├── docker-compose.yml
├── .env.example             # Muhit o'zgaruvchilari namunasi
│
├── database/
│   ├── db.py               # DB ulanish va jadvallar yaratish
│   └── queries.py          # Barcha SQL so'rovlar
│
├── handlers/
│   ├── common.py           # /start, /menu, umumiy callback'lar
│   ├── admin.py            # Admin (Uch Ko'zli Qarg'a) paneli
│   ├── king.py             # Qirol paneli
│   ├── lord.py             # Lord paneli
│   └── member.py           # Oddiy a'zo paneli + Bozor
│
├── keyboards/
│   └── kb.py               # Barcha InlineKeyboard va ReplyKeyboard
│
└── middlewares/
    └── auth.py             # Foydalanuvchini avtomatik ro'yxatdan o'tkazish
```

---

## 🚀 O'rnatish va ishga tushirish

### 1. Bot yaratish
[@BotFather](https://t.me/BotFather) da yangi bot yarating va TOKEN oling.

### 2. .env faylini sozlash
```bash
cp .env.example .env
# .env faylini tahrirlang:
# BOT_TOKEN=your_token
# ADMIN_IDS=your_telegram_id
# DATABASE_URL=postgresql://...
```

### 3. Docker bilan (tavsiya etiladi)
```bash
docker-compose up -d
```

### 4. Qo'lda ishga tushirish
```bash
pip install -r requirements.txt
python main.py
```

---

## 🎮 O'yin Bosqichlari

### Admin sifatida boshlash:
1. `/admin` buyrug'ini yuboring
2. **"Qirolliklarni yaratish"** → 7 ta xonadon avtomatik yaratiladi
3. **"Vassal oila qo'shish"** → Har bir qirollikka vassal oilalar qo'shing
4. **"Qirol tayinlash"** → Har bir qirollikka Qirol belgilang

### Foydalanuvchilar oqimi:
```
/start bosadi
    ↓
Queue tizimi tekshiradi
    ↓
Phase 1: 7 Qirollik × 7 kishi (49 kishi)
    ↓
Phase 2: Vassallar × 4 kishi (Lord saylovi uchun)
    ↓
Phase 3: Vassallar 7 tagacha to'ldiriladi
```

### Rol saylovi:
- Admin → **Qirollarni tayinlaydi** (foydalanuvchi ID orqali)
- A'zolar → **Lordni saylay**di (4+ kishi bo'lganda ovoz berish)

---

## 👥 Rol imkoniyatlari

| Rol | Imkoniyatlar |
|-----|-------------|
| 🔮 Admin | Qirollik yaratish, Qirol tayinlash, Vassal qo'shish, Xronika |
| 👑 Qirol | Farmon, Resurs talabi, Jazo, Diplomatiya (Urush/Ittifoq) |
| 🛡️ Lord | Buyruq bajarish/rad etish, Saylov, Panoh so'rash |
| ⚔️ Member | Kunlik farm, Ovoz berish, Xronika, Iron Bank |

---

## 💰 Resurslar tizimi

| Resurs | Qo'llanilishi |
|--------|---------------|
| Oltin | Asosiy valyuta, kunlik farm (+1/kun), bozor |
| Qo'shin | 100 oltin = 100 qo'shin (kuniga 1 marta) |
| Artefaktlar | Maxsus qobiliyatlar uchun |

### Iron Bank narxlari:
- 🗡️ Valeriya Po'lati: **70 oltin**
- 🔥 Yovvoyi Olov: **65 oltin**
- 🐉 Ajdar A (kuchli): **150 oltin**
- 🐉 Ajdar B (o'rta): **100 oltin**
- 🐉 Ajdar C (kichik): **60 oltin**

---

## ⚙️ Sozlash (`config.py`)

```python
MAX_KINGDOM_MEMBERS = 7      # Har bir qirollikdagi max a'zo
MIN_VASSAL_MEMBERS = 4       # Lord saylashi uchun minimal a'zo
DAILY_FARM_GOLD = 1          # Kunlik farm miqdori
ASSASSINATION_SUCCESS_THRESHOLD = 70  # Suiqasd muvaffaqiyati (%)
PUNISHMENT_SOLDIER_COST = 10  # Jazo uchun qo'shin soni
```

---

## 🗄️ Ma'lumotlar bazasi jadvallari

| Jadval | Maqsad |
|--------|--------|
| `kingdoms` | 7 Qirollik ma'lumotlari |
| `vassals` | Vassal oilalar |
| `users` | Barcha foydalanuvchilar |
| `chronicles` | Voqealar tarixi |
| `diplomacy` | Urush/Ittifoq takliflari |
| `elections` | Lord saylov natijalari |
| `artifacts` | Sotib olingan artefaktlar |
| `queue_state` | Foydalanuvchi navbat holati |

---

## 📌 Muhim eslatmalar

- **Bot hech qachon avtomatik Qirol yoki Lord tayinlamaydi**
- Har bir foydalanuvchi `/start` bosganda avtomatik ro'yxatdan o'tadi
- Suiqasd tizimi: tasodifiy 1-100 son, 70+ = muvaffaqiyat
- Xronikani hamma ko'rishi mumkin
- Lord saylovi ko'pchilik ovozi bilan tugaydi (n/2 + 1)
