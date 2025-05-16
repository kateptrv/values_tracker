
"""
Daily Values Journal – **Per-User Version**
========================================
A Streamlit app that lets **each authenticated user** keep a private journal tagged with personal values.

Features
--------
1. **Secure login** (username + password) via *streamlit-authenticator*.
2. **Add Entry** – write text, tag it with one or more core values, rate each 0-99.
3. **Dashboard** – bar-chart of your own values for Last 1 day / 7 days / 30 days / All time.
4. **Data isolation** – each user’s entries live in the same SQLite DB but are filtered by `username`, so no one else can read them.

Run
---
```bash
pip install streamlit pandas streamlit-authenticator pyyaml bcrypt
streamlit run value_tracker.py
```
Default demo credentials → **user:** `demo`  **pass:** `demo`  (edit in code or YAML for production!)
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import streamlit_authenticator as stauth
from pathlib import Path
import yaml

DB_PATH = "values_journal.db"

VALUE_OPTIONS = [
    'Connection', 'Interpersonal Harmony', 'Collaboration', 'Community', 'Integrity',
    'Honesty', 'Perseverance', 'Self-control', 'Benevolence', 'Justice', 'Patriotism',
    'Family', 'Tradition', 'Conformity', 'Power', 'Duty', 'Activism', 'Internal Peace',
    'Health', 'Wealth', 'Status', 'Luxury', 'Success', 'Pleasure', 'Environmentalism',
    'Spirituality', 'Diversity', 'Equality', 'Wisdom', 'Autonomy', 'Stability', 'Safety',
    'Drive', 'Creativity', 'Stimulation', 'Competency', 'Growth'
]

###############################################################################
# Authentication helpers                                                      #
###############################################################################

CRED_FILE = Path("credentials.yaml")

# ---------------------------------------------------------------------------
# If no credentials file exists, create a default demo login (demo/demo)
# ---------------------------------------------------------------------------
if not CRED_FILE.exists():
    demo_config = {
        "credentials": {
            "usernames": {
                "demo": {
                    "email": "demo@example.com",
                    "name": "Demo User",
                    "password": stauth.Hasher(["demo"]).generate()[0],  # hashed
                }
            }
        },
        "cookie": {"expiry_days": 30, "key": "values_journal_cookie"},
        "preauthorized": {"emails": []},
    }
    with CRED_FILE.open("w") as f:
        yaml.dump(demo_config, f)

with CRED_FILE.open() as f:
    config = yaml.safe_load(f)

authenticator = stauth.Authenticate(
    config,
    "values_journal",      # cookie name
    "auth",                # signature key (any string)
    cookie_expiry_days=30,
)

name, auth_status, username = authenticator.login("Login", "sidebar")

if auth_status is False:
    st.error("Username or password is incorrect")
    st.stop()
elif auth_status is None:
    st.warning("Please enter your username and password")
    st.stop()

# If here → authenticated
authenticator.logout("Logout", "sidebar")

###############################################################################
# Database helpers                                                            #
###############################################################################

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Entries table has username column for access control
    cur.execute(
        """CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                username TEXT NOT NULL,
                text TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS tags (
                entry_id INTEGER,
                value TEXT,
                rating INTEGER,
                FOREIGN KEY(entry_id) REFERENCES entries(id)
        )"""
    )
    conn.commit()
    conn.close()


def add_entry(entry_text: str, value_ratings: dict[str, int]):
    """Insert a journal entry plus its value tags for current user."""
    ts = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO entries (ts, username, text) VALUES (?, ?, ?)",
        (ts, username, entry_text),
    )
    entry_id = cur.lastrowid
    for value, rating in value_ratings.items():
        cur.execute(
            "INSERT INTO tags (entry_id, value, rating) VALUES (?, ?, ?)",
            (entry_id, value, rating),
        )
    conn.commit()
    conn.close()
    st.cache_data.clear()   # refresh cached reads


@st.cache_data(show_spinner=False, ttl=0)
def load_data():
    """Return (entries_df, tags_df) for current user only."""
    conn = sqlite3.connect(DB_PATH)
    entries = pd.read_sql_query(
        "SELECT * FROM entries WHERE username = ?", conn, params=(username,), parse_dates=["ts"]
    )
    if entries.empty:
        conn.close()
        return entries, pd.DataFrame(columns=["entry_id", "value", "rating"])

    tags = pd.read_sql_query(
        "SELECT * FROM tags WHERE entry_id IN (SELECT id FROM entries WHERE username = ?)",
        conn,
        params=(username,),
    )
    conn.close()
    return entries, tags

###############################################################################
# UI                                                                          #
###############################################################################

def dashboard():
    entries, tags = load_data()

    if entries.empty:
        st.info("No entries yet – add one first!")
        return

    timeframe = st.selectbox(
        "Choose time window", ("Last 1 day", "Last 7 days", "Last 30 days", "All time")
    )
    now = datetime.utcnow()
    if timeframe == "Last 1 day":
        start_ts = now - timedelta(days=1)
    elif timeframe == "Last 7 days":
        start_ts = now - timedelta(days=7)
    elif timeframe == "Last 30 days":
        start_ts = now - timedelta(days=30)
    else:
        start_ts = entries["ts"].min()

    recent_entries = entries[entries["ts"] >= pd.Timestamp(start_ts)]
    recent_tags = tags[tags["entry_id"].isin(recent_entries["id"])]

    if recent_tags.empty:
        st.info("No tagged values in the selected period.")
        return

    recent_tags["rating"].fillna(50, inplace=True)
    agg = (
        recent_tags.groupby("value")["rating"]
        .mean()
        .round(1)
        .sort_values(ascending=False)
    )

    st.subheader("Average value rating (higher = more salient)")
    st.bar_chart(agg)
    st.dataframe(agg.rename("avg_rating"))


def entry_form():
    st.subheader("New Journal Entry")
    entry_text = st.text_area("Write your entry", height=200)
    selected_values = st.multiselect("Tag with values", VALUE_OPTIONS)

    ratings: dict[str, int] = {}
    if selected_values:
        st.write("Rate how strongly each value featured (0-99):")
        for val in selected_values:
            ratings[val] = st.slider(val, 0, 99, 50, key=val)

    if st.button("Save Entry") and entry_text.strip():
        add_entry(entry_text, ratings)
        st.success("Entry saved!")
        st.rerun()


def main():
    st.title("Daily Values Journal – Private")
    st.markdown(f"**Logged in as:** {name}  ")

    menu = st.sidebar.radio("Navigate", ("Add entry", "Dashboard"))

    if menu == "Add entry":
        entry_form()
    else:
        dashboard()


if __name__ == "__main__":
    init_db()
    main()
