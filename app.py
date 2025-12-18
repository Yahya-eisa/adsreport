import streamlit as st
import pandas as pd
import re
from difflib import SequenceMatcher
import io

st.set_page_config(page_title="دمج الإعلانات والمنتجات", page_icon="📊", layout="wide")

st.title("🎯 دمج الإعلانات مع المنتجات")
st.markdown("---")

# دالة تنظيف أسماء الإعلانات
def normalize_campaign_name(name):
    name = str(name)
    name = name.replace('‎', '').replace('‏', '')
    name = re.sub(r'\s+\d{1,2}[-/]\d{1,2}.*$', '', name)
    name = re.sub(r'\s+\d{1,2}-\d{1,2}$', '', name)
    name = re.sub(r'\s*-?\s*Copy\s*\d*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*Copy\s+\d+\s+of\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^scale\s+of\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^New\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+[-–—]\s+', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()

# دالة مطابقة المنتجات
def find_product_match(campaign_name, products_list, threshold=60):
    if not campaign_name or pd.isna(campaign_name):
        return None, 0
    
    campaign_lower = str(campaign_name).lower()
    best_match = None
    best_score = threshold
    
    for product in products_list:
        product_lower = str(product).lower()
        similarity = SequenceMatcher(None, campaign_lower, product_lower).ratio() * 100
        campaign_words = [w for w in campaign_lower.split() if len(w) > 3]
        for word in campaign_words:
            if word in product_lower:
                similarity += 20
        
        if similarity > best_score:
            best_score = similarity
            best_match = product
    
    return best_match, best_score

# رفع الملفات
col1, col2 = st.columns(2)

with col1:
    st.subheader("📁 ملف الإعلانات")
    campaigns_file = st.file_uploader("ارفع ملف Excel للإعلانات", type=['xlsx', 'xls'], key="campaigns")

with col2:
    st.subheader("📦 ملف المنتجات")
    products_file = st.file_uploader("ارفع ملف Excel للمنتجات", type=['xlsx', 'xls'], key="products")

if campaigns_file and products_file:
    # تحميل البيانات
    with st.spinner("جاري تحميل البيانات..."):
        campaigns_df = pd.read_excel(campaigns_file)
        products_df = pd.read_excel(products_file)
    
    st.success(f"✅ تم تحميل {len(campaigns_df)} إعلان و {len(products_df)} منتج")
    
    # معالجة البيانات
    if st.button("🚀 ابدأ المعالجة", type="primary"):
        with st.spinner("جاري معالجة البيانات..."):
            # تنظيف البيانات
            campaigns_df['normalized_name'] = campaigns_df['Campaign name'].apply(normalize_campaign_name)
            campaigns_df['Amount spent (EGP)'] = pd.to_numeric(campaigns_df['Amount spent (EGP)'], errors='coerce')
            campaigns_df['Results'] = pd.to_numeric(campaigns_df['Results'], errors='coerce')
            
            # تجميع الإعلانات
            campaigns_grouped = campaigns_df.groupby('normalized_name').agg({
                'Amount spent (EGP)': 'sum',
                'Results': 'sum',
                'Campaign name': 'count'
            }).reset_index()
            
            campaigns_grouped.columns = ['campaign_name', 'total_spent', 'total_results', 'ads_count']
            campaigns_grouped = campaigns_grouped.sort_values('total_spent', ascending=False)
            
            # مطابقة المنتجات
            products_list = products_df['اسم المنتج'].tolist()
            campaigns_grouped['matched_product'] = None
            campaigns_grouped['match_score'] = 0
            
            progress_bar = st.progress(0)
            for idx, row in campaigns_grouped.iterrows():
                product, score = find_product_match(row['campaign_name'], products_list)
                campaigns_grouped.at[idx, 'matched_product'] = product
                campaigns_grouped.at[idx, 'match_score'] = score
                progress_bar.progress((idx + 1) / len(campaigns_grouped))
            
            # فصل المطابق وغير المطابق
            matched = campaigns_grouped[campaigns_grouped['match_score'] >= 60].copy()
            unmatched = campaigns_grouped[campaigns_grouped['match_score'] < 60].copy()
            
            st.success(f"✅ تم مطابقة {len(matched)} إعلان | ⚠️ {len(unmatched)} إعلان يحتاج مراجعة")
            
            # عرض الإعلانات غير المطابقة
            if len(unmatched) > 0:
                st.warning("### ⚠️ إعلانات تحتاج مطابقة يدوية:")
                st.dataframe(
                    unmatched[['campaign_name', 'total_spent', 'ads_count']].head(20),
                    use_container_width=True
                )
                
                st.info("💡 يمكنك إضافة المطابقة اليدوية في الكود ثم إعادة التشغيل")
            
            # دمج مع بيانات المنتجات
            final_df = campaigns_grouped.merge(
                products_df,
                left_on='matched_product',
                right_on='اسم المنتج',
                how='left'
            )
            
            # تجهيز البيانات النهائية
            final_df = final_df[[
                'campaign_name',
                'ads_count',
                'total_spent',
                'matched_product',
                'إجمالي الأوردرات',
                'تم التسليم',
                'ملغي',
            ]].copy()
            
            final_df.columns = [
                'اسم الإعلان',
                'عدد الإعلانات',
                'إجمالي الصرف (جنيه)',
                'اسم المنتج',
                'إجمالي الأوردرات',
                'تم التسليم',
                'المرتجع'
            ]
            
            # حساب تكلفة الأوردر المسلم
            final_df['تكلفة الأوردر المسلم'] = final_df.apply(
                lambda row: row['إجمالي الصرف (جنيه)'] / row['تم التسليم'] 
                if pd.notna(row['تم التسليم']) and row['تم التسليم'] > 0 
                else None,
                axis=1
            )
            
            final_df = final_df.sort_values('إجمالي الصرف (جنيه)', ascending=False)
            final_df = final_df.fillna({
                'إجمالي الأوردرات': 0,
                'تم التسليم': 0,
                'المرتجع': 0
            })
            
            # عرض الإحصائيات
            st.markdown("---")
            st.subheader("📊 ملخص النتائج")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("إجمالي الإعلانات", len(final_df))
            with col2:
                st.metric("إجمالي الإنفاق", f"{final_df['إجمالي الصرف (جنيه)'].sum():,.0f} EGP")
            with col3:
                st.metric("إجمالي الأوردرات", f"{final_df['إجمالي الأوردرات'].sum():.0f}")
            with col4:
                st.metric("تم التسليم", f"{final_df['تم التسليم'].sum():.0f}")
            
            # عرض الجدول
            st.markdown("---")
            st.subheader("📋 الجدول النهائي")
            st.dataframe(final_df, use_container_width=True)
            
            # تحميل الملف
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False, sheet_name='التقرير النهائي')
            
            st.download_button(
                label="⬇️ تحميل التقرير النهائي (Excel)",
                data=output.getvalue(),
                file_name="تقرير_الاعلانات_والمنتجات_النهائي.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    st.info("👆 من فضلك ارفع ملفي Excel (الإعلانات والمنتجات) للبدء")

# تذييل
st.markdown("---")
st.markdown("Made with ❤️ for Ali Deal Kuwait")
