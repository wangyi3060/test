import os
import base64

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

SALT_FILE = os.path.join(os.path.dirname(__file__), '.key_salt')

def _get_salt():
    if not os.path.exists(SALT_FILE):
        salt = os.urandom(16)
        with open(SALT_FILE, 'wb') as f:
            f.write(salt)
    else:
        with open(SALT_FILE, 'rb') as f:
            salt = f.read()
    return salt

def _get_key():
    machine_id = os.environ.get('COMPUTERNAME', 'default') + os.environ.get('USERNAME', 'user')
    machine_id = machine_id.encode()
    salt = _get_salt()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_id))
    return key

def encrypt_value(value):
    if not value or not CRYPTO_AVAILABLE:
        return value
    key = _get_key()
    f = Fernet(key)
    encrypted = f.encrypt(value.encode('utf-8'))
    return base64.urlsafe_b64encode(encrypted).decode('utf-8')

def decrypt_value(encrypted_value):
    if not encrypted_value or not CRYPTO_AVAILABLE:
        return encrypted_value
    try:
        key = _get_key()
        f = Fernet(key)
        decrypted = f.decrypt(base64.urlsafe_b64decode(encrypted_value.encode('utf-8')))
        return decrypted.decode('utf-8')
    except Exception:
        return encrypted_value

SENSITIVE_KEYS = {
    'MYSQL_PASSWORD', 'DB_PASSWORD', 'LDAP_BIND_PASSWORD',
    'SECRET_KEY', 'JWT_SECRET_KEY', 'SMTP_PASSWORD', 'SMS_SECRET_KEY',
}

def decrypt_env_value(env_path):
    if not CRYPTO_AVAILABLE or not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            for key in SENSITIVE_KEYS:
                if stripped.startswith(f'{key}='):
                    value = stripped[len(key)+1:]
                    if value.startswith('enc:'):
                        decrypted = decrypt_value(value[4:])
                        os.environ[key] = decrypted
                    break

def encrypt_env_file(input_path, output_path=None):
    if output_path is None:
        output_path = input_path

    encrypted_lines = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                encrypted_lines.append(line)
                continue

            matched = False
            for key in SENSITIVE_KEYS:
                if stripped.startswith(f'{key}='):
                    value = stripped[len(key)+1:]
                    if value and not value.startswith('enc:'):
                        encrypted = 'enc:' + encrypt_value(value)
                        encrypted_lines.append(f'{key}={encrypted}\n')
                    else:
                        encrypted_lines.append(line)
                    matched = True
                    break

            if not matched:
                encrypted_lines.append(line)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(encrypted_lines)
    print(f"加密完成: {output_path}")
