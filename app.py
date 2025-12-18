import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="ربط الحملات بالمنتجات", page_icon="📊", layout="wide")
st.title("🎯 ربط حملات الإعلانات بالمنتجات + تقرير لكل منتج")
st.markdown("---")

# ========= تهيئة حالة الجلسة =========
if 'campaigns_df' not in st.session_state:
    st.session_state.campaigns_df = None
if 'products_df' not in st.session_state:
    st.session_state.products_df = None
if 'grouped_campaigns' not in st.session_state:
    st.session_state.grouped_campaigns = None
if 'manual_mapping' not in st.session_state:
    st.session_state.manual_mapping = {}
if 'current_step' not in st.session_state:
    st.session_state.current_step = 'upload'  # upload -> manual_match -> final

NO_RESULT_LABEL = "لا توجد نتائج"

# ========= دوال مساعدة =========

def normalize_campaign_name(name):
    """تنظيف اسم الحملة (إزالة تواريخ، Copy، فراغات، علامات غريبة)"""
    name = str(name)
    name = name.replace('‎', '').replace('‏', '')
    # إزالة تواريخ في آخر الاسم مثل 12-15 أو 12/15
    name = re.sub(r'\s+\d{1,2}[-/]\d{1,2}.*$', '', name)
    # إزالة Copy وأي رقم جنبها
    name = re.sub(r'\s*copy\s*\d*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*copy\s+of\s+', '', name, flags=re.IGNORECASE)
    # إزالة كلمات عامة غير مفيدة لو موجودة كـ prefix
    name = re.sub(r'^new\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^scale\s+of\s+', '', name, flags=re.IGNORECASE)
    # توحيد المسافات والشرطات
    name = re.sub(r'\s+[-–—]\s+', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


def extract_campaign_data(df, file_name):
    """
    استخراج:
    - campaign_name_raw
    - campaign_name (normalized)
    - cost (من Amount spent أو Cost)
    """
    # اختيار عمود اسم الحملة
    campaign_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if any(k in col_lower for k in ['campaign', 'ad name', 'ad set name', 'ad', 'اسم', 'حملة', 'إعلان']):
            campaign_col = col
            break

    # اختيار عمود الصرف:
    # 1) amount spent
    cost_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if 'amount spent' in col_lower:
            cost_col = col
            break
    # 2) cost / spend / انفاق / صرف / تكلفة مع استبعاد cpc/cpm/per
    if cost_col is None:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(k in col_lower for k in ['cost', 'spend', 'انفاق', 'صرف', 'تكلفة']):
                if any(bad in col_lower for bad in ['cpc', 'cpm', 'per', '/', 'avg']):
                    continue
                cost_col = col
                break

    if campaign_col is None or cost_col is None:
        st.error(f"❌ ملف {file_name}: لم يتم العثور على عمود اسم الحملة أو عمود الصرف.")
        st.info(f"الأعمدة المتاحة: {list(df.columns)}")
        return None

    out = pd.DataFrame()
    out['campaign_name_raw'] = df[campaign_col]
    out['campaign_name'] = df[campaign_col].apply(normalize_campaign_name)
    out['cost'] = pd.to_numeric(df[cost_col], errors='coerce')
    out['source_file'] = file_name

    # إزالة صفوف فاضية أو total
    out = out[out['campaign_name_raw'].notna()]
    out = out[~out['campaign_name_raw'].astype(str).str.lower().str.contains('total')]
    out = out[out['cost'].notna()]

    st.success(f"✅ {file_name} | اسم الحملة: {campaign_col} | الصرف من: {cost_col}")
    return out


# ========= STEP 1: رفع الملفات وتجميع الحملات =========
if st.session_state.current_step == 'upload':
    st.subheader("📁 رفع ملفات الإعلانات (Facebook, TikTok, ...)")
    campaigns_files = st.file_uploader(
        "ارفع ملفات الإعلانات (يمكن أكثر من ملف)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="campaigns"
    )

    st.subheader("📦 رفع ملفات المنتجات (شيت واحد أو أكثر)")
    products_files = st.file_uploader(
        "ارفع ملفات المنتجات",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="products"
    )

    if campaigns_files and products_files and st.button("🚀 ابدأ المعالجة", type="primary"):
        # 1) الإعلانات
        all_campaigns = []
        for f in campaigns_files:
            df = pd.read_excel(f)
            extracted = extract_campaign_data(df, f.name)
            if extracted is not None:
                all_campaigns.append(extracted)
        if not all_campaigns:
            st.stop()
        campaigns_df = pd.concat(all_campaigns, ignore_index=True)

        # 2) المنتجات
        all_products = []
        for f in products_files:
            dfp = pd.read_excel(f)
            name_col = None
            for col in dfp.columns:
                col_lower = str(col).lower()
                if any(k in col_lower for k in ['اسم', 'منتج', 'product', 'name', 'item']):
                    name_col = col
                    break
            if name_col is None:
                st.error(f"❌ ملف منتجات {f.name} لا يحتوي على عمود اسم المنتج.")
            else:
                dfp = dfp.rename(columns={name_col: 'اسم المنتج'})
                all_products.append(dfp)
        if not all_products:
            st.stop()
        products_df = pd.concat(all_products, ignore_index=True)

        # تجميع الحملات حسب الاسم المنظف
        grouped_campaigns = campaigns_df.groupby('campaign_name').agg({
            'cost': 'sum',
            'campaign_name_raw': lambda x: list(x.unique()),
            'source_file': lambda x: ', '.join(x.unique()),
            'campaign_name': 'count'
        }).rename(columns={'campaign_name': 'ads_count'}).reset_index()

        grouped_campaigns = grouped_campaigns[['campaign_name', 'cost', 'ads_count', 'campaign_name_raw', 'source_file']]
        grouped_campaigns = grouped_campaigns.sort_values('cost', ascending=False)

        st.session_state.campaigns_df = campaigns_df
        st.session_state.products_df = products_df
        st.session_state.grouped_campaigns = grouped_campaigns
        st.session_state.manual_mapping = {}
        st.session_state.current_step = 'manual_match'
        st.rerun()

# ========= STEP 2: مطابقة يدوية (كل حملة → 0 أو أكثر من المنتجات) =========
elif st.session_state.current_step == 'manual_match':
    st.subheader("🔍 مطابقة الحملات مع المنتجات (يدويًا)")

    grouped = st.session_state.grouped_campaigns.copy()
    products_df = st.session_state.products_df
    products_list = products_df['اسم المنتج'].astype(str).tolist()

    st.info("لكل حملة: اختر منتج واحد أو أكثر، أو اختر 'لا توجد نتائج' لو الحملة عامة / بدون منتج.")

    with st.form("manual_match_form"):
        for idx, (i, row) in enumerate(grouped.iterrows(), 1):
            st.markdown(f"### {idx}. اسم الحملة (بعد التنظيف):")
            st.code(row['campaign_name'])
            st.write(
                f"💰 إجمالي الصرف: {row['cost']:.2f} | "
                f"📊 عدد الإعلانات داخل هذه المجموعة: {row['ads_count']} | "
                f"📁 من الملفات: {row['source_file']}"
            )

            col1, col2 = st.columns([2, 1])
            with col1:
                selected_products = st.multiselect(
                    "اختر كل المنتجات المرتبطة بهذه الحملة:",
                    options=products_list,
                    key=f"products_{i}"
                )
            with col2:
                no_result = st.checkbox(
                    "هذه الحملة عامة (لا توجد نتائج / لا منتج ثابت)",
                    key=f"nores_{i}"
                )

            if no_result:
                st.session_state.manual_mapping[row['campaign_name']] = [NO_RESULT_LABEL]
            else:
                st.session_state.manual_mapping[row['campaign_name']] = selected_products

            st.markdown("---")

        submitted = st.form_submit_button("✅ تأكيد وحساب التقرير النهائي", type="primary")

    if submitted:
        st.session_state.current_step = 'final'
        st.rerun()

# ========= STEP 3: تقرير نهائي للحملات + تقرير مجمّع لكل منتج =========
elif st.session_state.current_step == 'final':
    st.subheader("📊 التقرير النهائي")

    grouped = st.session_state.grouped_campaigns.copy()
    products_df = st.session_state.products_df
    manual_mapping = st.session_state.manual_mapping

    # ربط كل حملة بقائمة منتجات (أو لا توجد نتائج)
    grouped['قائمة المنتجات'] = grouped['campaign_name'].map(manual_mapping)

    # حملات عامة (لا توجد نتائج)
    def is_no_result(lst):
        return isinstance(lst, list) and len(lst) == 1 and lst[0] == NO_RESULT_LABEL

    campaigns_no_result = grouped[grouped['قائمة المنتجات'].apply(is_no_result)].copy()
    campaigns_with_products = grouped[~grouped['قائمة المنتجات'].apply(is_no_result)].copy()

    # تحويل قائمة المنتجات إلى نص واحد في نفس الخلية
    def products_list_to_str(lst):
        if not isinstance(lst, list) or len(lst) == 0:
            return ""
        # شيل التكرار لو حصل
        unique = list(dict.fromkeys(map(str, lst)))
        return " | ".join(unique)

    grouped['أسماء المنتجات'] = grouped['قائمة المنتجات'].apply(products_list_to_str)

    # تقريب الصرف
    grouped['cost'] = grouped['cost'].round(2)

    # --- 3.1 تقرير على مستوى الحملات ---
    final_campaigns = grouped[['campaign_name', 'ads_count', 'أسماء المنتجات', 'cost', 'source_file']].copy()
    final_campaigns.rename(columns={
        'campaign_name': 'اسم الحملة',
        'ads_count': 'عدد الإعلانات',
        'cost': 'إجمالي الصرف',
        'source_file': 'مصدر الملفات'
    }, inplace=True)

    final_campaigns = final_campaigns.sort_values('إجمالي الصرف', ascending=False)

    # عرض جدول الحملات
    st.subheader("📋 حملات الإعلانات مع المنتجات المرتبطة")
    search = st.text_input("🔍 بحث في اسم الحملة أو أسماء المنتجات", "")
    view_df = final_campaigns
    if search:
        view_df = final_campaigns[
            final_campaigns['اسم الحملة'].str.contains(search, case=False, na=False) |
            final_campaigns['أسماء المنتجات'].fillna('').str.contains(search, case=False)
        ]
    st.dataframe(view_df, use_container_width=True, height=350)

    # عرض الحملات العامة (لا توجد نتائج)
    if not campaigns_no_result.empty:
        st.subheader("⚠️ حملات عامة (لا توجد نتائج / لا منتج ثابت)")
        df_no_res = campaigns_no_result[['campaign_name', 'cost', 'ads_count', 'source_file']].copy()
        df_no_res.rename(columns={
            'campaign_name': 'اسم الحملة',
            'cost': 'إجمالي الصرف',
            'ads_count': 'عدد الإعلانات',
            'source_file': 'مصدر الملفات'
        }, inplace=True)
        df_no_res['إجمالي الصرف'] = df_no_res['إجمالي الصرف'].round(2)
        st.dataframe(df_no_res, use_container_width=True, height=250)
    else:
        df_no_res = pd.DataFrame()

    # --- 3.2 تقرير مجمّع لكل منتج ---
    st.subheader("📦 تقرير مجمّع لكل منتج")

    if campaigns_with_products.empty:
        st.warning("لا توجد حملات مرتبطة بمنتجات.")
        final_by_product = pd.DataFrame()
    else:
        # 1) فكّ الربط: كل (حملة × منتج) كسطر منفصل
        rows = []
        for _, row in campaigns_with_products.iterrows():
            products_lst = row['قائمة المنتجات'] if isinstance(row['قائمة المنتجات'], list) else []
            unique_products = list(dict.fromkeys(map(str, products_lst)))
            for p in unique_products:
                rows.append({
                    'اسم المنتج': p,
                    'اسم الحملة': row['campaign_name'],
                    'إجمالي الصرف_الحملة': row['cost'],
                    'عدد الإعلانات_الحملة': row['ads_count']
                })
        if rows:
            df_campaign_product = pd.DataFrame(rows)
        else:
            df_campaign_product = pd.DataFrame(columns=['اسم المنتج', 'اسم الحملة', 'إجمالي الصرف_الحملة', 'عدد الإعلانات_الحملة'])

        # 2) تجميع على مستوى المنتج:
        #    عدد الحملات، إجمالي الصرف، ثم نضيف من شيت المنتجات إجمالي الأوردرات / التسليم / المرتجع
        agg_from_campaigns = df_campaign_product.groupby('اسم المنتج').agg({
            'اسم الحملة': 'count',
            'إجمالي الصرف_الحملة': 'sum'
        }).rename(columns={
            'اسم الحملة': 'عدد الحملات',
            'إجمالي الصرف_الحملة': 'إجمالي الصرف'
        })

        # تجهيز أرقام المنتجات
        required_cols = ['اسم المنتج', 'إجمالي الأوردرات', 'تم التسليم', 'ملغي']
        for c in required_cols:
            if c not in products_df.columns:
                st.warning(f"⚠️ عمود {c} مش موجود في شيت المنتجات، هيتسجل 0.")
                products_df[c] = 0

        agg_from_products = products_df.groupby('اسم المنتج').agg({
            'إجمالي الأوردرات': 'sum',
            'تم التسليم': 'sum',
            'ملغي': 'sum'
        })

        # دمج
        final_by_product = agg_from_campaigns.join(agg_from_products, how='left').fillna(0)

        # حساب سعر الأوردر المسلم
        final_by_product['سعر الأوردر المسلم'] = final_by_product.apply(
            lambda r: (r['إجمالي الصرف'] / r['تم التسليم']) if r['تم التسليم'] > 0 else None,
            axis=1
        )

        # تقريب الأرقام
        num_cols_prod = final_by_product.select_dtypes(include=['float', 'int']).columns
        final_by_product[num_cols_prod] = final_by_product[num_cols_prod].round(2)

        final_by_product = final_by_product.reset_index()
        final_by_product = final_by_product.sort_values('إجمالي الصرف', ascending=False)

    if not final_by_product.empty:
        st.dataframe(final_by_product, use_container_width=True, height=350)

    # منتجات لم تُستخدم في أي حملة
    used_products = set()
    for lst in campaigns_with_products['قائمة المنتجات']:
        if isinstance(lst, list):
            for p in lst:
                used_products.add(str(p))

    products_df['اسم المنتج'] = products_df['اسم المنتج'].astype(str)
    unused_products = products_df[~products_df['اسم المنتج'].isin(used_products)].copy()

    if not unused_products.empty:
        st.subheader("📦 منتجات بدون أي حملات مرتبطة")
        st.dataframe(unused_products, use_container_width=True, height=250)

    # تحميل Excel: شيت حملات + شيت منتجات + شيت حملات بلا نتائج + شيت منتجات بلا حملات
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        final_campaigns.to_excel(writer, index=False, sheet_name="تقرير الحملات")
        if not final_by_product.empty:
            final_by_product.to_excel(writer, index=False, sheet_name="تقرير المنتجات")
        if not df_no_res.empty:
            df_no_res.to_excel(writer, index=False, sheet_name="حملات بلا نتائج")
        if not unused_products.empty:
            unused_products.to_excel(writer, index=False, sheet_name="منتجات بلا حملات")

    st.download_button(
        "⬇️ تحميل التقرير الكامل (Excel)",
        data=buf.getvalue(),
        file_name="تقرير_الحملات_والمنتجات_مجمع.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

    st.markdown("---")
    if st.button("🔄 البدء من جديد"):
        st.session_state.clear()
        st.rerun()

st.markdown("---")
st.caption("Made with ❤️ | Powered by Streamlit")
