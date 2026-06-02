#!/usr/bin/env python3
"""WeRSS 登录状态监控脚本

用法：
  python3 check_login.py

输出说明：
  - 如果登录正常且剩余时间充足 → 无输出 (静默)
  - 如果登录过期或即将过期 → 输出状态信息，供 cron 触发重登流程
"""

import sys
import os
import json
import time

# 切换到 WeRSS src 目录
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')
os.chdir(SRC_DIR)
sys.path.insert(0, SRC_DIR)

# 激活 venv
venv_path = os.path.join(SRC_DIR, 'venv', 'bin', 'activate_this.py')
if os.path.exists(venv_path):
    exec(open(venv_path).read(), {'__file__': venv_path})

from driver.success import getStatus, getLoginInfo

# 检查登录状态
status = getStatus()

if not status:
    # 登录已过期
    print("STATUS:EXPIRED")
    print("MSG:微信公众号登录已过期，需要重新扫码")
    sys.exit(0)

# 登录有效，检查剩余时间
info = getLoginInfo()
if not info:
    print("STATUS:NO_DATA")
    print("MSG:无法获取登录信息")
    sys.exit(0)

expiry = info.get('expiry', {})
remaining = expiry.get('remaining_seconds', 0) if expiry else 0
expiry_time = expiry.get('expiry_time', 'unknown') if expiry else 'unknown'
token = info.get('token', '')
wx_name = info.get('ext_data', {}).get('wx_app_name', 'unknown')

# 剩余时间阈值：低于 1 小时触发预警
WARN_THRESHOLD = 3600

if remaining < WARN_THRESHOLD:
    print(f"STATUS:EXPIRING_SOON")
    print(f"MSG:微信公众号 ({wx_name}) 登录即将过期")
    print(f"REMAINING:{remaining}")
    print(f"EXPIRY_TIME:{expiry_time}")
    print(f"TOKEN:{token[:20]}...")
else:
    # 一切正常，静默退出
    pass
