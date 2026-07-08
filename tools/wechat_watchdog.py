#!/usr/bin/env python3
"""
WeRSS 登录监控 + 自动重登脚本（no_agent 模式）
==============================================
- 登录正常 → 无输出（静默）
- 登录过期 → 调用 API 生成二维码 → 输出 MEDIA: 路径
"""

import sys
import os
import time
import subprocess
import json

BASE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = '/home/leo/.hermes/profiles/linus/workspace/we-mp-rss.bak/src'
VENV_PYTHON = os.path.join(SRC_DIR, 'venv', 'bin', 'python3')
QR_FILE = os.path.join(SRC_DIR, 'static', 'wx_qrcode.png')
ADMIN_USER = "admin"
# 从环境变量读取密码（不在 git 中保存）
# 优先从环境变量读取，其次从 .credentials.json
import json
_creds_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.credentials.json')
ADMIN_PASS = os.environ.get('WERSS_ADMIN_PASS', '')
if not ADMIN_PASS and os.path.exists(_creds_file):
    try:
        with open(_creds_file) as _f:
            ADMIN_PASS = json.load(_f).get('admin_pass', '')
    except Exception:
        pass

# ---------- 1. 检查登录状态 ----------
check_code = (
    "import sys, os;"
    f"os.chdir('{SRC_DIR}');"
    "sys.path.insert(0, os.getcwd());"
    "from driver.success import getStatus, getLoginInfo;"
    "s = getStatus();"
    "info = (getLoginInfo() or {}).get('expiry', {}) or {};"
    "rem = info.get('remaining_seconds', 0) if s else 0;"
    "print('OK' if s else 'EXPIRED', end='');"
    "print(f'|{rem}' if s else '');"
)
proc = subprocess.run(
    [VENV_PYTHON, '-c', check_code],
    capture_output=True, text=True, timeout=30
)
status_line = proc.stdout.strip()
# 检查末尾是否有 EXPIRED 状态（开头可能有启动信息）
is_expired = status_line.endswith('EXPIRED')

if not is_expired:
    sys.exit(0)

# 登录已过期 — 先输出通知到 stdout（确保 cron 在脚本完成/超时前就能看到）
print("🔴 **微信公众平台登录已过期**", file=sys.stderr)
print("正在自动生成二维码，请稍候...", file=sys.stderr)

# 兜底：先打印一份通知，哪怕二维码生成失败 cron 也能投递
print("🔴 **微信公众平台登录已过期**")
print("")
print("请使用微信扫描下方二维码进行授权，扫描后系统会自动恢复运行。")
print("二维码有效期为 5 分钟。")
print("")

# ---------- 2. 获取管理员 token ----------
login_resp = subprocess.run(
    ['curl', '-s', '-X', 'POST',
     'http://localhost:8001/api/v1/wx/auth/login',
     '-H', 'Content-Type: application/x-www-form-urlencoded',
     '-d', f'username={ADMIN_USER}&password={ADMIN_PASS}'],
    capture_output=True, text=True, timeout=15
)

try:
    token_data = json.loads(login_resp.stdout)
    admin_token = token_data['data']['access_token']
except Exception:
    print("⚠️ 获取管理员 Token 失败，请手动访问管理后台扫码登录")
    sys.exit(1)

# ---------- 3. 触发二维码生成（带重试） ----------
QR_RETRIES = 3
QR_RETRY_DELAY = 10

qr_ok = False
for attempt in range(1, QR_RETRIES + 1):
    if attempt > 1:
        print(f"   🔄 第 {attempt} 次重试生成二维码...", file=sys.stderr)
        time.sleep(QR_RETRY_DELAY)
        if os.path.exists(QR_FILE):
            os.remove(QR_FILE)

    subprocess.run(
        ['curl', '-s', '-X', 'GET',
         'http://localhost:8001/api/v1/wx/auth/qr/code',
         '-H', f'Authorization: Bearer {admin_token}'],
        capture_output=True, text=True, timeout=30
    )

    # 等待二维码图片生成（最多 60 秒）
    for waited in range(0, 60, 3):
        if os.path.exists(QR_FILE) and os.path.getsize(QR_FILE) > 364:
            qr_ok = True
            break
        time.sleep(3)
    if qr_ok:
        break
    print(f"⚠️ 二维码未生成 (尝试 {attempt}/{QR_RETRIES})", file=sys.stderr)

if not qr_ok:
    print("⚠️ 二维码生成失败，请手动访问管理后台扫码登录")
    sys.exit(1)

# ---------- 4. 追加 MEDIA 路径 ----------
print(f"MEDIA:{os.path.abspath(QR_FILE)}")
