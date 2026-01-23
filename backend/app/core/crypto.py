"""加密工具模块"""
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.config import settings

logger = logging.getLogger(__name__)

# 生成或获取加密密钥
def _get_encryption_key() -> bytes:
    """
    从 SECRET_KEY 生成 Fernet 加密密钥
    
    Fernet 需要一个 32 字节的 base64 编码密钥
    我们使用 PBKDF2 从 SECRET_KEY 派生密钥
    """
    secret_key = settings.SECRET_KEY.encode('utf-8')
    
    # 使用 PBKDF2 派生密钥
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'bugseek_salt',  # 固定 salt，确保相同的 SECRET_KEY 生成相同的加密密钥
        iterations=100000,
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(secret_key))
    return key


# 初始化 Fernet 实例
_fernet = Fernet(_get_encryption_key())


def encrypt_value(plain_text: str) -> str:
    """
    加密明文值
    
    Args:
        plain_text: 明文字符串
        
    Returns:
        加密后的字符串（base64 编码）
        
    Raises:
        ValueError: 如果加密失败
    """
    if not plain_text:
        return plain_text
    
    try:
        encrypted_bytes = _fernet.encrypt(plain_text.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"加密失败: {str(e)}")
        raise ValueError("加密失败") from e


def decrypt_value(encrypted_text: str) -> str:
    """
    解密加密值
    
    Args:
        encrypted_text: 加密后的字符串
        
    Returns:
        解密后的明文字符串
        
    Raises:
        ValueError: 如果解密失败
    """
    if not encrypted_text:
        return encrypted_text
    
    try:
        decrypted_bytes = _fernet.decrypt(encrypted_text.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"解密失败: {str(e)}")
        # 解密失败时返回原始值，避免数据丢失
        return encrypted_text


def mask_sensitive_value(value: str) -> str:
    """
    对敏感值进行掩码处理
    
    Args:
        value: 原始值
        
    Returns:
        掩码后的值（***）
    """
    return "***"