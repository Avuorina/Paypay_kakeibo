import os
import pandas as pd
from datetime import datetime
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import text
from config import DB_NAME, DEFAULT_CATEGORIES

Base = declarative_base()

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    store = Column(String)
    content = Column(String)
    category = Column(String)
    user_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (UniqueConstraint('date', 'amount', 'store', 'content', name='uix_transaction_1'),)

class CategoryRule(Base):
    __tablename__ = 'category_rules'
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)

class Budget(Base):
    __tablename__ = 'budgets'
    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(String, nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('month', 'category', name='uix_budget_1'),)

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)


@st.cache_resource
def get_engine():
    db_url = None
    try:
        # Streamlit上のsecrets
        db_url = st.secrets.get("SUPABASE_DB_URL")
    except Exception:
        pass
        
    if not db_url:
        # ローカル環境変数
        db_url = os.environ.get("SUPABASE_DB_URL")
        
    if db_url and "postgres://" in db_url and "..." not in db_url:
        # PostgresURLの場合の調整
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    elif db_url and "postgresql://" in db_url and "..." not in db_url:
        return create_engine(db_url)
    else:
        # ローカルSQLite
        return create_engine(f"sqlite:///{DB_NAME}", connect_args={"check_same_thread": False})

def get_session():
    engine = get_engine()
    SessionMaker = sessionmaker(bind=engine)
    return SessionMaker()

def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    
    with get_session() as session:
        # 既存カテゴリがなければconfigから初期化
        count = session.query(Category).count()
        if count == 0:
            for cat in DEFAULT_CATEGORIES:
                session.add(Category(name=cat))
            session.commit()

def save_transactions(df):
    """DataFrameのデータをDBに保存する"""
    records_inserted = 0
    with get_session() as session:
        for _, row in df.iterrows():
            d_date = row['date']
            d_amount = row['amount']
            d_store = row.get('store', '')
            d_content = row.get('content', '')
            
            exists = session.query(Transaction).filter_by(
                date=d_date, amount=d_amount, store=d_store, content=d_content
            ).first()
            
            if not exists:
                tx = Transaction(
                    date=d_date,
                    amount=d_amount,
                    store=d_store,
                    content=d_content,
                    category=row.get('category', 'その他'),
                    user_confirmed=row.get('user_confirmed', False)
                )
                session.add(tx)
                records_inserted += 1
            else:
                # 存在する場合はカテゴリなどを上書きする可能性があるためオプション対応
                if row.get('user_confirmed'):
                    exists.category = row.get('category', exists.category)
                    exists.user_confirmed = True
        session.commit()
    return records_inserted

def get_all_transactions():
    engine = get_engine()
    # ORMではなく直接SQL文字列で取得してPandasのDataFrameにする方がStreamlitで扱いやすい
    df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC", engine)
    return df

def update_transaction_category(tx_id, new_category):
    with get_session() as session:
        tx = session.query(Transaction).filter_by(id=tx_id).first()
        if tx:
            tx.category = new_category
            tx.user_confirmed = True
            
            store_name = tx.store
            if store_name:
                rule = session.query(CategoryRule).filter_by(keyword=store_name).first()
                if rule:
                    rule.category = new_category
                else:
                    session.add(CategoryRule(keyword=store_name, category=new_category))
        session.commit()

def delete_transaction(tx_id):
    with get_session() as session:
        tx = session.query(Transaction).filter_by(id=tx_id).first()
        if tx:
            session.delete(tx)
            session.commit()

def add_manual_transaction(date, amount, store, content, category):
    with get_session() as session:
        tx = Transaction(
            date=date,
            amount=amount,
            store=store,
            content=content,
            category=category,
            user_confirmed=True
        )
        session.add(tx)
        session.commit()

def get_category_rules():
    with get_session() as session:
        rules = {r.keyword: r.category for r in session.query(CategoryRule).all()}
    return rules

def get_budgets(month):
    with get_session() as session:
        budgets = {b.category: b.amount for b in session.query(Budget).filter_by(month=month).all()}
    return budgets

def save_budget(month, category, amount):
    with get_session() as session:
        b = session.query(Budget).filter_by(month=month, category=category).first()
        if b:
            b.amount = amount
        else:
            session.add(Budget(month=month, category=category, amount=amount))
        session.commit()

def get_custom_categories():
    with get_session() as session:
        cats = [c.name for c in session.query(Category).order_by(Category.id).all()]
    if not cats:
        return DEFAULT_CATEGORIES
    return cats

def add_custom_category(name):
    with get_session() as session:
        cat = session.query(Category).filter_by(name=name).first()
        if not cat:
            session.add(Category(name=name))
            session.commit()

def update_transaction_category_rule_only(store, new_category):
    if store and str(store).strip():
        with get_session() as session:
            s_name = str(store).strip()
            rule = session.query(CategoryRule).filter_by(keyword=s_name).first()
            if rule:
                rule.category = new_category
            else:
                session.add(CategoryRule(keyword=s_name, category=new_category))
            session.commit()

# 初期化実行
if __name__ == "__main__":
    init_db()
