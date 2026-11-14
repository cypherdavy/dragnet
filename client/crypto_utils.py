# crypto_utils.py (Final Corrected Version)
import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

# --- THIS IS THE CORRECTED KEY ---
# It is now exactly 32 bytes long.
KEY = b'My_Super_Secret_Key_For_Dragnet!'

def encrypt(data: str) -> str:
    """Encrypts data using the 'cryptography' library."""
    iv = os.urandom(16) # AES block size is 16 bytes
    cipher = Cipher(algorithms.AES(KEY), modes.CBC(iv))
    encryptor = cipher.encryptor()
    
    padder = padding.PKCS7(128).padder() # 128-bit block size
    padded_data = padder.update(data.encode('utf-8')) + padder.finalize()
    
    ct = encryptor.update(padded_data) + encryptor.finalize()
    
    iv_b64 = base64.b64encode(iv).decode('utf-8')
    ct_b64 = base64.b64encode(ct).decode('utf-8')
    return f"{iv_b64}:{ct_b64}"

def decrypt(encrypted_data: str) -> str:
    """Decrypts data using the 'cryptography' library."""
    try:
        iv_b64, ct_b64 = encrypted_data.split(':')
        iv = base64.b64decode(iv_b64)
        ct = base64.b64decode(ct_b64)
        
        cipher = Cipher(algorithms.AES(KEY), modes.CBC(iv))
        decryptor = cipher.decryptor()
        
        padded_data = decryptor.update(ct) + decryptor.finalize()
        
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        
        return data.decode('utf-8')
    except (ValueError, KeyError) as e:
        return f"Decryption Error: Invalid data format ({e})"