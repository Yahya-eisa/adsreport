import streamlit as st
import pandas as pd
import re
from difflib import SequenceMatcher
import io

st.set_page_config(page_title="تقرير الاعلانات", page_icon="📊", layout="wide")

st.title("🎯 تقرير الاعلانات")
st.markdown("---")

# Initialize session state
if 'campaigns_grouped' not in st.session_state:
    st.session_state.campaigns_grouped = None
if 'products_df' not in st.session_state:
    st.session_state.products_df = None
if 'unmatched' not in st.session_state:
    st.session_state.unmatched = None
if 'manual_mapping' not in st.session_state:
    st.session_state.manual_mapping = {}
if 'current_step' not in st.session_state:
    st.session_state.current_step = 'upload'  # upload, manual_match, final

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
    campaign_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if any(keyword in col_lower for keyword in ['campaign', 'اسم', 'name', 'حملة', 'إعلان']):
            campaign_col = col
            break
    
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
    
    result_df = pd.DataFrame()
    result_df['campaign_name'] = df[campaign_col]
    result_df['cost'] = pd.to_numeric(df[cost_col], errors='coerce')
    result_df['source_file'] = file_name
    
    st.success(f"✅ {file_name}: {campaign_col} → {cost_col}")
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

# ==================== المرحلة 1: رفع الملفات ====================
if st.session_state.current_step == 'upload':
    
    st.subheader("📁 رفع ملفات الإعلانات")
    st.info("💡 يمكنك رفع أكثر من ملف (Facebook, TikTok, Google Ads, إلخ)")
    campaigns_files = st.file_uploader(
        "ارفع ملفات Excel للإعلانات",
        type=['xlsx', 'xls'],
        accept_multiple_files=True,
        key="campaigns"
    )
    
    st.markdown("---")
    
    st.subheader("📦 رفع ملفات المنتجات")
    products_files = st.file_uploader(
        "ارفع ملفات Excel للمنتجات",
        type=['xlsx', 'xls'],
        accept_multiple_files=True,
        key="products"
    )
    
    if campaigns_files and products_files:
        
        st.markdown("---")
        
        if st.button("🚀 ابدأ المعالجة", type="primary"):
            
            # معالجة ملفات الإعلانات
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
            
            campaigns_df = pd.concat(all_campaigns, ignore_index=True)
            st.success(f"✅ إجمالي الإعلانات: {len(campaigns_df)}")
            
            # معالجة ملفات المنتجات
            st.markdown("---")
            st.subheader("⚙️ معالجة ملفات المنتجات...")
            all_products = []
            
            for product_file in products_files:
                with st.spinner(f"جاري معالجة {product_file.name}..."):
                    df = pd.read_excel(product_file)
                    product_name_col = None
                    for col in df.columns:
                        col_lower = str(col).lower()
                        if any(keyword in col_lower for keyword in ['اسم', 'منتج', 'product', 'name', 'item']):
                            product_name_col = col
                            break
                    
                    if product_name_col:
                        all_products.append(df)
                        st.success(f"✅ {product_file.name}: {len(df)} منتج")
            
            if not all_products:
                st.error("❌ لم يتم تحميل أي منتجات")
                st.stop()
            
            products_df = pd.concat(all_products, ignore_index=True)
            
            for col in products_df.columns:
                col_lower = str(col).lower()
                if any(keyword in col_lower for keyword in ['اسم', 'منتج', 'product', 'name']):
                    products_df.rename(columns={col: 'اسم المنتج'}, inplace=True)
                    break
            
            st.success(f"✅ إجمالي المنتجات: {len(products_df)}")
            
            # تنظيف وتجميع الإعلانات
            st.markdown("---")
            st.subheader("🔄 تجميع الإعلانات المتشابهة...")
            
            campaigns_df['normalized_name'] = campaigns_df['campaign_name'].apply(normalize_campaign_name)
            
            campaigns_grouped = campaigns_df.groupby('normalized_name').agg({
                'cost': 'sum',
                'campaign_name': 'count',
                'source_file': lambda x: ', '.join(x.unique())
            }).reset_index()
            
            campaigns_grouped.columns = ['campaign_name', 'total_spent', 'ads_count', 'source_files']
            campaigns_grouped = campaigns_grouped.sort_values('total_spent', ascending=False)
            
            st.success(f"✅ تم دمج {len(campaigns_df)} إعلان إلى {len(campaigns_grouped)} مجموعة")
            
            # مطابقة الإعلانات مع المنتجات
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
            
            # حفظ في session state
            st.session_state.campaigns_grouped = campaigns_grouped
            st.session_state.products_df = products_df
            st.session_state.unmatched = unmatched
            
            if len(unmatched) > 0:
                st.session_state.current_step = 'manual_match'
                st.rerun()
            else:
                st.session_state.current_step = 'final'
                st.rerun()

# ==================== المرحلة 2: المطابقة اليدوية ====================
elif st.session_state.current_step == 'manual_match':
    
    st.subheader("🔍 مطابقة الإعلانات يدوياً")
    st.warning(f"يوجد {len(st.session_state.unmatched)} إعلان يحتاج توضيح منك")
    
    unmatched = st.session_state.unmatched.sort_values('total_spent', ascending=False)
    products_list = st.session_state.products_df['اسم المنتج'].tolist()
    
    # إضافة خيار "لا يوجد منتج"
    products_options = ['-- اختر المنتج --', 'لا يوجد منتج (none)'] + products_list
    
    st.markdown("---")
    
    # عرض الإعلانات غير المطابقة
    st.info(f"💡 قم بمطابقة الإعلانات التالية مع المنتجات المناسبة")
    
    # نموذج المطابقة
    with st.form("manual_matching_form"):
        
        for idx, (i, row) in enumerate(unmatched.head(20).iterrows(), 1):
            st.markdown(f"### {idx}. **{row['campaign_name']}**")
            
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write(f"💰 **الإنفاق:** {row['total_spent']:,.2f} جنيه")
            with col2:
                st.write(f"📊 **عدد الإعلانات:** {row['ads_count']}")
            with col3:
                st.write(f"📁 **الملف:** {row['source_files'][:20]}...")
            
            # قائمة اختيار المنتج
            selected_product = st.selectbox(
                f"اختر المنتج المناسب للإعلان:",
                options=products_options,
                key=f"product_select_{i}"
            )
            
            if selected_product != '-- اختر المنتج --':
                if selected_product == 'لا يوجد منتج (none)':
                    st.session_state.manual_mapping[row['campaign_name']] = None
                else:
                    st.session_state.manual_mapping[row['campaign_name']] = selected_product
            
            st.markdown("---")
        
        # زر الإرسال
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            submitted = st.form_submit_button("✅ تطبيق المطابقة والمتابعة", type="primary", use_container_width=True)
        
        if submitted:
            # التحقق من أن جميع الإعلانات تم مطابقتها
            matched_count = len(st.session_state.manual_mapping)
            
            if matched_count == 0:
                st.error("⚠️ الرجاء مطابقة إعلان واحد على الأقل")
            else:
                # تطبيق المطابقة اليدوية
                for campaign, product in st.session_state.manual_mapping.items():
                    st.session_state.campaigns_grouped.loc[
                        st.session_state.campaigns_grouped['campaign_name'] == campaign,
                        'matched_product'
                    ] = product
                    st.session_state.campaigns_grouped.loc[
                        st.session_state.campaigns_grouped['campaign_name'] == campaign,
                        'match_score'
                    ] = 100 if product else 0
                
                st.success(f"✅ تم تطبيق {matched_count} مطابقة يدوية")
                st.session_state.current_step = 'final'
                st.rerun()
    
    # زر تخطي
    st.markdown("---")
    if st.button("⏭️ تخطي المطابقة والمتابعة بدون تطابق", type="secondary"):
        st.session_state.current_step = 'final'
        st.rerun()

# ==================== المرحلة 3: النتيجة النهائية ====================
elif st.session_state.current_step == 'final':
    
    st.subheader("📊 التقرير النهائي")
    
    campaigns_grouped = st.session_state.campaigns_grouped
    products_df = st.session_state.products_df
    
    # دمج البيانات النهائية
    final_df = campaigns_grouped.merge(
        products_df,
        left_on='matched_product',
        right_on='اسم المنتج',
        how='left'
    )
    
    # تحديد الأعمدة المتاحة
    available_cols = ['campaign_name', 'ads_count', 'total_spent', 'matched_product', 'source_files']
    
    if 'إجمالي الأوردرات' in final_df.columns:
        available_cols.append('إجمالي الأوردرات')
    if 'تم التسليم' in final_df.columns:
        available_cols.append('تم التسليم')
    if 'ملغي' in final_df.columns:
        available_cols.append('ملغي')
    
    final_df = final_df[available_cols].copy()
    
    # إعادة تسمية الأعمدة
    rename_dict = {
        'campaign_name': 'اسم الإعلان',
        'ads_count': 'عدد الإعلانات',
        'total_spent': 'إجمالي الصرف (جنيه)',
        'matched_product': 'اسم المنتج',
        'source_files': 'مصدر الملف'
    }
    final_df.rename(columns=rename_dict, inplace=True)
    
    # حساب تكلفة الأوردر المسلم
    if 'تم التسليم' in final_df.columns:
        final_df['تكلفة الأوردر المسلم'] = final_df.apply(
            lambda row: row['إجمالي الصرف (جنيه)'] / row['تم التسليم'] 
            if pd.notna(row['تم التسليم']) and row['تم التسليم'] > 0 
            else None,
            axis=1
        )
    
    final_df = final_df.sort_values('إجمالي الصرف (جنيه)', ascending=False)
    
    # الإحصائيات
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("إجمالي الإعلانات", len(final_df))
    with col2:
        st.metric("إجمالي الإنفاق", f"{final_df['إجمالي الصرف (جنيه)'].sum():,.0f} EGP")
    with col3:
        if 'إجمالي الأوردرات' in final_df.columns:
            st.metric("إجمالي الأوردرات", f"{final_df['إجمالي الأوردرات'].sum():.0f}")
    with col4:
        if 'تم التسليم' in final_df.columns:
            st.metric("تم التسليم", f"{final_df['تم التسليم'].sum():.0f}")
    
    st.markdown("---")
    
    # البحث
    search_term = st.text_input("🔍 ابحث في التقرير", "")
    if search_term:
        filtered_df = final_df[
            final_df['اسم الإعلان'].str.contains(search_term, case=False, na=False) |
            final_df['اسم المنتج'].fillna('').str.contains(search_term, case=False)
        ]
        st.dataframe(filtered_df, use_container_width=True, height=400)
    else:
        st.dataframe(final_df, use_container_width=True, height=400)
    
    # تحميل الملف
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, index=False, sheet_name='التقرير النهائي')
    
    st.download_button(
        label="⬇️ تحميل التقرير النهائي (Excel)",
        data=output.getvalue(),
        file_name="تقرير_الاعلانات_والمنتجات_النهائي.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
    
    # زر البدء من جديد
    st.markdown("---")
    if st.button("🔄 البدء من جديد", type="secondary"):
        st.session_state.clear()
        st.rerun()

# تذييل
st.markdown("---")
st.markdown("Made with ❤️ | YAHYA EISSA")

