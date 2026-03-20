"""
Тест подключения к Telegram
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
SESSION_PATH = BASE_DIR / 'sessions/userbot'

print(f"API_ID: {API_ID}")
print(f"API_HASH: {API_HASH[:8]}...")
print(f"PHONE: {PHONE}")
print(f"SESSION: {SESSION_PATH}.session")
print()

async def test():
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    
    print("Подключение...")
    await client.connect()
    print("Подключено!")
    
    if await client.is_user_authorized():
        print("✓ Авторизовано!")
        me = await client.get_me()
        print(f"Пользователь: {me.first_name} (@{me.username})")
        
        # Пробуем отправить сообщение себе (избранное)
        print("\nТест отправки сообщения...")
        await client.send_message('me', '[TEST] Проверка рассылки')
        print("✓ Сообщение отправлено!")
    else:
        print("✗ НЕ авторизовано!")
    
    await client.disconnect()
    print("\nОтключено.")

if __name__ == "__main__":
    asyncio.run(test())
