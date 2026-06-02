#!/usr/bin/env python3
"""
WeRSS \u5e7f\u544a\u6587\u7ae0\u81ea\u52a8\u6e05\u7406\u811a\u672c
\u6309 description/title \u8fc7\u6ee4\u5e7f\u544a\u6587\u7ae0\uff0c\u6807\u8bb0\u5220\u9664
\u6b63\u5e38\u65f6\u9759\u9ed8\uff0c\u6709\u5220\u9664\u65f6\u8f93\u51fa\u6458\u8981
"""

import sys, re, sqlite3

DB_PATH = '/home/leo/.hermes/profiles/linus/workspace/we-mp-rss.bak/src/data/db.db'
STATUS_DELETED = 1000

# \u6bcf\u6761\u89c4\u5219\uff1a(mp_id, field, pattern, mode, reason)
# mode: 'eq' = exact match, 're' = regex match
RULES = [
    ("MP_WXS_3862012093", "description", "\u7cbe\u7ec6\u5316\u8fd0\u8425\u5de5\u51772026\u5e74\u4e9a\u9a6c\u900a\u5356\u5bb6\u5fc5\u5907", "eq",
     "\u5e7f\u544a\uff1a\u5de5\u5177\u63a8\u8350"),
    ("MP_WXS_3862012093", "title", r"\u5de5\u5177.*[0-9]+\u9009|\u9009\u4e00", "re",
     "\u5e7f\u544a\uff1a\u5de5\u5177\u9009\u4e00"),
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Fetch non-deleted articles for the target mp
cur.execute("SELECT id, title, description FROM articles WHERE mp_id='MP_WXS_3862012093' AND status != ?", (STATUS_DELETED,))
all_articles = cur.fetchall()

total_deleted = 0
deleted_titles = []

for art_id, title, desc in all_articles:
    matched = False
    reason = ""
    for mp_id, field, pattern, mode, r in RULES:
        val = desc if field == "description" else title
        if mode == "eq":
            if val == pattern:
                matched, reason = True, r
                break
        else:
            if re.search(pattern, val):
                matched, reason = True, r
                break
    if matched:
        cur.execute("UPDATE articles SET status=? WHERE id=?", (STATUS_DELETED, art_id))
        total_deleted += 1
        deleted_titles.append(f"  [{reason}] {title[:55]}")

conn.commit()
conn.close()

if total_deleted > 0:
    print(f"[\u6e05\u7406] \u5171\u5220\u9664 {total_deleted} \u7bc7\u5e7f\u544a\u6587\u7ae0")
    for t in deleted_titles:
        print(t)
else:
    sys.exit(0)
