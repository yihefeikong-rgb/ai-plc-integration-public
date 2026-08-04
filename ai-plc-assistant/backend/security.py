"""本地控制面的最小会话鉴权。"""

import hmac
import hashlib

from fastapi import Header, HTTPException
from config import settings as app_config


# 已知可预测/占位令牌的拒绝名单（fail-closed）：命中的不是“凭据”，而是
# 明确拒绝的弱默认值，防止随 .env / 前端构建产物泄露的固定默认令牌被用于控制面。
_KNOWN_WEAK_TOKENS = frozenset({
    "local-dev-token-2026",
    "local-dev-token",
    "changeme",
    "change-me",
    "change_me",
    "secret",
    "password",
    "123456",
    "admin",
})
_WEAK_TOKEN_PREFIXES = ("local-dev-token-",)


def _is_known_weak_token(token: str) -> bool:
    """判断配置的令牌是否为已知可预测默认值或占位符。"""
    return token in _KNOWN_WEAK_TOKENS or token.startswith(_WEAK_TOKEN_PREFIXES)


async def require_local_session(x_local_api_token: str | None = Header(default=None)) -> str:
    """控制或修改本地状态前必须提供启动时配置的会话令牌。"""
    expected = app_config.local_api_token
    if not expected:
        raise HTTPException(status_code=503, detail="本地控制未配置 LOCAL_API_TOKEN")
    if _is_known_weak_token(expected):
        # fail-closed：配置的令牌仍是已知弱默认值时拒绝全部控制/写操作，
        # 即使该默认令牌已随前端构建产物泄露也无法通过鉴权。
        raise HTTPException(status_code=503, detail="LOCAL_API_TOKEN 为已知弱默认值，请配置强随机令牌")
    if not x_local_api_token or not hmac.compare_digest(x_local_api_token, expected):
        raise HTTPException(status_code=401, detail="本地控制会话令牌无效")
    # 审计只需要可关联的已认证主体，绝不把会话令牌本身写入日志。
    fingerprint = hashlib.sha256(x_local_api_token.encode("utf-8")).hexdigest()[:16]
    return f"local-session:{fingerprint}"
