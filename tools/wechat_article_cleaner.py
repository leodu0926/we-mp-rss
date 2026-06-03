#!/usr/bin/env python3
"""
WeRSS 广告文章自动清理脚本
按 description/title 过滤广告文章，标记删除
正常时静默，有删除时输出摘要
"""

import sys, re, sqlite3, json, os

DB_PATH = '/home/leo/.hermes/profiles/linus/workspace/we-mp-rss.bak/src/data/db.db'
STATUS_DELETED = 1000

# 规则：(mp_id, field, pattern, mode, reason)
# mode: 'eq' = 精确匹配, 're' = 正则匹配
RULES = [
    # ===== 大宝站外推广 =====
    ("MP_WXS_3862012093", "description", "精细化运营工具2026年亚马逊卖家必备", "eq",
     "广告：工具推荐"),
    ("MP_WXS_3862012093", "title", "工具.*[0-9]+选|选一", "re",
     "广告：工具选一"),

    # ===== 知无不言 =====
    # 深圳线下活动推广
    ("MP_WXS_3888889046", "description",
     "深圳·宝安丨为保障活动质量，本活动仅限卖家参与，谢绝服务商/第三机构。",
     "eq", "广告：深圳线下活动推广"),
    # 免费报名活动推广
    ("MP_WXS_3888889046", "description",
     "办公椅、电竞椅、功能沙发……坐具类核心产品全覆盖",
     "eq", "广告：免费报名活动推广"),
    # 付费课程推广
    ("MP_WXS_3888889046", "description",
     "亚马逊亿级操盘手亲授的流量方法论",
     "eq", "广告：付费课程推广"),
    # 标题规则
    ("MP_WXS_3888889046", "title", "倒计时.*天", "re",
     "广告：活动倒计时"),
    ("MP_WXS_3888889046", "title", "开放麦", "re",
     "广告：开放麦活动"),
    ("MP_WXS_3888889046", "title", "招聘|求职|招募", "re",
     "广告：招聘"),
    ("MP_WXS_3888889046", "title",
     "麦多|coconut\.is|Nano Banana|供应链资源对接",
     "re", "广告：产品推广"),
    # description 以 ⏰ 开头 - 活动/课程推广
    ("MP_WXS_3888889046", "description", "^⏰", "re",
     "广告：活动/课程推广"),
    # 标题含展会关键词
    ("MP_WXS_3888889046", "title", "跨博会|跨交会|跨境节|年度盛会", "re",
     "广告：展会宣传"),
    # 标题含 SellersX
    ("MP_WXS_3888889046", "title", "SellersX", "re",
     "广告：活动推广"),
    # 分享图片 - 废文
    ("MP_WXS_3888889046", "title", "分享图片", "eq",
     "广告：废文"),
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
    print(f"[清理] 共删除 {total_deleted} 篇广告文章")
    for t in deleted_titles:
        print(t)
else:
    sys.exit(0)
