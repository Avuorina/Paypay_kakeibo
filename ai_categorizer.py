import google.generativeai as genai
import json
import time
from config import GEMINI_API_KEY, DEFAULT_CATEGORIES
from database import get_category_rules, get_custom_categories

def init_gemini():
    if not GEMINI_API_KEY:
        return False
    genai.configure(api_key=GEMINI_API_KEY)
    return True

def categorize_transactions(df):
    """
    データフレームのトランザクションに対して、AI（とルール）を使ってカテゴリを推論する。
    戻り値: (補完されたDataFrame, エラーメッセージ)
    """
    if df.empty:
        return df, None
        
    rules = get_category_rules()
    
    # カテゴリ列と推論理由列を初期化
    if 'category' not in df.columns:
        df['category'] = 'その他'
    df['ai_reason'] = ''
    df['user_confirmed'] = False
    
    # 未分類かつルールにヒットしないもののリスト
    to_predict = []
    
    for idx, row in df.iterrows():
        store = str(row.get('store', '')).strip()
        
        # ルールにヒットするかチェック
        if store and store in rules:
            df.at[idx, 'category'] = rules[store]
            df.at[idx, 'ai_reason'] = '過去の学習（ルール一致）'
            df.at[idx, 'user_confirmed'] = True # ルールによるものは確定済みとするか要検討（ここでは未確定としておき後でまとめて保存の対象から外すなどの処理も可能）
        else:
            # AI予測対象
            to_predict.append({
                'id': idx,
                'store': store,
                'content': str(row.get('content', '')).strip(),
                'amount': row['amount']
            })

    # AI予測対象がなければ終了
    if not to_predict:
        return df, None
        
    if not init_gemini():
        for item in to_predict:
            df.at[item['id'], 'ai_reason'] = 'APIキー未設定'
        return df, "Gemini APIキーが設定されていません。手動でカテゴリを選択してください。"

    custom_categories = get_custom_categories()

    # プロンプトの構築（JSONで返すように指示）
    system_instruction = f"""
あなたは日本の優秀な家計簿アシスタントです。
以下のカテゴリリストの中から、提供された支払いデータに最も適切なカテゴリを1つ選び、JSON形式で返答してください。
判断が難しい場合は「その他」を選択してください。

【カテゴリリスト】
{', '.join(custom_categories)}

【出力JSONの形式】
[
    {{"id": <入力ID>, "category": "<カテゴリ名>", "reason": "<10文字以内の短い理由>"}}
]
"""
    
    # バッチサイズを区切る（一気に送りすぎるとエラーになる可能性があるため）
    batch_size = 30
    error_msg = None
    
    # モデルのフォールバックリスト（無料枠や制限に引っ掛かった場合を考慮）
    models_to_try = ['gemini-2.5-flash-lite', 'gemini-flash-lite-latest', 'gemini-2.0-flash-lite', 'gemini-2.5-flash']
    
    for i in range(0, len(to_predict), batch_size):
        batch = to_predict[i:i+batch_size]
        input_data = json.dumps(batch, ensure_ascii=False)
        
        success = False
        last_error = None
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    f"{system_instruction}\n\n【入力データ】\n{input_data}",
                    generation_config=genai.types.GenerationConfig(
                        response_mime_type="application/json",
                    )
                )
                success = True
                break # 成功したら内側のモデルループを抜ける
            except Exception as e:
                last_error = e
                # エラーが出たら次のモデルを試す
                continue
                
        if not success:
            error_msg = f"AI推論中にエラーが発生しました（全モデル失敗）: {str(last_error)}"
            for item in batch:
                df.at[item['id'], 'category'] = 'その他'
                df.at[item['id'], 'ai_reason'] = 'AI制限エラー'
            break
            
        try:
            result_json = json.loads(response.text)
            for res in result_json:
                idx = res.get('id')
                cat = res.get('category', 'その他')
                reason = res.get('reason', '')
                
                if cat not in custom_categories:
                    cat = 'その他'
                    
                if idx in df.index:
                    df.at[idx, 'category'] = cat
                    df.at[idx, 'ai_reason'] = reason
                    df.at[idx, 'user_confirmed'] = False # AIの予測はユーザー確認待ち
            
        except Exception as e:
            error_msg = f"AI推論中にエラーが発生しました: {str(e)}"
            for item in batch:
                df.at[item['id'], 'category'] = 'その他'
                df.at[item['id'], 'ai_reason'] = 'AIエラー'
            break
            
        # API制限の簡易回避
        time.sleep(1)

    return df, error_msg

