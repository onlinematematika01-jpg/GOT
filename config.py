"""
Configuration settings
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/got_battle")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []

# Game constants
MAX_KINGDOM_MEMBERS = 7          # Members per kingdom (phase 1)
MIN_VASSAL_MEMBERS = 4           # Min members to elect Lord
MAX_VASSAL_MEMBERS = 7           # Max members per vassal
KINGDOMS_COUNT = 7               # Number of kingdoms

# Resource constants
GOLD_TO_SOLDIER_RATE = 1        # 1 gold = 1 soldier
DAILY_FARM_GOLD = 1             # Gold per daily farm

# Artifact prices
VALYRIAN_STEEL_PRICE = 70
WILDFIRE_PRICE = 65
DRAGON_A_PRICE = 150
DRAGON_B_PRICE = 100
DRAGON_C_PRICE = 60

# Assassination system
ASSASSINATION_MIN = 1
ASSASSINATION_MAX = 100
ASSASSINATION_SUCCESS_THRESHOLD = 70  # 70+ = success

# Punishment cost
PUNISHMENT_SOLDIER_COST = 10

# Kingdom names
# Xronika kanali
CHRONICLE_CHANNEL_ID = -1003744070167

KINGDOM_NAMES = [
    "Stark",
    "Lannister",
    "Baratheon",
    "Targaryen",
    "Greyjoy",
    "Tyrell",
    "Martell"
]

KINGDOM_SIGILS = {
    "Stark": "🐺",
    "Lannister": "🦁",
    "Baratheon": "🦌",
    "Targaryen": "🐉",
    "Greyjoy": "🦑",
    "Tyrell": "🌹",
    "Martell": "☀️"
}
