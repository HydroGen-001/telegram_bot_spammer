"""
Тест отправки фото
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

PHOTO_PATH = BASE_DIR / 'photos' / 'photo_2026-03-11_15-45-44.jpg'
TEXT = "🫵 ТЕСТ фото + текст"

async def test_photo():
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    
    try:
        print("Подключение...")
        await client.connect()
        print("Подключено!")
        
        if not await client.is_user_authorized():
            print("НЕ авторизовано!")
            return
        
        print(f"\nФото: {PHOTO_PATH}")
        print(f"Существует: {PHOTO_PATH.exists()}")
        
        # Отправляем себе (me)
        print("\nОтправка фото себе (me)...")
        try:
            print("Вызов send_file()...")
            await client.send_file('me', str(PHOTO_PATH), caption=TEXT)
            print("✓ Фото отправлено!")
        except Exception as e:
            print(f"✗ Ошибка: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        # Отправляем только текст
        print("\nОтправка текста себе (me)...")
        await client.send_message('me', '[TEST] Текст')
        print("✓ Текст отправлен!")
        
    finally:
        client.disconnect()
        print("\nОтключено.")

if __name__ == "__main__":
    asyncio.run(test_photo())
