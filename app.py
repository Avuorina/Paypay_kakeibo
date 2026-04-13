import streamlit as st
import pandas as pd
from datetime import date
import io
import time

from config import APP_NAME, DEFAULT_CATEGORIES, THEME_COLOR_PRIMARY
from utils import parse_paypay_csv, get_target_period, get_month_str
from database import (
    get_all_transactions, save_transactions, update_transaction_category,
    delete_transaction, add_manual_transaction, get_budgets, save_budget, init_db,
    get_custom_categories, add_custom_category, update_transaction_category_rule_only
)
from ai_categorizer import categorize_transactions
from ui_components import create_pie_chart, create_custom_css

# ----- ページ設定 -----
st.set_page_config(page_title=APP_NAME, page_icon="👛", layout="centered", initial_sidebar_state="collapsed")

# カスタムCSS適用
st.markdown(create_custom_css(), unsafe_allow_html=True)

# ----- セッションステート初期化 -----
if 'db_inited' not in st.session_state:
    init_db()
    st.session_state.db_inited = True
    
if 'temp_df' not in st.session_state:
    st.session_state.temp_df = None

custom_categories = get_custom_categories()

@st.dialog("✏️ カテゴリの修正")
def edit_category_dialog(idx, current_store, current_amount, current_date, current_cat):
    st.write(f"**{current_date}**  \n**{current_store}** ({current_amount:,}円)")
    new_cat = st.selectbox("正しいカテゴリを選択", custom_categories, index=custom_categories.index(current_cat) if current_cat in custom_categories else 0)
    
    if st.button("💾 保存して学習", type="primary", use_container_width=True):
        df = st.session_state.temp_df
        if df is not None and idx in df.index:
            row_to_save = df.loc[[idx]].copy()
            row_to_save['category'] = new_cat
            row_to_save['user_confirmed'] = True
            save_transactions(row_to_save)
            update_transaction_category_rule_only(row_to_save['store'].values[0], new_cat)
            st.session_state.temp_df = df.drop(idx)
        st.rerun()

# ----- メインロジック -----
st.title(f"👛 {APP_NAME}")

tabs = st.tabs(["🏠 ホーム", "📝 明細", "⬆️ アップロード", "⚙️ 設定"])

### 🏠 ホームダッシュボード ###
with tabs[0]:
    st.header("今月のサマリー")
    
    # 期間選択（デフォルトは前25〜今24）
    c1, c2 = st.columns(2)
    def_start, def_end = get_target_period()
    start_date = c1.date_input("開始日", value=def_start)
    end_date = c2.date_input("終了日", value=def_end)
    
    df = get_all_transactions()
    
    if not df.empty:
        # 日付文字列から datetime 形式に変換。errors='coerce' で不正なフォーマットは NaT になる。
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        # NaT が含まれる行を削除しておく（不要であれば残してもよいが比較時にエラーになる可能性あり）
        df = df.dropna(subset=['date'])
        
        # start_date / end_date も pd.Timestamp に変換して比較する
        period_df = df[
            (df['date'] >= pd.Timestamp(start_date)) & 
            (df['date'] <= pd.Timestamp(end_date))
        ]
        
        total_expense = period_df['amount'].sum()
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.metric("支出合計", f"¥ {total_expense:,}")
            
        with col2:
            st.write("カテゴリ別割合")
            if not period_df.empty:
                fig = create_pie_chart(period_df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("この期間のデータはありません")
                
        # 予算アラート
        st.subheader("📊 予算状況")
        month_str = get_month_str(end_date)
        budgets = get_budgets(month_str)
        
        if budgets:
            for cat, budget_amt in budgets.items():
                cat_expense = period_df[period_df['category'] == cat]['amount'].sum()
                progress = min(cat_expense / budget_amt if budget_amt > 0 else 0, 1.0)
                
                # プログレスバーの色を変える (CSSハック不要な範囲で警告)
                if progress >= 1.0:
                    st.markdown(f"**<span style='color:red;'>【{cat}】 予算オーバー！ ( {cat_expense:,}円 / {budget_amt:,}円 )</span>**", unsafe_allow_html=True)
                elif progress >= 0.8:
                    st.warning(f"【{cat}】 予算接近中 ( {cat_expense:,}円 / {budget_amt:,}円 )")
                else:
                    st.success(f"【{cat}】 余裕あり ( {cat_expense:,}円 / {budget_amt:,}円 )")
                    
                st.progress(progress)
        else:
            st.info("設定タブから予算を設定してみましょう！")

    else:
        st.info("データがありません。アップロードタブからCSVを取り込んでください。")

### 📝 明細一覧・編集 ###
with tabs[1]:
    st.header("明細一覧")
    
    # フィルタリング
    f_cat = st.selectbox("カテゴリフィルタ", ["すべて"] + custom_categories)
    f_word = st.text_input("検索（店舗名・内容）", placeholder="PayPay...")
    
    if not df.empty:
        # datetime 型に変換済みなので文字列に戻す、または表示用に調整
        display_df = df.copy()
        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
        
        if f_cat != "すべて":
            display_df = display_df[display_df['category'] == f_cat]
        if f_word:
            display_df = display_df[
                display_df['store'].str.contains(f_word, na=False) | 
                display_df['content'].str.contains(f_word, na=False)
            ]
            
        # 一括選択チェックボックス
        select_all = st.checkbox("☑️ 表示中の明細をすべて選択")
        
        # エクスプローラー風に選択できるようにCheckBox列を追加
        display_df.insert(0, "選択", select_all)
        
        st.write("▼ 左のチェックボックスで選択して一括削除、またはカテゴリの直接変更が可能です")
        edited_df = st.data_editor(
            display_df[['選択', 'id', 'date', 'category', 'amount', 'store', 'content']],
            column_config={
                "選択": st.column_config.CheckboxColumn("選択", default=False),
                "id": None, # IDは非表示
                "date": st.column_config.TextColumn("日付", disabled=True),
                "category": st.column_config.SelectboxColumn("カテゴリ", options=custom_categories, required=True),
                "amount": st.column_config.NumberColumn("金額(円)", disabled=True),
                "store": st.column_config.TextColumn("店舗", disabled=True),
                "content": st.column_config.TextColumn("内容", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="details_editor"
        )
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 カテゴリ変更を保存"):
                changed_df = edited_df[edited_df['category'] != display_df['category']]
                if not changed_df.empty:
                    for _, row in changed_df.iterrows():
                        update_transaction_category(row['id'], row['category'])
                    st.success(f"{len(changed_df)} 件のカテゴリを更新しました！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.info("変更はありません")
                    
        with c2:
            selected_rows = edited_df[edited_df['選択'] == True]
            if not selected_rows.empty:
                if st.button(f"🗑️ 選択した {len(selected_rows)} 件を削除", type="primary"):
                    for row_id in selected_rows['id']:
                        delete_transaction(row_id)
                    st.success(f"削除完了！")
                    time.sleep(1)
                    st.rerun()
                    
        # エクスポート機能
        csv = display_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 表示中のデータをCSVダウンロード", data=csv, file_name="kakeibo_export.csv", mime="text/csv")
        
        st.divider()
        st.subheader("✏️ 手動で追加")
        with st.form("manual_add"):
            m_date = st.date_input("日付")
            m_amount = st.number_input("金額(円)", min_value=0, step=100)
            m_cat = st.selectbox("カテゴリ", custom_categories)
            m_store = st.text_input("店舗（任意）")
            m_content = st.text_input("内容（任意）")
            if st.form_submit_button("追加", type="primary"):
                add_manual_transaction(m_date.strftime('%Y-%m-%d'), m_amount, m_store, m_content, m_cat)
                st.success("追加しました！")
                st.rerun()
    else:
        st.info("データがありません。")

### ⬆️ CSVアップロード ###
with tabs[2]:
    st.header("履歴の取り込み")
    st.write("PayPayアプリから出力したCSVファイルをアップロードしてください。")
    
    uploaded_files = st.file_uploader("CSVファイルを選択 (複数可)", type=['csv'], accept_multiple_files=True)
    
    if st.button("CSVから読み込み", type="primary") and uploaded_files:
        with st.spinner("AIがカテゴリを推測しています...⏳"):
            all_dfs = []
            for file in uploaded_files:
                parsed_df, err = parse_paypay_csv(file)
                if err:
                    st.error(f"{file.name}: {err}")
                elif parsed_df is not None:
                    all_dfs.append(parsed_df)
            
            if all_dfs:
                combined_df = pd.concat(all_dfs, ignore_index=True)
                # AI分類 (時間かかる可能性あり)
                categorized_df, ai_err = categorize_transactions(combined_df)
                if ai_err:
                    st.warning(ai_err)
                
                st.session_state.temp_df = categorized_df
                st.success("読み込みと推論が完了しました。下で確認して保存してください。")
            
    if st.session_state.temp_df is not None:
        df = st.session_state.temp_df
        
        if df.empty:
            st.success("🎉 すべての明細の確認と保存が完了しました！")
            st.session_state.temp_df = None
            if st.button("OK"):
                st.rerun()
        else:
            st.subheader(f"🤖 AIプレビュー (残り {len(df)} 件)")
            st.info("確認して「良い」か「修正」を選んでください。")
            
            if st.button("✅ すべて「良い」として一括確定する", type="primary", use_container_width=True):
                df['user_confirmed'] = True
                inserted = save_transactions(df)
                for _, row in df.iterrows():
                    update_transaction_category_rule_only(row['store'], row['category'])
                st.success(f"{inserted} 件のデータを保存しました！")
                st.session_state.temp_df = None
                time.sleep(1)
                st.rerun()
                
            st.divider()
            
            # 各データをカード型で表示
            for idx, row in df.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{row['date']}**　<span style='font-size:1.2em; font-weight:bold; color:{THEME_COLOR_PRIMARY};'>{row['amount']:,}円</span>", unsafe_allow_html=True)
                    st.markdown(f"🛍️ **{row['store']}**　🏷️ **{row['category']}**")
                    
                    if row.get('ai_reason'):
                        st.caption(f"💡 AIの判断理由: {row['ai_reason']}")
                        
                    # 縦並びのボタン
                    if st.button("✅ この判断で良い", key=f"good_{idx}", type="primary", use_container_width=True):
                        row_to_save = df.loc[[idx]].copy()
                        row_to_save['user_confirmed'] = True
                        save_transactions(row_to_save)
                        update_transaction_category_rule_only(row['store'], row['category'])
                        st.session_state.temp_df = df.drop(idx)
                        st.rerun()
                        
                    if st.button("✏️ 修正", key=f"edit_{idx}", use_container_width=True):
                        edit_category_dialog(idx, row['store'], row['amount'], row['date'], row['category'])

### ⚙️ 設定・予算 ###
with tabs[3]:
    st.header("予算管理")
    # 年月の選択肢を生成（前後半年分）
    from dateutil.relativedelta import relativedelta
    base_m = date.today().replace(day=1)
    month_options = [(base_m + relativedelta(months=i)).strftime('%Y-%m') for i in range(-6, 7)]
    
    default_m_str = get_month_str(date.today())
    if default_m_str not in month_options:
        month_options.append(default_m_str)
    month_options.sort()
    
    def_idx = month_options.index(default_m_str)
    month_str = st.selectbox("設定する年月", month_options, index=def_idx)
    
    st.write(f"**{month_str}** のカテゴリ予算設定")
    
    current_budgets = get_budgets(month_str)
    
    with st.form("budget_form"):
        new_budgets = {}
        for cat in custom_categories:
            def_val = current_budgets.get(cat, 0)
            new_budgets[cat] = st.number_input(f"{cat} (円)", min_value=0, value=int(def_val), step=1000)
            
        if st.form_submit_button("予算を保存", type="primary"):
            for cat, amt in new_budgets.items():
                save_budget(month_str, cat, amt)
            st.success("予算を保存しました！")

    st.divider()
    st.subheader("📝 カテゴリの追加")
    st.write("新しいカテゴリを追加できます。（※追加後はアプリがリロードされます）")
    with st.form("add_cat_form"):
        new_cat_name = st.text_input("新しいカテゴリ名")
        if st.form_submit_button("追加する"):
            if new_cat_name and new_cat_name.strip() not in custom_categories:
                add_custom_category(new_cat_name.strip())
                st.success(f"「{new_cat_name}」を追加しました！")
                st.rerun()
            elif new_cat_name.strip() in custom_categories:
                st.warning("すでに存在するカテゴリです。")

