"""
Daily Values Journal – Private & Complete
========================================
A Streamlit app with local bcrypt‑based auth.
Pages:
1. **Add entry** – write and tag journal entries.
2. **Dashboard** – average value ratings per timeframe.
3. **Value definitions** – glossary of all core values.

Run
---
```bash
python3 -m venv venv && source venv/bin/activate
pip install streamlit pandas bcrypt
streamlit run value_tracker.py
```
Default credentials: **demo / demo**
"""

from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
import pandas as pd
import streamlit as st
import textwrap

DB_PATH = "values_journal.db"
USERS_TABLE = "users"

# ---------------------- Value glossary ----------------------
VALUES = {
    "Connection": "Valuing connection means prioritizing relationships and genuine interactions with others. It involves actively nurturing and appreciating emotional ties, communication, and mutual support in a variety of contexts in one's life.",
    "Interpersonal Harmony": "Valuing interpersonal harmony means prioritizing peaceful and respectful relationships, often striving to avoid conflict and foster understanding among individuals. It involves being considerate of others' feelings and perspectives to maintain a positive social environment.",
    "Collaboration": "Valuing collaboration means recognizing and appreciating the importance of working together with others to achieve common goals, leveraging diverse skills and perspectives. It involves fostering a culture of communication, mutual respect, and shared responsibility to enhance collective effectiveness and innovation.",
    "Community": "Valuing community means recognizing and prioritizing the importance of collective well-being, mutual support, and shared goals over individual interests. It involves actively contributing to and participating in communal activities and initiatives that enhance the collective quality of life.",
    "Integrity": "Valuing integrity means prioritizing ethical behavior and strong moral principles above all other considerations. It involves consistently adhering to moral principles, even when it is challenging or inconvenient.",
    "Honesty": "Valuing honesty means prioritizing truthfulness even when it is difficult or inconvenient. It involves being transparent and trustworthy regardless of the consequences.",
    "Perseverance": "Valuing perseverance means appreciating the importance of persistent effort and resilience in the face of challenges, rather than giving up. It involves consistently striving towards goals despite obstacles, setbacks, and delays.",
    "Self-control": "Valuing self-control means prioritizing the ability to regulate one's behaviors, thoughts, and emotions in the face of temptations and impulses. It involves making conscious choices that align with long-term goals rather than succumbing to immediate gratifications.",
    "Benevolence": "Valuing benevolence means prioritizing kindness, compassion, and goodwill towards others in your actions and decisions. It involves a genuine desire to contribute positively to the well-being of individuals and society.",
    "Justice": "Valuing Justice means prioritizing fairness in all actions and decisions, ensuring that laws and actions are applied impartially. It involves a commitment to addressing and rectifying injustices in society, fostering a culture of accountability and ethical behavior.",
    "Patriotism": "Valuing patriotism means holding a deep respect and love for one's country, including its cultural heritage, values, and principles. It also involves a commitment to the nation's well-being and active participation in civic duties to support and improve the country.",
    "Family": "Valuing family means prioritizing the principles, traditions, and responsibilities that uphold the well-being and unity of the family unit. It involves fostering strong relationships, mutual respect, and commitment to supporting and caring for one another.",
    "Tradition": "Valuing tradition means appreciating and preserving customs, beliefs, and practices passed down through generations. It involves recognizing the importance of cultural heritage and maintaining continuity with the past.",
    "Conformity": "Valuing conformity means prioritizing adherence to social norms, rules, and expectations, often to maintain harmony and cohesion within a group. It emphasizes the importance of fitting in and aligning one's behavior and beliefs with those of the majority or authority.",
    "Power": "Valuing power means prioritizing the ability to influence, lead, and command people and situations. It often involves seeking positions or taking actions that enhance one's capacity to shape outcomes, exert influence, and assert one's authority.",
    "Duty": "Valuing duty means prioritizing the responsibilities and obligations of one's role, even when it requires personal sacrifices. It involves readiness to commit oneself to a goal which extends beyond their own personal goals.",
    "Activism": "Valuing activism means appreciating efforts to advocate for social, political, or environmental change. It involves recognizing the personal responsiblity one has in taking action to shape one's society.",
    "Internal Peace": "Valuing internal peace means prioritizing a harmonious and balanced inner state, free from internal conflict and turmoil. It involves cultivating a mindset and lifestyle that promote mental clarity, self-acceptance, and harmony, regardless of external chaos or challenges.",
    "Health": "Valuing health means prioritizing physical, mental, and emotional well-being through practices such as regular exercise, balanced nutrition, and stress management. It also involves making informed choices that promote long-term vitality and prevent illness.",
    "Wealth": "Valuing wealth means prioritizing the accumulation and preservation of financial assets and resources. It often involves making decisions that aim to enhance one's economic standing and viewing monetary success as a key indicator of personal achievement and security.",
    "Luxury": "Valuing luxury means appreciating and seeking high-quality, premium goods and experiences that often come with a significant cost. It emphasizes a preference for exclusivity, craftsmanship, and indulgence, often as a marker of status or personal reward.",
    "Success": "Valuing success means prioritizing achievements as a central aspect of one's life, often measuring well-being and self-worth through accomplishments. It entails a strong focus on attaining specific outcomes and recognizing the hard work, determination, and perseverance required to reach them.",
    "Pleasure": "Valuing pleasure means prioritizing experiences and activities that bring enjoyment and satisfaction. It involves seeking out and cherishing moments of joy and comfort while often aiming to minimize pain and discomfort.",
    "Environmentalism": "Valuing environmentalism means prioritizing the protection and preservation of the natural world, recognizing its intrinsic worth and the necessity of sustainable practices for the health of our planet. It involves advocating for policies and behaviors that reduce environmental impact, conserve resources, and promote biodiversity.",
    "Spirituality": "Valuing spirituality means prioritizing inner growth via a connection to something greater than oneself, such as a higher power or universal consciousness. It involves seeking meaning, purpose, and a sense of peace through practices like meditation, prayer, or self-reflection.",
    "Diversity": "Valuing diversity means appreciating and respecting the differences between people, including differences in backgrounds, perspectives, and abilities. It also involves actively promoting an inclusive culture where people feel empowered to contribute their unique strengths.",
    "Equality": "Valuing equality means recognizing and promoting the fair treatment and opportunities for all individuals, regardless of their differences such as race, gender, socioeconomic status, or other characteristics. It involves actively challenging and addressing systemic inequities and biases to ensure everyone has an equal chance to succeed and thrive.",
    "Wisdom": "Valuing wisdom means prioritizing the pursuit of insight, discernment, and sound judgment in decision-making and life choices. It involves seeking knowledge and experiences that foster personal growth, ethical behavior, and the well-being of oneself and others.",
    "Autonomy": "Valuing autonomy means prioritizing and respecting an individual's right to make their own decisions and govern their own actions. It emphasizes the importance of independence and self-determination in one's personal and professional life.",
    "Stability": "Valuing stability means prioritizing consistency, reliability, and predictability in various aspects of life, such as personal relationships, professional environments, and financial situations. It involves seeking environments and decisions that minimize risk and uncertainty to ensure a steady, predictable course of action.",
    "Safety": "Valuing safety means prioritizing the protection of oneself, one's loved ones, and one's community from harm. It involves continuously assessing and mitigating potential dangers to promote well-being and peace of mind.",
    "Drive": "Valuing drive means appreciating the determination and motivation that propel individuals to achieve challenging goals. It means placing high importance on perseverance, ambition, and the proactive pursuit of success in personal and professional endeavors.",
    "Creativity": "Valuing creativity means recognizing and appreciating the importance of original thinking and innovation. It involves recognizing the role of thinking out of the box in fostering progress, and enriching various aspects of life.",
    "Stimulation": "Valuing stimulation means seeking out experiences that are exciting, novel, and challenging. It reflects a desire for variety and dynamic activities that keep life interesting.",
    "Competency": "Valuing competency means prioritizing and appreciating skills, expertise, and the ability to perform tasks effectively and efficiently. It involves respecting individuals who demonstrate proficiency in their respective fields and consistently seeking to acquire mastery in one's own pursuits.",
    "Growth": "Valuing growth means prioritizing continuous personal and professional development, striving to improve in all domains of life. It involves embracing challenges, learning from experiences, and seeking opportunities for advancement."
}
VALUE_OPTIONS = list(VALUES.keys())

# ------------------ DB helpers ------------------

def conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def ensure_schema():
    c = conn(); cur = c.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {USERS_TABLE} (username TEXT PRIMARY KEY, pwd_hash TEXT NOT NULL)")
    cur.execute("CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, text TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS tags (entry_id INTEGER, value TEXT, rating INTEGER)")
    # add missing columns
    for table, col in [("entries", "username TEXT"), ("tags", "value TEXT"), ("tags", "rating INTEGER")]:
        colname = col.split()[0]
        existing = [r[1] for r in cur.execute(f"PRAGMA table_info({table})")]
        if colname not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col}")
    # demo user
    if not cur.execute(f"SELECT 1 FROM {USERS_TABLE} LIMIT 1").fetchone():
        cur.execute(f"INSERT INTO {USERS_TABLE} VALUES (?,?)", ("demo", bcrypt.hashpw(b"demo", bcrypt.gensalt()).decode()))
    c.commit(); c.close()

# ------------------ Auth helpers ------------------

def verify(u,p):
    row = conn().execute(f"SELECT pwd_hash FROM {USERS_TABLE} WHERE username=?",(u,)).fetchone()
    return bool(row and bcrypt.checkpw(p.encode(), row[0].encode()))

def register(u,p):
    try:
        conn().execute(f"INSERT INTO {USERS_TABLE} VALUES (?,?)", (u, bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode())); conn().commit(); return True
    except sqlite3.IntegrityError:
        return False

# ------------------ CRUD ------------------

def add_entry(user,text,ratings):
    c=conn();cur=c.cursor();ts=datetime.utcnow().isoformat();cur.execute("INSERT INTO entries (ts,text,username) VALUES (?,?,?)",(ts,text,user));eid=cur.lastrowid
    for v,r in ratings.items():cur.execute("INSERT INTO tags VALUES (?,?,?)",(eid,v,r));c.commit();c.close();st.cache_data.clear()

def load(user):
    c=conn();e=pd.read_sql_query("SELECT * FROM entries WHERE username=?",c,params=(user,),parse_dates=["ts"]);t=pd.read_sql_query("SELECT * FROM tags WHERE entry_id IN (SELECT id FROM entries WHERE username=?)",c,params=(user,));c.close();return e,t

# ------------------ UI ------------------

def sidebar_auth():
    st.sidebar.header("Account")
    if "user" not in st.session_state:
        l_tab,r_tab=st.sidebar.tabs(["Login","Register"])
        with l_tab:
            u=st.text_input("Username",key="l_u");p=st.text_input("Password",type="password",key="l_p");
            if st.button("Login"):
                if verify(u,p):st.session_state.user=u;st.rerun()
                else:st.error("Bad creds")
        with r_tab:
            u=st.text_input("New username",key="r_u");p=st.text_input("New password",type="password",key="r_p");
            if st.button("Register"):
                if register(u,p):st.success("User created");
                else:st.error("Username exists")
    else:
        st.sidebar.success(f"Logged in as {st.session_state.user}")
        if st.sidebar.button("Logout"):st.session_state.clear();st.rerun()

# pages

def page_add(user):
    st.subheader("New Entry");txt=st.text_area("Entry",height=200);chosen=st.multiselect("Values",VALUE_OPTIONS)
    ratings={v:st.slider(v,0,99,50,key=v) for v in chosen}
    if st.button("Save") and txt.strip():add_entry(user,txt,ratings);st.success("Saved");st.rerun()

def page_dash(user):
    e,t=load(user);
    if e.empty:st.info("No entries yet");return
    win=st.selectbox("Window",("Last 1 day","Last 7 days","Last 30 days","All time"));now=datetime.utcnow()
    start={"Last 1 day":now-timedelta(days=1),"Last 7 days":now-timedelta(days=7),"Last 30 days":now-timedelta(days=30),"All time":e["ts"].min()}[win]
    recent=e[e["ts"]>=pd.Timestamp(start)];tag=t[t["entry_id"].isin(recent["id"])]
    if tag.empty:st.info("No tags in window");return
    tag["rating"].fillna(50,inplace=True)
    agg=tag.groupby("value")["rating"].mean().round(1).sort_values(ascending=False)
    st.bar_chart(agg);st.dataframe(agg.rename("avg_rating"))

def page_defs():
    st.subheader("Core Value Definitions")
    for name,desc in VALUES.items():
        st.markdown(f"### {name}\n{textwrap.fill(desc,80)}\n")

# ------------------ Main ------------------
ensure_schema()
sidebar_auth()

if "user" in st.session_state:
    st.title("Daily Values Journal – Private")
    page = st.sidebar.radio("Navigate", ("Add entry","Dashboard","Definitions"))
    if page=="Add entry":page_add(st.session_state.user)
    elif page=="Dashboard":page_dash(st.session_state.user)
    else:page_defs()
else:
    st.title("Please log in or register")
