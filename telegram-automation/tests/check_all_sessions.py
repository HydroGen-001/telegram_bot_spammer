"""
Проверка альтернативной сессии
"""

import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')


async def check_session(session_name):
    print("=" * 60)
    print(f"Проверка сессии: {session_name}")
    print("=" * 60)
    print()
    
    client = TelegramClient(f'sessions/{session_name}', API_ID, API_HASH)
    
    print("Подключение...")
    await client.connect()
    
    try:
        authorized = await client.is_user_authorized()
        
        if authorized:
            me = await client.get_me()
            print()
            print("[OK] СЕССИЯ РАБОЧАЯ!")
            print()
            print(f"Вы вошли как: {me.first_name} {me.last_name or ''}")
            if me.username:
                print(f"Username: @{me.username}")
            print(f"ID: {me.id}")
            print(f"Phone: {me.phone}")
            print()
            return True
        else:
            print("[ERROR] Сессия не авторизована")
            return False
            
    except Exception as e:
        print(f"[ERROR] {e}")
        return False
    
    finally:
        await client.disconnect()


async def main():
    sessions_to_check = ['userbot', 'broadcast_session']
    
    for session in sessions_to_check:
        result = await check_session(session)
        if result:
            print()
            print("=" * 60)
            print(f"РАБОЧАЯ СЕССИЯ: {session}.session")
            print("=" * 60)
            print()
            print(f"Обновите config/config.json:")
            print(f'  "session": {{')
            print(f'    "path": "sessions/{session}"')
            print(f'  }}')
            print()
            print("Затем запустите:")
            print("  python collect_from_session.py")
            print()
            return
        
        print()
    
    print("[ERROR] Ни одна сессия не работает")
    print("Нужно пройти авторизацию:")
    print("  python auth_sms.py")


if __name__ == "__main__":
    asyncio.run(main())
