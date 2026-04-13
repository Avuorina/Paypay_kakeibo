import plotly.express as px
from config import DEFAULT_CATEGORIES, THEME_COLOR_PRIMARY, THEME_COLOR_SECONDARY, THEME_COLOR_BACKGROUND

def create_pie_chart(df):
    """
    データフレームからカテゴリ別のExpenditure円グラフを作成。
    """
    grouped = df.groupby('category')['amount'].sum().reset_index()
    
    # 0円のカテゴリは除外
    grouped = grouped[grouped['amount'] > 0]
        
    if grouped.empty:
        return None
        
    fig = px.pie(
        grouped, 
        values='amount', 
        names='category', 
        hole=0.4,
        color_discrete_sequence=px.colors.sequential.Oranges_r
    )
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#FAFAFA" if THEME_COLOR_BACKGROUND == "#1E1E1E" else "#333333")
    )
    
    return fig

def create_custom_css():
    """
    Streamlit用のカスタムCSS (スマホ向けレイアウト調整、オレンジ基調)
    """
    return f"""
    <style>
    /* 全体の背景・テキスト色（Streamlitのベース設定に上書き） */
    .stApp {{
        background-color: {THEME_COLOR_BACKGROUND};
    }}
    
    /* タブのスタイリング（モバイルで押しやすく） */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        overflow-x: auto;
    }}
    .stTabs [data-baseweb="tab"] {{
        padding: 10px 16px;
        white-space: nowrap;
        border-radius: 8px 8px 0 0;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {THEME_COLOR_PRIMARY};
        color: white !important;
    }}
    
    /* 統計指標(Metric)のデザイン */
    [data-testid="stMetricValue"] {{
        color: {THEME_COLOR_PRIMARY};
        font-weight: bold;
        font-size: 2rem !important;
    }}
    
    /* ボタンの共通スタイリング（押しやすく） */
    .stButton > button {{
        width: 100%;
        border-radius: 8px;
        min-height: 48px;
    }}
    
    /* Primaryボタン */
    .stButton > button[kind="primary"] {{
        background-color: {THEME_COLOR_PRIMARY};
        color: white;
        border: none;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {THEME_COLOR_SECONDARY};
    }}
    
    /* エキスパンダーのヘッダー */
    .streamlit-expanderHeader {{
        font-weight: bold;
    }}
    </style>
    """
