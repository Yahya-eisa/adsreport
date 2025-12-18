import streamlit as st
import pandas as pd
import re
from difflib import SequenceMatcher
import io

st.set_page_config(page_title="دمج الإعلانات والمنتجات", page_icon="📊", layout="wide")
st.title("🎯 دمج الإعلانات مع المنتجات")
st.markdown("---")

# ========= تهيئة حالة الجلسة =========
if 'campaigns_grouped' not in st.session_state:
    st.session_state.campaigns_grouped = None
if 'products_df' not in st.session_state:
    st.session_state.products_df = None
if 'unmatched' not in st.session_state:
    st.session_state.unmatched = None
if 'manual_mapping' not in st.session_state:
    st.session_state.manual_mapping = {}
if 'current_step' not in st.session_state:
    st.session_state.current_step = 'upload'  # upload -> manual_match -> final

NO_PRODUCT_FLAG = "__NO_PRODUCT__"

# ========= دوال مساعدة =========

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

def extract_campaign_data(df, file_name):
    """
    استخراج اسم الإعلان والصرف:
    - الصرف أولاً من عمود فيه 'amount spent'
    - لو مش موجود، نستخدم عمود فيه 'cost' أو 'spend' أو 'صرف/تكلفة'
    - استثناء cpc/cpm/cost per
    """
    # تجاهل صفوف total
    df = df[~df.astype(str).apply(lambda r: 'total' in r.str.lower().to_string(), axis=1)]

    # اسم الإعلان
    campaign_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if any(k in col_lower for k in ['campaign', 'ad name', 'ad set name', 'ad', 'اسم', 'حملة', 'إعلان']):
            campaign_col = col
            break

    # الصرف: أولوية لـ amount spent
    cost_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if 'amount spent' in col_lower:
            cost_col = col
            break
    if cost_col is None:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(k in col_lower for k in ['cost', 'spend', 'انفاق', 'صرف', 'تكلفة']):
                if any(bad in col_lower for bad in ['cpc', 'cpm', 'per', '/', 'avg']):
                    continue
                cost_col = col
                break

    if campaign_col is None or cost_col is None:
        st.error(f"❌ ملف {file_name}: لم يتم العثور على عمود اسم الإعلان أو عمود الصرف.")
        st.info(f"الأعمدة المتاحة: {list(df.columns)}")
        return None

    out = pd.DataFrame()
    out['campaign_name_raw'] = df[campaign_col]
    out['campaign_name'] = df[campaign_col].apply(normalize_campaign_name)
    out['cost'] = pd.to_numeric(df[cost_col], errors='coerce')
    out['source_file'] = file_name

    # حذف الصفوف اللي مفيهاش اسم إعلان أو مفيهاش صرف
    out = out[out['campaign_name_raw'].notna()]
    out = out[~out['campaign_name_raw'].astype(str).str.lower().str.contains('total')]
    out = out[out['cost'].notna()]

    st.success(f"✅ {file_name} | اسم الإعلان: {campaign_col} | الصرف من العمود: {cost_col}")
    return out

def find_product_match(campaign_name, products_list, threshold=60):
    """مطابقة تقريبية بين اسم الإعلان واسم المنتج"""
    if not campaign_name or pd.isna(campaign_name):
        return None, 0
    campaign_lower = str(campaign_name).lower()
    best_match = None
    best_score = threshold

    for product in products_list:
        product_lower = str(product).lower()
        score = SequenceMatcher(None, campaign_lower, product_lower).ratio() * 100
        for w in campaign_lower.split():
            w = w.strip()
            if len(w) > 3 and w in product_lower:
                score += 10
        if score > best_score:
            best_score = score
            best_match = product

    return best_match, best_score

# ========= STEP 1: Upload & Auto Match =========
if st.session_state.current_step == 'upload':
    st.subheader("📁 رفع ملفات الإعلانات")
    campaigns_files = st.file_uploader(
        "ارفع ملفات الإعلانات (Facebook, TikTok, ...)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="campaigns"
    )

    st.subheader("📦 رفع ملفات المنتجات")
    products_files = st.file_uploader(
        "ارفع ملفات المنتجات (يمكن أكثر من ملف)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="products"
    )

    if campaigns_files and products_files:
        if st.button("🚀 ابدأ المعالجة", type="primary"):
            # الإعلانات
            all_campaigns = []
            for f in campaigns_files:
                df = pd.read_excel(f)
                extracted = extract_campaign_data(df, f.name)
                if extracted is not None:
                    all_campaigns.append(extracted)
            if not all_campaigns:
                st.stop()
            campaigns_df = pd.concat(all_campaigns, ignore_index=True)

            # المنتجات
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
            grouped = campaigns_df.groupby('campaign_name').agg({
                'cost': 'sum',
                'campaign_name_raw': lambda x: list(x.unique()),
                'source_file': lambda x: ', '.join(x.unique()),
                'campaign_name': 'count'
            }).rename(columns={'campaign_name': 'ads_count'}).reset_index()

            grouped = grouped[['campaign_name', 'cost', 'ads_count', 'campaign_name_raw', 'source_file']]
            grouped = grouped.sort_values('cost', ascending=False)

            # مطابقة تلقائية
            products_list = products_df['اسم المنتج'].astype(str).tolist()
            grouped['matched_product'] = None
            grouped['match_score'] = 0.0

            prog = st.progress(0)
            for i, row in grouped.iterrows():
                mp, score = find_product_match(row['campaign_name'], products_list, threshold=60)
                grouped.at[i, 'matched_product'] = mp
                grouped.at[i, 'match_score'] = score
                prog.progress((i + 1) / len(grouped))

            unmatched = grouped[grouped['matched_product'].isna()]

            st.session_state.campaigns_grouped = grouped
            st.session_state.products_df = products_df
            st.session_state.unmatched = unmatched
            st.session_state.manual_mapping = {}

            if len(unmatched) > 0:
                st.session_state.current_step = 'manual_match'
            else:
                st.session_state.current_step = 'final'
            st.rerun()

# ========= STEP 2: Manual Match (كل الإعلانات غير المطابقة) =========
elif st.session_state.current_step == 'manual_match':
    st.subheader("🔍 مطابقة كل الإعلانات غير المرتبطة بأي منتج")

    grouped = st.session_state.campaigns_grouped
    products_df = st.session_state.products_df
    unmatched = st.session_state.unmatched.sort_values('cost', ascending=False)

    st.warning(f"عدد الحملات غير المطابقة: {len(unmatched)}")

    products_list = products_df['اسم المنتج'].astype(str).tolist()

    st.info("💡 يمكنك البحث داخل قائمة المنتجات بالكتابة في مربع السيرش في الـ multiselect.")

    with st.form("manual_form"):
        for idx, (i, row) in enumerate(unmatched.iterrows(), 1):
            st.markdown(f"### {idx}. الحملة المدمجة:")
            st.code(row['campaign_name'])
            st.write(
                f"💰 إجمالي الصرف: {row['cost']:.2f} | "
                f"📊 عدد الإعلانات: {row['ads_count']} | "
                f"📁 من الملفات: {row['source_file']}"
            )

            col1, col2 = st.columns([2, 1])
            with col1:
                sel_list = st.multiselect(
                    "اختر كل المنتجات المرتبطة بهذه الحملة (يمكن أكثر من منتج):",
                    options=products_list,
                    key=f"multi_{i}"
                )
            with col2:
                no_prod = st.checkbox(
                    "هذه الحملة عامة (لا يوجد منتج محدد)",
                    key=f"noprod_{i}"
                )

            # حفظ في manual_mapping
            if no_prod:
                st.session_state.manual_mapping[row['campaign_name']] = [NO_PRODUCT_FLAG]
            else:
                st.session_state.manual_mapping[row['campaign_name']] = sel_list

            st.markdown("---")

        ok = st.form_submit_button("✅ تطبيق المطابقة والمتابعة", type="primary")

    if ok:
        # تطبيق كل المطابقات اليدوية
        for cname, plist in st.session_state.manual_mapping.items():
            if not plist:
                grouped.loc[grouped['campaign_name'] == cname, 'matched_product'] = None
                grouped.loc[grouped['campaign_name'] == cname, 'match_score'] = 0
            elif NO_PRODUCT_FLAG in plist:
                grouped.loc[grouped['campaign_name'] == cname, 'matched_product'] = NO_PRODUCT_FLAG
                grouped.loc[grouped['campaign_name'] == cname, 'match_score'] = 0
            else:
                joined = " | ".join(map(str, plist))
                grouped.loc[grouped['campaign_name'] == cname, 'matched_product'] = joined
                grouped.loc[grouped['campaign_name'] == cname, 'match_score'] = 100

        st.session_state.campaigns_grouped = grouped
        st.session_state.unmatched = grouped[grouped['matched_product'].isna()]

        if len(st.session_state.unmatched) > 0:
            st.info(f"مازال هناك {len(st.session_state.unmatched)} حملة بدون منتج، سيتم عرضها لتكمل المطابقة.")
            st.rerun()
        else:
            st.session_state.current_step = 'final'
            st.rerun()

# ========= STEP 3: Final Report =========
elif st.session_state.current_step == 'final':
    st.subheader("📊 التقرير النهائي")

    grouped = st.session_state.campaigns_grouped
    products_df = st.session_state.products_df

    # الحملات بدون منتج (NO_PRODUCT_FLAG)
    ads_no_product = grouped[grouped['matched_product'] == NO_PRODUCT_FLAG].copy()

    # الحملات التي لها منتجات (نص أوتوماتيك أو يدوي)
    grouped_for_merge = grouped[grouped['matched_product'].notna() & (grouped['matched_product'] != NO_PRODUCT_FLAG)].copy()

    # merge بسيط: هنا matched_product هو نص (قد يحتوي أكثر من منتج مفصول بـ |)
    # فنكتفي بعرضه كما هو بدون merge بالمنتجات لتفادي التضخيم
    final = grouped_for_merge.copy()
    final.rename(columns={
        'campaign_name': 'اسم الحملة',
        'ads_count': 'عدد الإعلانات',
        'cost': 'إجمالي الصرف',
        'matched_product': 'أسماء المنتجات',
        'source_file': 'مصدر الملفات'
    }, inplace=True)

    # تقريب الأرقام
    num_cols = final.select_dtypes(include=['float', 'int']).columns
    final[num_cols] = final[num_cols].round(2)

    final = final.sort_values('إجمالي الصرف', ascending=False)

    # منتجات مستخدمة في أي حملة
    used_products = set()
    for val in grouped_for_merge['matched_product'].dropna().astype(str):
        for p in val.split('|'):
            p = p.strip()
            if p:
                used_products.add(p)

    # منتجات لم تُستخدم في أي حملة
    products_df['اسم المنتج'] = products_df['اسم المنتج'].astype(str)
    unused_products = products_df[~products_df['اسم المنتج'].isin(used_products)].copy()

    # إحصائيات
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("عدد مجموعات الحملات المرتبطة بمنتجات", len(final))
    with c2:
        st.metric("إجمالي الصرف", f"{final['إجمالي الصرف'].sum():,.2f}")
    with c3:
        st.metric("حملات بدون منتج", len(ads_no_product))

    st.markdown("---")

    # بحث
    q = st.text_input("🔍 بحث في اسم الحملة أو أسماء المنتجات", "")
    view_df = final
    if q:
        view_df = final[
            final['اسم الحملة'].str.contains(q, case=False, na=False) |
            final['أسماء المنتجات'].fillna('').str.contains(q, case=False)
        ]

    st.subheader("📋 حملات مرتبطة بمنتجات")
    st.dataframe(view_df, use_container_width=True, height=350)

    # حملات بدون منتجات
    if not ads_no_product.empty:
        st.subheader("⚠️ حملات عامة (بدون منتج محدد)")
        df_ads_np = ads_no_product[['campaign_name', 'cost', 'ads_count', 'source_file']].copy()
        df_ads_np.rename(columns={
            'campaign_name': 'اسم الحملة',
            'cost': 'إجمالي الصرف',
            'ads_count': 'عدد الإعلانات',
            'source_file': 'مصدر الملفات'
        }, inplace=True)
        num_cols_np = df_ads_np.select_dtypes(include=['float', 'int']).columns
        df_ads_np[num_cols_np] = df_ads_np[num_cols_np].round(2)
        st.dataframe(df_ads_np, use_container_width=True, height=250)
    else:
        df_ads_np = pd.DataFrame()

    # منتجات بدون حملات
    if not unused_products.empty:
        st.subheader("📦 منتجات بدون أي حملات")
        st.dataframe(unused_products, use_container_width=True, height=250)

    # حفظ إلى Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        final.to_excel(writer, index=False, sheet_name="حملات بمنتجات")
        if not df_ads_np.empty:
            df_ads_np.to_excel(writer, index=False, sheet_name="حملات بدون منتجات")
        if not unused_products.empty:
            unused_products.to_excel(writer, index=False, sheet_name="منتجات بدون حملات")

    st.download_button(
        "⬇️ تحميل التقرير (Excel)",
        data=buf.getvalue(),
        file_name="تقرير_الاعلانات_والمنتجات_النهائي.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )

    st.markdown("---")
    if st.button("🔄 البدء من جديد"):
        st.session_state.clear()
        st.rerun()

st.markdown("---")
st.caption("Made with ❤️ | Powered by Streamlit")
