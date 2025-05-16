
"""
Value Journal Tracker
---------------------
Streamlit app for journaling daily entries tagged with personal values.

Features
========
1. **Add Entry** – write text, pick values, give each a 0-99 strength.
2. **Dashboard** – see which values were most salient in the last day/week/month.

Run
---
```bash
pip install streamlit pandas
streamlit run value_tracker.py
```
"""

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "values_journal.db"

VALUE_OPTIONS = [
    'Connection', 'Interpersonal Harmony', 'Collaboration', 'Community', 'Integrity',
    'Honesty', 'Perseverance', 'Self-control', 'Benevolence', 'Justice', 'Patriotism',
    'Family', 'Tradition', 'Conformity', 'Power', 'Duty', 'Activism', 'Internal Peace',
    'Health', 'Wealth', 'Status', 'Luxury', 'Success', 'Pleasure', 'Environmentalism',
    'Spirituality', 'Diversity', 'Equality', 'Wisdom', 'Autonomy', 'Stability', 'Safety',
    'Drive', 'Creativity', 'Stimulation', 'Competency', 'Growth'
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
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


def add_entry(entry_text: str, value_ratings: dict):
    """Insert a journal entry plus its value tags."""
    ts = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO entries (ts, text) VALUES (?, ?)", (ts, entry_text))
    entry_id = cur.lastrowid
    for value, rating in value_ratings.items():
        cur.execute(
            "INSERT INTO tags (entry_id, value, rating) VALUES (?, ?, ?)",
            (entry_id, value, rating)
        )
    conn.commit()
    conn.close()

    # Invalidate Streamlit cache so next run sees fresh data
    st.cache_data.clear()


@st.cache_data(show_spinner=False, ttl=0)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    entries = pd.read_sql_query("SELECT * FROM entries", conn, parse_dates=['ts'])
    tags = pd.read_sql_query("SELECT * FROM tags", conn)
    conn.close()
    return entries, tags


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
        start_ts = entries['ts'].min()

    recent_entries = entries[entries['ts'] >= pd.Timestamp(start_ts)]
    recent_tags = tags[tags['entry_id'].isin(recent_entries['id'])]

    if recent_tags.empty:
        st.info("No tagged values in the selected period.")
        return

    recent_tags['rating'].fillna(50, inplace=True)
    agg = (recent_tags.groupby('value')['rating']
           .mean()
           .round(1)
           .sort_values(ascending=False))

    st.subheader("Average value rating (higher = more salient)")
    st.bar_chart(agg)
    st.dataframe(agg.rename("avg_rating"))


def entry_form():
    st.subheader("New Journal Entry")
    entry_text = st.text_area("Write your entry", height=200)
    selected_values = st.multiselect("Tag with values", VALUE_OPTIONS)

    ratings = {}
    if selected_values:
        st.write("Rate how strongly each value featured (0-99):")
        for val in selected_values:
            ratings[val] = st.slider(val, 0, 99, 50, key=val)

    if st.button("Save Entry") and entry_text.strip():
        add_entry(entry_text, ratings)
        st.success("Entry saved!")
        st.rerun()


def main():
    st.title("Daily Values Journal")

    menu = st.sidebar.radio("Navigate", ("Add entry", "Dashboard"))

    if menu == "Add entry":
        entry_form()
    else:
        dashboard()


if __name__ == "__main__":
    init_db()
    main()
