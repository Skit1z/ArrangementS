"""字段级加密：AES-256-GCM，用于身份证号 / 银行卡号。

密钥来自 FIELD_ENCRYPTION_KEY（base64 编码的 32 字节）。数据库只额外保存后四位用于脱敏。
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_NONCE_LEN = 12


def _load_key() -> bytes:
    raw = settings.field_encryption_key.strip()
    if not raw:
        if settings.is_production:
            raise RuntimeError("生产环境必须配置 FIELD_ENCRYPTION_KEY")
        # 开发环境回退到确定性密钥，方便本地联调（切勿用于生产）。
        return b"\x00" * 32
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise RuntimeError("FIELD_ENCRYPTION_KEY 必须是 base64 编码的 32 字节")
    return key


def encrypt_field(plaintext: str | None) -> bytes | None:
    if plaintext is None or plaintext == "":
        return None
    aesgcm = AESGCM(_load_key())
    nonce = os.urandom(_NONCE_LEN)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ct


def decrypt_field(blob: bytes | None) -> str | None:
    if not blob:
        return None
    aesgcm = AESGCM(_load_key())
    nonce, ct = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")


def last4(value: str | None) -> str | None:
    if not value:
        return None
    digits = value.strip()
    return digits[-4:] if len(digits) >= 4 else digits


def generate_key_b64() -> str:
    """生成一枚可写入 .env 的新密钥。"""
    return base64.b64encode(os.urandom(32)).decode("ascii")
