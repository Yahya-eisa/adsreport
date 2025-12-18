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
    """تحديد عمود اسم الإعلان وعمود الصرف بدقة"""
    # عمود اسم الإعلان
    campaign_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if any(k in col_lower for k in ['campaign', 'ad name', 'ad', 'اسم', 'حملة', 'إعلان']):
            campaign_col = col
            break

    # عمود التكلفة / الصرف
    cost_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        # نحاول نتفادى أعمدة زي CPM, CPC إلخ
        if any(k in col_lower for k in ['amount spent', 'spend', 'cost', 'budget', 'تكلفة', 'صرف', 'انفاق']):
            # استثناء أعمدة مثل cpc, cpm, cost per
            if any(bad in col_lower for bad in ['cpc', 'cpm', 'per', '/']):
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

    st.success(f"✅ {file_name} | اسم الإعلان: {campaign_col} | الصرف: {cost_col}")
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
        # تعزيز لو في كلمة مشتركة
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
        "ارفع ملفات الإعلانات (يمكن أكثر من ملف: Facebook, TikTok,... )",
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

            # تجميع الإعلانات بنفس الاسم المنظف
            grouped = campaigns_df.groupby('campaign_name').agg({
                'cost': 'sum',
                'campaign_name_raw': lambda x: list(x.unique()),
                'source_file': lambda x: ', '.join(x.unique()),
                'campaign_name': 'count'
            }).rename(columns={'campaign_name': 'ads_count'}).reset_index()

            grouped = grouped[['campaign_name', 'cost', 'ads_count', 'campaign_name_raw', 'source_file']]
            grouped = grouped.sort_values('cost', ascending=False)

            # مطابقة تلقائية مع المنتجات
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

# ========= STEP 2: Manual Match =========
elif st.session_state.current_step == 'manual_match':
    st.subheader("🔍 مطابقة الإعلانات يدويًا مع المنتجات")

    grouped = st.session_state.campaigns_grouped
    products_df = st.session_state.products_df
    unmatched = st.session_state.unmatched.sort_values('cost', ascending=False)

    st.warning(f"يوجد {len(unmatched)} مجموعة إعلانية بدون منتج مطابق، قم بتحديد المنتج لكل إعلان.")

    products_list = products_df['اسم المنتج'].astype(str).tolist()
    products_options = ['-- اختر من القائمة --', 'لا يوجد منتج (none)'] + products_list

    with st.form("manual_form"):
        for idx, (i, row) in enumerate(unmatched.iterrows(), 1):
            st.markdown(f"### {idx}. اسم الحملة المدمجة:")
            st.code(row['campaign_name'])
            st.write(f"💰 إجمالي الصرف: {row['cost']:.2f} | 📊 عدد الإعلانات: {row['ads_count']} | 📁 من ملفات: {row['source_file']}")

            mode = st.radio(
                "طريقة المطابقة:",
                ['اختيار من قائمة المنتجات', 'كتابة اسم المنتج يدويًا'],
                key=f"mode_{i}"
            )

            if mode == 'اختيار من قائمة المنتجات':
                sel = st.selectbox(
                    "اختر المنتج المرتبط بهذه الحملة:",
                    products_options,
                    key=f"sel_{i}"
                )
                if sel == 'لا يوجد منتج (none)':
                    st.session_state.manual_mapping[row['campaign_name']] = None
                elif sel not in ['-- اختر من القائمة --', 'لا يوجد منتج (none)']:
                    st.session_state.manual_mapping[row['campaign_name']] = sel
            else:
                typed = st.text_input(
                    "اكتب اسم المنتج كما تحب يظهر في التقرير:",
                    key=f"typed_{i}"
                )
                if typed.strip():
                    st.session_state.manual_mapping[row['campaign_name']] = typed.strip()

            st.markdown("---")

        ok = st.form_submit_button("✅ تطبيق المطابقة والمتابعة", type="primary")

    if ok:
        # تطبيق المطابقة اليدوية
        for cname, pname in st.session_state.manual_mapping.items():
            grouped.loc[grouped['campaign_name'] == cname, 'matched_product'] = pname
            grouped.loc[grouped['campaign_name'] == cname, 'match_score'] = 100 if pname else 0

        st.session_state.campaigns_grouped = grouped
        # تحديث unmatched بعد المطابقة
        st.session_state.unmatched = grouped[grouped['matched_product'].isna()]

        if len(st.session_state.unmatched) > 0:
            # لو لسه فيه إعلانات بدون منتج، نرجع للمطابقة اليدوية مرة تانية
            st.info(f"مازال هناك {len(st.session_state.unmatched)} إعلان بدون منتج، سيتم عرضهم في جولة أخرى.")
            st.rerun()
        else:
            st.session_state.current_step = 'final'
            st.rerun()

# ========= STEP 3: Final Report =========
elif st.session_state.current_step == 'final':
    st.subheader("📊 التقرير النهائي")

    grouped = st.session_state.campaigns_grouped
    products_df = st.session_state.products_df

    final = grouped.merge(
        products_df,
        left_on='matched_product',
        right_on='اسم المنتج',
        how='left'
    )

    cols = ['campaign_name', 'ads_count', 'cost', 'matched_product', 'source_file']
    if 'إجمالي الأوردرات' in final.columns:
        cols.append('إجمالي الأوردرات')
    if 'تم التسليم' in final.columns:
        cols.append('تم التسليم')
    if 'ملغي' in final.columns:
        cols.append('ملغي')

    final = final[cols].copy()
    final.rename(columns={
        'campaign_name': 'اسم الحملة',
        'ads_count': 'عدد الإعلانات',
        'cost': 'إجمالي الصرف',
        'matched_product': 'اسم المنتج',
        'source_file': 'مصدر الملفات'
    }, inplace=True)

    # تكلفة الأوردر المسلم
    if 'تم التسليم' in final.columns:
        final['تكلفة الأوردر المسلم'] = final.apply(
            lambda r: r['إجمالي الصرف'] / r['تم التسليم']
            if pd.notna(r.get('تم التسليم')) and r.get('تم التسليم', 0) > 0
            else None,
            axis=1
        )

    # تقريب الأرقام لرقمين بعد العلامة
    num_cols = final.select_dtypes(include=['float', 'int']).columns
    final[num_cols] = final[num_cols].round(2)

    final = final.sort_values('إجمالي الصرف', ascending=False)

    # إحصائيات
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("عدد مجموعات الحملات", len(final))
    with c2:
        st.metric("إجمالي الصرف", f"{final['إجمالي الصرف'].sum():,.2f}")
    if 'إجمالي الأوردرات' in final.columns:
        with c3:
            st.metric("إجمالي الأوردرات", f"{final['إجمالي الأوردرات'].sum():.0f}")
    if 'تم التسليم' in final.columns:
        with c4:
            st.metric("إجمالي تم التسليم", f"{final['تم التسليم'].sum():.0f}")

    st.markdown("---")

    # بحث
    q = st.text_input("🔍 بحث في اسم الحملة أو اسم المنتج", "")
    view_df = final
    if q:
        view_df = final[
            final['اسم الحملة'].str.contains(q, case=False, na=False) |
            final['اسم المنتج'].fillna('').str.contains(q, case=False)
        ]

    st.dataframe(view_df, use_container_width=True, height=450)

    # تحميل
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        final.to_excel(writer, index=False, sheet_name="التقرير النهائي")

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
