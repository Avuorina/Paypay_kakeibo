import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

def parse_paypay_csv(file):
    """
    PayPayのCSVファイルを読み込み、必要な列を抽出・整形する。
    出金のみを対象とする。
    """
    try:
        # まずは通常通り読み込み（文字コードはShift-JISかUTF-8のケースが多い）
        try:
            df = pd.read_csv(file, encoding='shift_jis')
        except UnicodeDecodeError:
            file.seek(0)
            df = pd.read_csv(file, encoding='utf-8')
            
        # 必要な列を探す
        # 想定される列名: 日付, 取引先, 内容, 出金, 入金, 잔高など
        
        # 列名を正規化（スペース除去など）
        df.columns = [str(c).strip() for c in df.columns]
        
        date_col = None
        store_col = None
        content_col = None
        withdrawal_col = None
        
        for col in df.columns:
            if not date_col and any(k in col for k in ['日付', '日時', '取引日']):
                date_col = col
            elif not store_col and any(k in col for k in ['取引先', '店舗']):
                store_col = col
            elif not content_col and any(k in col for k in ['内容', '取引内容']):
                content_col = col
            elif not withdrawal_col and any(k in col for k in ['出金', '出金金額']):
                withdrawal_col = col
                
        if not date_col or not withdrawal_col:
            return None, "必要な列（日付、出金）が見つかりませんでした。"
            
        # データ整形
        # 日付フォーマットの統一
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # 出金額の数値化と欠損値処理
        if df[withdrawal_col].dtype == object:
            df[withdrawal_col] = df[withdrawal_col].str.replace(',', '').str.replace('¥', '').str.replace('円', '')
        df[withdrawal_col] = pd.to_numeric(df[withdrawal_col], errors='coerce')
        
        # 出金がある行のみを抽出（入金行は無視）
        df = df[df[withdrawal_col].notna() & (df[withdrawal_col] > 0)]
        
        result_df = pd.DataFrame()
        result_df['date'] = df[date_col]
        result_df['amount'] = df[withdrawal_col].astype(int)
        
        if store_col:
            result_df['store'] = df[store_col].fillna('')
        else:
            result_df['store'] = ''
            
        if content_col:
            result_df['content'] = df[content_col].fillna('')
        else:
            result_df['content'] = ''
            
        # NAを除外
        result_df = result_df.dropna(subset=['date'])
        
        return result_df, None
        
    except Exception as e:
        return None, f"CSVの解析中にエラーが発生しました: {str(e)}"

def get_target_period(base_date=None):
    """
    指定された日付（デフォルトは今日）を基準に、
    「前月25日」〜「当月24日」の期間を返す（デフォルト集計期間）。
    """
    if base_date is None:
        base_date = date.today()
        
    if base_date.day >= 25:
        # 当月25日～翌月24日
        start_date = date(base_date.year, base_date.month, 25)
        end_date = start_date + relativedelta(months=1) - relativedelta(days=1)
    else:
        # 前月25日～当月24日
        end_date = date(base_date.year, base_date.month, 24)
        start_date = end_date - relativedelta(months=1) + relativedelta(days=1)
        
    return start_date, end_date

def get_month_str(date_obj):
    """予算用に月を表す文字列 (YYYY-MM) を取得"""
    if date_obj.day >= 25:
        target_month = date_obj + relativedelta(months=1)
    else:
        target_month = date_obj
    return target_month.strftime('%Y-%m')

