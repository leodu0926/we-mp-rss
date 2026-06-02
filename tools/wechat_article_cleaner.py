#!/usr/bin/env python3
"""
WeRSS \u5e7f\u544a\u6587\u7ae0\u81ea\u52a8\u6e05\u7406\u811a\u672c
\u6309 description/title \u8fc7\u6ee4\u5e7f\u544a\u6587\u7ae0\uff0c\u6807\u8bb0\u5220\u9664
\u6b63\u5e38\u65f6\u9759\u9ed8\uff0c\u6709\u5220\u9664\u65f6\u8f93\u51fa\u6458\u8981
"""

import sys, re, sqlite3, json, os

DB_PATH = '/home/leo/.hermes/profiles/linus/workspace/we-mp-rss.bak/src/data/db.db'
STATUS_DELETED = 1000

# \u89c4\u5219\uff1a(mp_id, field, pattern, mode, reason)
# mode: 'eq' = \u7cbe\u786e\u5339\u914d, 're' = \u6b63\u5219\u5339\u914d
RULES = [
    # ===== \u5927\u5b9d\u7ad9\u5916\u63a8\u5e7f =====
    ("MP_WXS_3862012093", "description", "\u7cbe\u7ec6\u5316\u8fd0\u8425\u5de5\u51772026\u5e74\u4e9a\u9a6c\u900a\u5356\u5bb6\u5fc5\u5907", "eq",
     "\u5e7f\u544a\uff1a\u5de5\u5177\u63a8\u8350"),
    ("MP_WXS_3862012093", "title", "\u5de5\u5177.*[0-9]+\u9009|\u9009\u4e00", "re",
     "\u5e7f\u544a\uff1a\u5de5\u5177\u9009\u4e00"),

    # ===== \u77e5\u4e0d\u8a00 =====
    # \u6df1\u5733\u7ebf\u4e0b\u6d3b\u52a8\u63a8\u5e7f
    ("MP_WXS_3888889046", "description",
     "\u6df1\u5733\u00b7\u5b9d\u5b89\u4e28\u4e3a\u4fdd\u969c\u6d3b\u52a8\u8d28\u91cf\uff0c\u672c\u6d3b\u52a8\u4ec5\u9650\u5356\u5bb6\u53c2\u4e0e\uff0c\u8c22\u7edd\u670d\u52a1\u5546/\u7b2c\u4e09\u673a\u6784\u3002",
     "eq", "\u5e7f\u544a\uff1a\u6df1\u5733\u7ebf\u4e0b\u6d3b\u52a8\u63a8\u5e7f"),
    # \u514d\u8d39\u62a5\u540d\u6d3b\u52a8\u63a8\u5e7f
    ("MP_WXS_3888889046", "description",
     "\u529e\u516c\u6905\u3001\u7535\u7ade\u6905\u3001\u529f\u80fd\u6c99\u53d1\u2026\u2026\u5750\u5177\u7c7b\u6838\u5fc3\u4ea7\u54c1\u5168\u8986\u76d6",
     "eq", "\u5e7f\u544a\uff1a\u514d\u8d39\u62a5\u540d\u6d3b\u52a8\u63a8\u5e7f"),
    # \u4ed8\u8d39\u8bfe\u7a0b\u63a8\u5e7f
    ("MP_WXS_3888889046", "description",
     "\u4e9a\u9a6c\u900a\u4ebf\u7ea7\u64cd\u76d8\u624b\u4eb2\u6388\u7684\u6d41\u91cf\u65b9\u6cd5\u8bba",
     "eq", "\u5e7f\u544a\uff1a\u4ed8\u8d39\u8bfe\u7a0b\u63a8\u5e7f"),
    # \u6807\u9898\u89c4\u5219
    ("MP_WXS_3888889046", "title", "\u5012\u8ba1\u65f6.*\u5929", "re",
     "\u5e7f\u544a\uff1a\u6d3b\u52a8\u5012\u8ba1\u65f6"),
    ("MP_WXS_3888889046", "title", "\u5f00\u653e\u9ea6", "re",
     "\u5e7f\u544a\uff1a\u5f00\u653e\u9ea6\u6d3b\u52a8"),
    ("MP_WXS_3888889046", "title", "\u62db\u8058|\u6c42\u804c|\u62db\u52df", "re",
     "\u5e7f\u544a\uff1a\u62db\u8058"),
    ("MP_WXS_3888889046", "title",
     "\u9ea6\u591a|coconut\\.is|Nano Banana|\u4f9b\u5e94\u94fe\u8d44\u6e90\u5bf9\u63a5",
     "re", "\u5e7f\u544a\uff1a\u4ea7\u54c1\u63a8\u5e7f"),
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
total_deleted = 0
deleted_titles = []

for mp_id, field, pattern, mode, reason in RULES:
    cur.execute("SELECT id, title, description FROM articles WHERE mp_id=? AND status != ?",
                (mp_id, STATUS_DELETED))
    articles = cur.fetchall()

    for art_id, title, desc in articles:
        val = desc if field == "description" else title
        matched = False
        if mode == "eq":
            if val == pattern:
                matched = True
        else:
            if re.search(pattern, val):
                matched = True

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
