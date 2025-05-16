"""
Daily Values Journal – No‑Dependency Auth
========================================
A Streamlit app for private journaling and value tracking.  
Uses **only built‑in Streamlit widgets + SQLite + bcrypt** for authentication—no external auth library that might break.

Features
--------
* **Register / log in** (bcrypt‑hashed passwords stored locally)  
* **Add journal entry** – tag with values, rate each 0‑99  
* **Dashboard** – average rating per value for last 1/7/30 days or all time  
* Each user sees **only their own** data  

Install & run
-------------
```bash
python3 -m venv venv && source venv/bin/activate
pip install streamlit pandas bcrypt
streamlit run value_tracker.py
```
A default account **demo / demo** is created automatically if no users exist.
"""

from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
import pandas as pd
import streamlit as st

###############################################################################
# Config
###############################################################################
DB_PATH = "values_journal.db"
USERS_TABLE = "users"

VALUE_OPTIONS = [
    'Connection', 'Interpersonal Harmony', 'Collaboration', 'Community', 'Integrity',
    'Honesty', 'Perseverance', 'Self-control', 'Benevolence', 'Justice', 'Patriotism',
    'Family', 'Tradition', 'Conformity', 'Power', 'Duty', 'Activism', 'Internal Peace',
    'Health', 'Wealth', 'Status', 'Luxury', 'Success', 'Pleasure', 'Environmentalism',
    'Spirituality', 'Diversity', 'Equality', 'Wisdom', 'Autonomy', 'Stability', 'Safety',
    'Drive', 'Creativity', 'Stimulation', 'Competency', 'Growth'
]

###############################################################################
# Database helpers
###############################################################################

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def _ensure_column(cur, table: str, column_def: str):
    """Add *column_def* to *table* if it doesn't already exist."""
    name = column_def.split()[0]
    cols = [row[1] for row in cur.execute(f"PRAGMA table_info({table})")]  # colname at idx 1
    if name not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Users
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {USERS_TABLE} (
        username TEXT PRIMARY KEY,
        pwd_hash TEXT NOT NULL
    )""")

    # Entries
    cur.execute("""CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        text TEXT NOT NULL
    )""")
    # Ensure newer columns exist (username)
    _ensure_column(cur, "entries", "username TEXT")

    # Tags
    cur.execute("""CREATE TABLE IF NOT EXISTS tags (
        entry_id INTEGER,
        value TEXT,
        rating INTEGER
    )""")
    # Ensure FK columns if DB created early
    _ensure_column(cur, "tags", "rating INTEGER")
    _ensure_column(cur, "tags", "value TEXT")

    conn.commit()

    # Ensure default demo user
    if not cur.execute(f"SELECT 1 FROM {USERS_TABLE} LIMIT 1").fetchone():
        demo_hash = bcrypt.hashpw(b"demo", bcrypt.gensalt()).decode()
        cur.execute(f"INSERT INTO {USERS_TABLE} (username, pwd_hash) VALUES (?, ?)", ("demo", demo_hash))
        conn.commit()
    conn.close()

###############################################################################
# Auth helpers
###############################################################################

def verify_user(username: str, password: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute(f"SELECT pwd_hash FROM {USERS_TABLE} WHERE username=?", (username,)).fetchone()
    conn.close()
    if not row:
        return False
    return bcrypt.checkpw(password.encode(), row[0].encode())


def register_user(username: str, password: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"INSERT INTO {USERS_TABLE} (username, pwd_hash) VALUES (?, ?)",
                    (username, bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

###############################################################################
# Entry CRUD
###############################################################################

def add_entry(user: str, text: str, ratings: dict[str, int]):
    conn = get_conn()
    cur = conn.cursor()
    ts = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO entries (ts, username, text) VALUES (?,?,?)", (ts, user, text))
    entry_id = cur.lastrowid
    for val, rating in ratings.items():
        cur.execute("INSERT INTO tags (entry_id, value, rating) VALUES (?,?,?)", (entry_id, val, rating))
    conn.commit()
    conn.close()
    st.cache_data.clear()


def load_user_data(user: str):
    conn = get_conn()
    entries = pd.read_sql_query("SELECT * FROM entries WHERE username=?", conn, params=(user,), parse_dates=["ts"])
    tags = pd.read_sql_query("SELECT * FROM tags WHERE entry_id IN (SELECT id FROM entries WHERE username=?)", conn, params=(user,))
    conn.close()
    return entries, tags

###############################################################################
# UI: Auth screens
###############################################################################

def auth_sidebar():
    st.sidebar.header("Account")
    if "user" not in st.session_state:
        login_tab, register_tab = st.sidebar.tabs(["Login", "Register"])
        with login_tab:
            u = st.text_input("Username", key="login_user")
            p = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Login"):
                if verify_user(u, p):
                    st.session_state.user = u
                    st.success("Logged in!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        with register_tab:
            nu = st.text_input("New username", key="reg_user")
            np = st.text_input("New password", type="password", key="reg_pwd")
            if st.button("Register"):
                if register_user(nu, np):
                    st.success("User created. You can log in now.")
                else:
                    st.error("Username already exists")
    else:
        st.sidebar.markdown(f"**Logged in as {st.session_state.user}**")
        if st.sidebar.button("Logout"):
            st.session_state.clear()
            st.rerun()

###############################################################################
# UI pages (require login)
###############################################################################

def page_add(user: str):
    st.subheader("New Journal Entry")
    text = st.text_area("Entry text", height=200)
    chosen = st.multiselect("Tag with values", VALUE_OPTIONS)
    ratings = {val: st.slider(val, 0, 99, 50, key=val) for val in chosen}
    if st.button("Save") and text.strip():
        add_entry(user, text, ratings)
        st.success("Saved!")
        st.rerun()


def page_dashboard(user: str):
    entries, tags = load_user_data(user)
    if entries.empty:
        st.info("No entries yet – add one first!")
        return
    window = st.selectbox("Window", ("Last 1 day", "Last 7 days", "Last 30 days", "All time"))
    now = datetime.utcnow()
    if window == "Last 1 day":
        start = now - timedelta(days=1)
    elif window == "Last 7 days":
        start = now - timedelta(days=7)
    elif window == "Last 30 days":
        start = now - timedelta(days=30)
    else:
        start = entries["ts"].min()
    recent_entries = entries[entries["ts"] >= pd.Timestamp(start)]
    recent_tags = tags[tags["entry_id"].isin(recent_entries["id"])]
    if recent_tags.empty:
        st.info("No tagged values in selected window.")
        return
    recent_tags["rating"].fillna(50, inplace=True)
    agg = recent_tags.groupby("value")["rating"].mean().round(1).sort_values(ascending=False)
    st.bar_chart(agg)
    st.dataframe(agg.rename("avg_rating"))

###############################################################################
# Main
###############################################################################

init_db()
auth_sidebar()

if "user" in st.session_state:
    st.title("Daily Values Journal – Private")
    page = st.sidebar.radio("Navigate", ("Add entry", "Dashboard"))
    if page == "Add entry":
        page_add(st.session_state.user)
    else:
        page_dashboard(st.session_state.user)
else:
    st.title("Please log in or register")
