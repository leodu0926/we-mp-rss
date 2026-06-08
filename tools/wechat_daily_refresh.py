#!/usr/bin/env python3
"""
WeRSS 每日定时扫码刷新脚本
每天早上 10:30 主动生成二维码发送给用户扫码，确保登录不过期
"""

import sys
import os
import time
import subprocess
import json

SRC_DIR = '/home/leo/.hermes/profiles/linus/workspace/we-mp-rss.bak/src'
VENV_PYTHON = os.path.join(SRC_DIR, 'venv', 'bin', 'python3')
QR_FILE = os.path.join(SRC_DIR, 'static', 'wx_qrcode.png')
ADMIN_USER = "admin"
# 从环境变量读取密码（不在 git 中保存）
# 优先从环境变量读取，其次从 .credentials.json
_creds_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.credentials.json')
ADMIN_PASS = os.environ.get('WERSS_ADMIN_PASS', '')
if not ADMIN_PASS and os.path.exists(_creds_file):
    try:
        with open(_creds_file) as _f:
            ADMIN_PASS = json.load(_f).get('admin_pass', '')
    except Exception:
        pass

# ---------- 1. 获取管理员 token（带重试） ----------
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

admin_token = None
for attempt in range(1, MAX_RETRIES + 1):
    if attempt > 1:
        print(f"   🔄 第 {attempt} 次重试...")
        time.sleep(RETRY_DELAY)

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
        break  # 成功获取，跳出重试
    except Exception as e:
        print(f"⚠️ 获取管理员 Token 失败 (尝试 {attempt}/{MAX_RETRIES}): {e}")
        if login_resp.stdout.strip():
            print(f"   响应内容: {login_resp.stdout[:300]}")
        if login_resp.stderr.strip():
            print(f"   错误输出: {login_resp.stderr[:300]}")
        print(f"   退出码: {login_resp.returncode}")

if admin_token is None:
    print("❌ 重试耗尽，放弃刷新")
    sys.exit(1)

# ---------- 2. 触发二维码生成 ----------
subprocess.run(
    ['curl', '-s', '-X', 'GET',
     'http://localhost:8001/api/v1/wx/auth/qr/code',
     '-H', f'Authorization: Bearer {admin_token}'],
    capture_output=True, text=True, timeout=30
)

# 等待二维码图片生成（最多 60 秒）
for waited in range(0, 60, 3):
    if os.path.exists(QR_FILE) and os.path.getsize(QR_FILE) > 364:
        break
    time.sleep(3)
else:
    print("⚠️ 二维码生成失败，稍后请手动扫码")
    sys.exit(1)

# ---------- 3. 输出 MEDIA 路径 ----------
print(f"MEDIA:{os.path.abspath(QR_FILE)}")
print("")
print("☀️ **每日扫码刷新提醒**")
print("")
print("每天早上扫码一次，确保微信登录 session 不过期。")
print("扫描上方二维码后系统会自动刷新 Token，有效期为 1 天。")
print("二维码有效期为 5 分钟。")
