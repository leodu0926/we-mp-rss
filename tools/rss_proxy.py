#!/usr/bin/env python3
"""
WeRSS RSS 实时广告过滤代理 + 数据库清理
监听 :8098，转发到 WeRSS :8001。
RSS 请求经过滤后返回，同时同步从数据库删除广告文章。
启动：  python3 rss_proxy.py [port]
"""

import re, sys, os, sqlite3, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError
import xml.etree.ElementTree as ET

UPSTREAM = "http://127.0.0.1:8001"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8098
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "db.db"
)
STATUS_DELETED = 1000

# 广告过滤规则：(field, pattern, mode)
# field: 'title' | 'description' | '*'
# mode: 'eq' = 精确, 're' = 正则
AD_RULES = [
    # ===== 大宝站外推广 =====
    ("description", "精细化运营工具2026年亚马逊卖家必备", "eq"),
    ("title", r"工具.*[0-9]+选|选一", "re"),
    # ===== 知无不言 =====
    ("description", "深圳·宝安丨为保障活动质量，本活动仅限卖家参与，谢绝服务商/第三机构。", "eq"),
    ("description", "办公椅、电竞椅、功能沙发……坐具类核心产品全覆盖", "eq"),
    ("description", "亚马逊亿级操盘手亲授的流量方法论", "eq"),
    ("title", r"倒计时.*天", "re"),
    ("title", "开放麦", "re"),
    ("title", r"招聘|求职|招募", "re"),
    ("title", r"麦多|coconut\.is|Nano Banana|供应链资源对接", "re"),
    ("description", r"^⏰", "re"),
    ("title", r"跨博会|跨交会|跨境节|跨境电商节|电商节|年度盛会", "re"),
    ("description", r"AI数字员工|Alexa新流量|百万级联盟营销|全链路广告优化", "re"),
    ("title", "SellersX", "re"),
    ("description", r"SellersX|探索中心|点我查看|拼团优惠", "re"),
    ("description", r"备货垫资|回款慢.*怪圈|钱永远在路上|融资方案|天逸电商宝|跨境资金|现金流.*困境", "re"),
    ("title", "分享图片", "eq"),
    # ===== soju子晴跨境实战玩家 =====
    ("title", r"沙龙|特训营", "re"),
    ("description", r"深圳线下沙龙|一天讲透|特训营回顾", "re"),
]


def is_rss_path(path: str) -> bool:
    """判断是否是 RSS 输出路径"""
    p = path.split("?")[0].rstrip("/")
    if p.startswith("/feed/") and any(x in path for x in (".xml", ".rss", ".atom", ".json")):
        return True
    if p.startswith("/rss"):
        return True
    return False


def is_ad_article(title: str, description: str) -> bool:
    """对标题和描述逐条匹配广告规则"""
    for field, pattern, mode in AD_RULES:
        val = title if field == "title" else description
        if not val:
            continue
        if mode == "eq":
            if val == pattern:
                return True
        else:
            if re.search(pattern, val):
                return True
    return False


def delete_from_db(article_ids: list) -> int:
    """从 SQLite 标记删除指定 ID 的文章"""
    if not article_ids:
        return 0
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        cur = conn.cursor()
        placeholders = ",".join("?" for _ in article_ids)
        cur.execute(
            f"UPDATE articles SET status=? WHERE id IN ({placeholders}) AND status != ?",
            [STATUS_DELETED] + article_ids + [STATUS_DELETED]
        )
        affected = cur.rowcount
        conn.commit()
        conn.close()
        return affected
    except Exception as e:
        print(f"[RSS Proxy] DB 写入失败: {e}", file=sys.stderr)
        return 0


def filter_rss_xml(xml_bytes: bytes) -> bytes:
    """解析 RSS XML，移除广告 item，同时从数据库删除"""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return xml_bytes

    channel = root.find("channel")
    if channel is None:
        return xml_bytes

    items = channel.findall("item")
    deleted_ids = []
    removed_count = 0

    for item in items:
        title_el = item.find("title")
        desc_el = item.find("description")
        id_el = item.find("id")
        title = title_el.text if title_el is not None and title_el.text else ""
        desc = desc_el.text if desc_el is not None and desc_el.text else ""

        if is_ad_article(title, desc):
            art_id = id_el.text if id_el is not None and id_el.text else None
            if art_id:
                deleted_ids.append(art_id)
            channel.remove(item)
            removed_count += 1

    # 同步从数据库删除
    db_deleted = delete_from_db(deleted_ids)
    if removed_count > 0:
        print(f"[RSS Proxy] RSS 过滤 {removed_count} 篇，数据库删除 {db_deleted} 篇")

    if removed_count == 0:
        return xml_bytes

    xml_str = '<?xml version="1.0" encoding="utf-8"?>\n' + \
              ET.tostring(root, encoding="unicode", method="xml",
                          short_empty_elements=False)
    return xml_str.encode("utf-8")


def proxy_request(path: str, method: str = "GET", body: bytes = b"",
                  headers: dict = None, content_type: str = None) -> tuple:
    """向 upstream 发起请求并返回 (status, resp_headers, body_bytes)"""
    url = f"{UPSTREAM}{path}"
    req = Request(url, data=body if body else None, method=method)
    req.add_header("Host", "localhost")
    if headers:
        for k, v in headers.items():
            if k.lower() not in ("host", "connection", "transfer-encoding"):
                req.add_header(k, v)
    if content_type and body:
        req.add_header("Content-Type", content_type)

    try:
        resp = urlopen(req, timeout=30)
        resp_body = resp.read()
        resp_headers = dict(resp.headers.items())
        return resp.status, resp_headers, resp_body
    except URLError as e:
        return 502, {"Content-Type": "text/plain"}, f"Proxy Error: {e.reason}".encode("utf-8")
    except Exception as e:
        return 502, {"Content-Type": "text/plain"}, f"Proxy Error: {e}".encode("utf-8")


class ProxyHandler(BaseHTTPRequestHandler):
    def _handle(self, method: str):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b""

        req_headers = {}
        for key in self.headers.keys():
            req_headers[key] = self.headers[key]

        status, resp_headers, resp_body = proxy_request(
            self.path, method, body, req_headers,
            self.headers.get("Content-Type")
        )

        # RSS 路径：过滤 + 同步删除数据库
        if status == 200 and is_rss_path(self.path):
            resp_body = filter_rss_xml(resp_body)

        self.send_response(status)
        skip_headers = {"transfer-encoding", "content-encoding", "content-length",
                        "connection", "keep-alive"}
        for k, v in resp_headers.items():
            if k.lower() not in skip_headers:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp_body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(resp_body)

    def do_GET(self): self._handle("GET")
    def do_POST(self): self._handle("POST")
    def do_PUT(self): self._handle("PUT")
    def do_DELETE(self): self._handle("DELETE")
    def do_PATCH(self): self._handle("PATCH")
    def do_HEAD(self): self._handle("HEAD")
    def do_OPTIONS(self): self._handle("OPTIONS")

    def log_message(self, fmt, *args):
        path = self.path.split("?")[0]
        if not is_rss_path(path):
            super().log_message(fmt, *args)


SCAN_INTERVAL = 1800  # 30 minutes

# 正文关键词规则（只用于后台全量扫描，RSS 过滤无正文可用）
CONTENT_AD_KEYWORDS = [
    "本文为商业推广软文",
    "本文为商业推广",
    "本文为广告推广",
    "本文为广告",
]


def db_scan_loop():
    """后台线程：定期全量扫描数据库（含正文），删除广告文章"""
    while True:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()
            cur.execute("SELECT id, title, description, content FROM articles WHERE status != ?",
                        (STATUS_DELETED,))
            rows = cur.fetchall()
            total_deleted = 0
            for art_id, title, desc, content in rows:
                # 标题/描述规则检查
                if is_ad_article(title or "", desc or ""):
                    cur.execute("UPDATE articles SET status=? WHERE id=? AND status != ?",
                                (STATUS_DELETED, art_id, STATUS_DELETED))
                    if cur.rowcount > 0:
                        total_deleted += 1
                    continue
                # 正文关键词检查
                body = (content or "").lower()
                for kw in CONTENT_AD_KEYWORDS:
                    if kw.lower() in body:
                        cur.execute("UPDATE articles SET status=? WHERE id=? AND status != ?",
                                    (STATUS_DELETED, art_id, STATUS_DELETED))
                        if cur.rowcount > 0:
                            total_deleted += 1
                        break
            conn.commit()
            conn.close()
            if total_deleted > 0:
                print(f"[RSS Proxy] 后台扫描: 删除 {total_deleted} 篇广告文章", flush=True)
        except Exception as e:
            print(f"[RSS Proxy] 后台扫描失败: {e}", file=sys.stderr, flush=True)
        time.sleep(SCAN_INTERVAL)


def main():
    server = HTTPServer(("0.0.0.0", PORT), ProxyHandler)
    db_dir = os.path.dirname(DB_PATH)
    print(f"[RSS Proxy] 监听 :{PORT} → {UPSTREAM}")
    print(f"[RSS Proxy] 数据库: {DB_PATH}  {'存在' if os.path.exists(DB_PATH) else '不存在!'}")
    print(f"[RSS Proxy] 广告规则 {len(AD_RULES)} 条，RSS 过滤 + 同步删除数据库")
    print(f"[RSS Proxy] 后台扫描每 {SCAN_INTERVAL//60} 分钟全量检查")
    t = threading.Thread(target=db_scan_loop, daemon=True)
    t.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[RSS Proxy] 已退出")
        server.server_close()


if __name__ == "__main__":
    main()
