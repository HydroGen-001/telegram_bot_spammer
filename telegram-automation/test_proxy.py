"""
Проверка подключения через прокси
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')
SESSION_PATH = BASE_DIR / 'sessions' / 'userbot'

# Прокси
PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
PROXY_HOST = os.getenv('PROXY_HOST', '')
PROXY_PORT = int(os.getenv('PROXY_PORT', '0'))
PROXY_USERNAME = os.getenv('PROXY_USERNAME', '')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')

print("=" * 60)
print("ПРОВЕРКА ПРОКСИ")
print("=" * 60)
print(f"\nAPI_ID: {API_ID}")
print(f"API_HASH: {API_HASH[:8]}...")
print(f"PHONE: {PHONE}")
print(f"\nПрокси:")
print(f"  Включён: {PROXY_ENABLED}")
print(f"  Host: {PROXY_HOST or '(не указан)'}")
print(f"  Port: {PROXY_PORT or '(не указан)'}")
print(f"  User: {PROXY_USERNAME or '(не указан)'}")
print()

async def test():
    if PROXY_ENABLED and PROXY_HOST:
        print("[INFO] Настройка прокси...")
        print(f"[INFO] Тип: SOCKS5 ({PROXY_HOST}:{PROXY_PORT})")
        # SOCKS5 прокси с авторизацией
        client = TelegramClient(
            str(SESSION_PATH),
            API_ID,
            API_HASH,
            proxy=(PROXY_HOST, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
        )
        print(f"[OK] Прокси: {PROXY_HOST}:{PROXY_PORT}")
    else:
        client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
        print("[INFO] Прокси не включён")
    
    try:
        print("\n[INFO] Подключение...")
        await client.connect()
        print("[OK] Подключено!")
        
        if await client.is_user_authorized():
            print("[OK] Сессия активна!")
            me = await client.get_me()
            print(f"[OK] Пользователь: {me.first_name} (@{me.username})")
            
            # Тест отправки
            print("\n[INFO] Тест отправки (себе)...")
            await client.send_message('me', '[TEST] Proxy check')
            print("[OK] Сообщение отправлено!")
        else:
            print("[ERROR] Сессия не активна! Запустите start.py → пункт 1")
        
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        
    finally:
        print("\n[INFO] Отключение...")
        await client.disconnect()
        print("[OK] Отключено")

if __name__ == "__main__":
    asyncio.run(test())
