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

# دالة استخراج اسم الإعلان والتكلفة من أي شيت
def extract_campaign_data(df, file_name):
    """استخراج اسم الإعلان والتكلفة بغض النظر عن اسم العمود"""
    
    # البحث عن عمود اسم الإعلان
    campaign_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if any(keyword in col_lower for keyword in ['campaign', 'اسم', 'name', 'حملة', 'إعلان']):
            campaign_col = col
            break
    
    # البحث عن عمود التكلفة/الصرف
    cost_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if any(keyword in col_lower for keyword in ['cost', 'spend', 'spent', 'amount', 'صرف', 'تكلفة', 'إنفاق']):
            cost_col = col
            break
    
    if not campaign_col or not cost_col:
        st.error(f"❌ لم يتم العثور على أعمدة الإعلان أو التكلفة في ملف: {file_name}")
        st.info(f"الأعمدة الموجودة: {', '.join(df.columns)}")
        return None
    
    # استخراج البيانات
    result_df = pd.DataFrame()
    result_df['campaign_name'] = df[campaign_col]
    result_df['cost'] = pd.to_numeric(df[cost_col], errors='coerce')
    result_df['source_file'] = file_name
    
    st.success(f"✅ تم استخراج البيانات من: {file_name} (عمود الإعلان: {campaign_col}, عمود التكلفة: {cost_col})")
    
    return result_df

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
st.subheader("📁 رفع ملفات الإعلانات")
st.info("💡 يمكنك رفع أكثر من ملف (Facebook, TikTok, Google Ads, إلخ)")
campaigns_files = st.file_uploader(
    "ارفع ملفات Excel للإعلانات (يمكن اختيار أكثر من ملف)",
    type=['xlsx', 'xls'],
    accept_multiple_files=True,
    key="campaigns"
)

st.markdown("---")

st.subheader("📦 رفع ملفات المنتجات")
products_files = st.file_uploader(
    "ارفع ملفات Excel للمنتجات (يمكن اختيار أكثر من ملف)",
    type=['xlsx', 'xls'],
    accept_multiple_files=True,
    key="products"
)

if campaigns_files and products_files:
    
    st.markdown("---")
    st.subheader("📊 الملفات المرفوعة")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**ملفات الإعلانات:**")
        for f in campaigns_files:
            st.write(f"• {f.name}")
    
    with col2:
        st.write("**ملفات المنتجات:**")
        for f in products_files:
            st.write(f"• {f.name}")
    
    # معالجة البيانات
    if st.button("🚀 ابدأ المعالجة", type="primary"):
        
        # ==================== معالجة ملفات الإعلانات ====================
        st.markdown("---")
        st.subheader("⚙️ معالجة ملفات الإعلانات...")
        
        all_campaigns = []
        
        for campaign_file in campaigns_files:
            with st.spinner(f"جاري معالجة {campaign_file.name}..."):
                df = pd.read_excel(campaign_file)
                extracted_data = extract_campaign_data(df, campaign_file.name)
                
                if extracted_data is not None:
                    all_campaigns.append(extracted_data)
        
        if not all_campaigns:
            st.error("❌ لم يتم استخراج أي بيانات من ملفات الإعلانات")
            st.stop()
        
        # دمج جميع ملفات الإعلانات
        campaigns_df = pd.concat(all_campaigns, ignore_index=True)
        st.success(f"✅ إجمالي الإعلانات من جميع الملفات: {len(campaigns_df)}")
        
        # ==================== معالجة ملفات المنتجات ====================
        st.markdown("---")
        st.subheader("⚙️ معالجة ملفات المنتجات...")
        
        all_products = []
        
        for product_file in products_files:
            with st.spinner(f"جاري معالجة {product_file.name}..."):
                df = pd.read_excel(product_file)
                
                # البحث عن عمود اسم المنتج
                product_name_col = None
                for col in df.columns:
                    col_lower = str(col).lower()
                    if any(keyword in col_lower for keyword in ['اسم', 'منتج', 'product', 'name', 'item']):
                        product_name_col = col
                        break
                
                if product_name_col:
                    all_products.append(df)
                    st.success(f"✅ تم تحميل {len(df)} منتج من: {product_file.name}")
                else:
                    st.error(f"❌ لم يتم العثور على عمود اسم المنتج في: {product_file.name}")
        
        if not all_products:
            st.error("❌ لم يتم تحميل أي منتجات")
            st.stop()
        
        # دمج جميع ملفات المنتجات
        products_df = pd.concat(all_products, ignore_index=True)
        
        # توحيد اسم العمود
        for col in products_df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in ['اسم', 'منتج', 'product', 'name']):
                products_df.rename(columns={col: 'اسم المنتج'}, inplace=True)
                break
        
        st.success(f"✅ إجمالي المنتجات من جميع الملفات: {len(products_df)}")
        
        # ==================== تنظيف وتجميع الإعلانات ====================
        st.markdown("---")
        st.subheader("🔄 تجميع الإعلانات المتشابهة...")
        
        with st.spinner("جاري التجميع..."):
            campaigns_df['normalized_name'] = campaigns_df['campaign_name'].apply(normalize_campaign_name)
            
            # تجميع الإعلانات المتشابهة
            campaigns_grouped = campaigns_df.groupby('normalized_name').agg({
                'cost': 'sum',
                'campaign_name': 'count',
                'source_file': lambda x: ', '.join(x.unique())
            }).reset_index()
            
            campaigns_grouped.columns = ['campaign_name', 'total_spent', 'ads_count', 'source_files']
            campaigns_grouped = campaigns_grouped.sort_values('total_spent', ascending=False)
            
            st.success(f"✅ تم دمج {len(campaigns_df)} إعلان إلى {len(campaigns_grouped)} مجموعة")
        
        # ==================== مطابقة الإعلانات مع المنتجات ====================
        st.markdown("---")
        st.subheader("🔗 مطابقة الإعلانات مع المنتجات...")
        
        products_list = products_df['اسم المنتج'].tolist()
        campaigns_grouped['matched_product'] = None
        campaigns_grouped['match_score'] = 0
        
        progress_bar = st.progress(0)
        for idx, row in campaigns_grouped.iterrows():
            product, score = find_product_match(row['campaign_name'], products_list)
            campaigns_grouped.at[idx, 'matched_product'] = product
            campaigns_grouped.at[idx, 'match_score'] = score
            progress_bar.progress((idx + 1) / len(campaigns_grouped))
        
        matched = campaigns_grouped[campaigns_grouped['match_score'] >= 60].copy()
        unmatched = campaigns_grouped[campaigns_grouped['match_score'] < 60].copy()
        
        st.success(f"✅ تم مطابقة {len(matched)} إعلان | ⚠️ {len(unmatched)} إعلان يحتاج مراجعة")
        
        # عرض الإعلانات غير المطابقة
        if len(unmatched) > 0:
            with st.expander("⚠️ عرض الإعلانات التي تحتاج مطابقة يدوية", expanded=False):
                st.dataframe(
                    unmatched[['campaign_name', 'total_spent', 'ads_count', 'source_files']].head(30),
                    use_container_width=True
                )
        
        # ==================== دمج البيانات النهائية ====================
        st.markdown("---")
        st.subheader("📋 إنشاء التقرير النهائي...")
        
        with st.spinner("جاري الدمج..."):
            # دمج مع بيانات المنتجات
            final_df = campaigns_grouped.merge(
                products_df,
                left_on='matched_product',
                right_on='اسم المنتج',
                how='left'
            )
            
            # تحديد الأعمدة المتاحة
            available_cols = ['campaign_name', 'ads_count', 'total_spent', 'matched_product', 'source_files']
            
            # إضافة أعمدة المنتجات إذا كانت موجودة
            if 'إجمالي الأوردرات' in final_df.columns:
                available_cols.append('إجمالي الأوردرات')
            if 'تم التسليم' in final_df.columns:
                available_cols.append('تم التسليم')
            if 'ملغي' in final_df.columns:
                available_cols.append('ملغي')
            
            final_df = final_df[available_cols].copy()
            
            # إعادة تسمية الأعمدة
            final_df.columns = [
                'اسم الإعلان',
                'عدد الإعلانات',
                'إجمالي الصرف (جنيه)',
                'اسم المنتج',
                'مصدر الملف'
            ] + [col for col in final_df.columns[5:]]
            
            # حساب تكلفة الأوردر المسلم إذا كانت البيانات متاحة
            if 'تم التسليم' in final_df.columns:
                final_df['تكلفة الأوردر المسلم'] = final_df.apply(
                    lambda row: row['إجمالي الصرف (جنيه)'] / row['تم التسليم'] 
                    if pd.notna(row['تم التسليم']) and row['تم التسليم'] > 0 
                    else None,
                    axis=1
                )
            
            final_df = final_df.sort_values('إجمالي الصرف (جنيه)', ascending=False)
        
        # ==================== عرض الإحصائيات ====================
        st.markdown("---")
        st.subheader("📊 ملخص النتائج")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("إجمالي الإعلانات", len(final_df))
        with col2:
            st.metric("إجمالي الإنفاق", f"{final_df['إجمالي الصرف (جنيه)'].sum():,.0f} EGP")
        with col3:
            if 'إجمالي الأوردرات' in final_df.columns:
                st.metric("إجمالي الأوردرات", f"{final_df['إجمالي الأوردرات'].sum():.0f}")
            else:
                st.metric("ملفات الإعلانات", len(campaigns_files))
        with col4:
            if 'تم التسليم' in final_df.columns:
                st.metric("تم التسليم", f"{final_df['تم التسليم'].sum():.0f}")
            else:
                st.metric("ملفات المنتجات", len(products_files))
        
        # ==================== عرض الجدول ====================
        st.markdown("---")
        st.subheader("📋 الجدول النهائي")
        
        # إضافة فلتر للبحث
        search_term = st.text_input("🔍 ابحث في التقرير", "")
        if search_term:
            filtered_df = final_df[
                final_df['اسم الإعلان'].str.contains(search_term, case=False, na=False) |
                final_df['اسم المنتج'].fillna('').str.contains(search_term, case=False)
            ]
            st.dataframe(filtered_df, use_container_width=True, height=400)
        else:
            st.dataframe(final_df, use_container_width=True, height=400)
        
        # ==================== تحميل الملف ====================
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            final_df.to_excel(writer, index=False, sheet_name='التقرير النهائي')
            
            # إضافة شيت للإعلانات غير المطابقة
            if len(unmatched) > 0:
                unmatched.to_excel(writer, index=False, sheet_name='إعلانات تحتاج مراجعة')
        
        st.download_button(
            label="⬇️ تحميل التقرير النهائي (Excel)",
            data=output.getvalue(),
            file_name="تقرير_الاعلانات_والمنتجات_النهائي.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

else:
    st.info("👆 من فضلك ارفع ملفات Excel (الإعلانات والمنتجات) للبدء")
    
    # معلومات مساعدة
    with st.expander("ℹ️ كيفية الاستخدام"):
        st.markdown("""
        ### 📝 التعليمات:
        
        1. **ارفع ملفات الإعلانات:**
           - يمكنك رفع أكثر من ملف (Facebook, TikTok, Google Ads)
           - يجب أن يحتوي كل ملف على:
             - عمود اسم الإعلان (Campaign name, اسم الحملة، إلخ)
             - عمود التكلفة (Cost, Amount spent, الصرف، إلخ)
        
        2. **ارفع ملفات المنتجات:**
           - يمكنك رفع أكثر من ملف
           - يجب أن يحتوي على:
             - عمود اسم المنتج
             - بيانات الطلبات (اختياري)
        
        3. **اضغط "ابدأ المعالجة"**
        
        4. **حمل التقرير النهائي**
        
        ### ✨ المميزات:
        - دمج تلقائي للإعلانات المتشابهة
        - دعم منصات إعلانية متعددة
        - مطابقة ذكية مع المنتجات
        - حساب تكلفة الأوردر المسلم
        """)

# تذييل
st.markdown("---")
st.markdown("Made with ❤️ | YAHYA EISSA")
