
import pandas as pd
import re
import numpy as np
from difflib import SequenceMatcher

# ==================== الخطوة 1: تحميل الملفات ====================
print("=" * 80)
print("تحميل الملفات...")
print("=" * 80)

# ضع أسماء الملفات هنا
campaigns_file = 'ALIDEALKW-Campaigns-18-Nov-2022-18-Dec-2025.xlsx'
products_file = 'tqryr-lmntjt-2025-12-18.xlsx'

campaigns_df = pd.read_excel(campaigns_file)
products_df = pd.read_excel(products_file)

print(f"✅ تم تحميل {len(campaigns_df)} إعلان")
print(f"✅ تم تحميل {len(products_df)} منتج")


# ==================== الخطوة 2: دالة تنظيف أسماء الإعلانات ====================
def normalize_campaign_name(name):
    """إزالة التواريخ، Copy، وأي إضافات من اسم الإعلان"""
    name = str(name)

    # إزالة علامات RTL
    name = name.replace('‎', '').replace('‏', '')

    # إزالة التواريخ (مثل 12-15، 9/20، إلخ)
    name = re.sub(r'\s+\d{1,2}[-/]\d{1,2}.*$', '', name)
    name = re.sub(r'\s+\d{1,2}-\d{1,2}$', '', name)

    # إزالة "Copy" وتنويعاتها
    name = re.sub(r'\s*-?\s*Copy\s*\d*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*Copy\s+\d+\s+of\s+', '', name, flags=re.IGNORECASE)

    # إزالة "scale of"
    name = re.sub(r'^scale\s+of\s+', '', name, flags=re.IGNORECASE)

    # إزالة "New"
    name = re.sub(r'^New\s+', '', name, flags=re.IGNORECASE)

    # تنظيف المسافات والشرطات
    name = re.sub(r'\s+[-–—]\s+', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    name = name.strip()

    return name


# ==================== الخطوة 3: تنظيف وتجميع الإعلانات ====================
print("\n" + "=" * 80)
print("تنظيف وتجميع الإعلانات المتشابهة...")
print("=" * 80)

campaigns_df['normalized_name'] = campaigns_df['Campaign name'].apply(normalize_campaign_name)

# تحويل الأعمدة الرقمية
campaigns_df['Amount spent (EGP)'] = pd.to_numeric(campaigns_df['Amount spent (EGP)'], errors='coerce')
campaigns_df['Results'] = pd.to_numeric(campaigns_df['Results'], errors='coerce')

# تجميع الإعلانات المتشابهة
campaigns_grouped = campaigns_df.group
