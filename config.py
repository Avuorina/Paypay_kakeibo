# config.py
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Default categories
DEFAULT_CATEGORIES = [
    "食費", 
    "日用品", 
    "交通費", 
    "娯楽", 
    "交際費", 
    "住居費", 
    "医療・健康", 
    "衣服・美容", 
    "その他"
]

# Theme colors (Orange base)
THEME_COLOR_PRIMARY = "#FF7F50"      # Coral Orange
THEME_COLOR_SECONDARY = "#FFA07A"    # Light Salmon
THEME_COLOR_BACKGROUND = "#1E1E1E"   # Dark mode background
THEME_COLOR_TEXT = "#FAFAFA"         # Light text
THEME_COLOR_ACCENT = "#FF4500"       # Orange Red for alerts

# Application Constants
APP_NAME = "PayPay家計簿"
DB_NAME = "paypay_kakeibo.db"
