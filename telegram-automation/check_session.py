"""
Проверка сессии Telegram
"""

import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_PATH = 'sessions/userbot'


async def main():
    print("=" * 60)
    print("Проверка сессии Telegram")
    print("=" * 60)
    print()
    
    print(f"API_ID: {API_ID}")
    print(f"API_HASH: {API_HASH[:8]}...")
    print(f"Session: {SESSION_PATH}")
    print()
    
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    print("Подключение...")
    await client.connect()
    
    try:
        authorized = await client.is_user_authorized()
        
        if authorized:
            me = await client.get_me()
            print()
            print("=" * 60)
            print("[OK] СЕССИЯ РАБОЧАЯ!")
            print("=" * 60)
            print()
            print(f"Вы вошли как: {me.first_name} {me.last_name or ''}")
            if me.username:
                print(f"Username: @{me.username}")
            print(f"ID: {me.id}")
            print()
            print("Далее запустите:")
            print("  python collect_from_session.py")
            print()
        else:
            print()
            print("[ERROR] Сессия не авторизована")
            print("Нужно пройти авторизацию:")
            print("  python auth_sms.py")
            print()
            
    except Exception as e:
        print()
        print(f"[ERROR] {e}")
        print()
        print("Возможные причины:")
        print("  - Сессия повреждена")
        print("  - API ключи не совпадают с сессией")
        print("  - Сессия устарела")
        print()
    
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
