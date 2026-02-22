import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64
import os
import qrcode
from io import BytesIO
import pyotp

logger = logging.getLogger(__name__)

# Generate a key for encryption (in production, store this securely)
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    # Generate a key if not provided (for development only)
    ENCRYPTION_KEY = base64.urlsafe_b64encode(os.urandom(32)).decode()
    logger.warning("ENCRYPTION_KEY not set. Generated temporary key for development.")

cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_data(data: str) -> str:
    """Encrypt sensitive data"""
    if not data:
        return None
    try:
        encrypted = cipher_suite.encrypt(data.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return None

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    if not encrypted_data:
        return None
    try:
        decrypted = cipher_suite.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        return None

def generate_qr_code(data: str) -> BytesIO:
    """Generate QR code for 2FA"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

def generate_2fa_secret() -> str:
    """Generate 2FA secret"""
    return pyotp.random_base32()

def validate_target(target: str) -> bool:
    """Validate report target format"""
    import re
    patterns = [
        r'^@\w{5,32}$',  # Username
        r'^https?://t\.me/[\w\+]+/?$',  # Telegram link
        r'^https?://t\.me/\+[\w]+$',  # Private group invite
        r'^\d+$',  # User ID
    ]
    return any(re.match(pattern, target) for pattern in patterns)

def format_number(num: int) -> str:
    """Format large numbers"""
    if num < 1000:
        return str(num)
    elif num < 1000000:
        return f"{num/1000:.1f}K"
    else:
        return f"{num/1000000:.1f}M"

def escape_markdown(text: str) -> str:
    """Escape Markdown special characters"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text