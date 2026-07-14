"""本地控制面的最小会话鉴权。"""

import hmac
import hashlib
import os

from fastapi import Header, HTTPException


async def require_local_session(x_local_api_token: str | None = Header(default=None)) -> str:
    """控制或修改本地状态前必须提供启动时配置的会话令牌。"""
    expected = os.environ.get("LOCAL_API_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="本地控制未配置 LOCAL_API_TOKEN")
    if not x_local_api_token or not hmac.compare_digest(x_local_api_token, expected):
        raise HTTPException(status_code=401, detail="本地控制会话令牌无效")
    # 审计只需要可关联的已认证主体，绝不把会话令牌本身写入日志。
    fingerprint = hashlib.sha256(x_local_api_token.encode("utf-8")).hexdigest()[:16]
    return f"local-session:{fingerprint}"
