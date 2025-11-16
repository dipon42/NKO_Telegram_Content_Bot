from cryptography.fernet import Fernet

from config import config


# Получение ключа шифрования из переменной окружения
ENCRYPTION_KEY =  config.ENCRYPTION_KEY

fernet = Fernet(ENCRYPTION_KEY.encode())

def encrypt_api_key(api_key: str) -> str:
    """Шифрует API-ключ и возвращает в виде строки"""
    return fernet.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    """Расшифровывает API-ключ"""
    return fernet.decrypt(encrypted_key.encode()).decode()