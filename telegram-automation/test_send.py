"""
Тест отправки в конкретный чат
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')
SESSION_PATH = BASE_DIR / 'sessions/userbot'

TEXT = "🫵 ТЕСТ рассылки! Не обращайте внимания."

async def test_send():
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)

    try:
        print("Подключение...")
        await client.connect()
        print("Подключено!")

        if not await client.is_user_authorized():
            print("НЕ авторизовано!")
            return

        # Получаем все диалоги и пробуем отправить в первые несколько
        print("\nПолучение диалогов...")
        dialogs = []
        async for dialog in client.iter_dialogs():
            dialogs.append(dialog)
            if len(dialogs) >= 5:
                break
        
        for dialog in dialogs:
            entity = dialog.entity
            name = getattr(entity, 'title', 'Unknown')
            chat_type = type(entity).__name__
            
            # Пропускаем пользователей
            if chat_type == 'User':
                continue
                
            print(f"\n--- Чат: {name} ({chat_type}) ---")
            
            # Проверяем тип
            is_channel = hasattr(entity, 'broadcast') and entity.broadcast
            is_group = hasattr(entity, 'megagroup') and entity.megagroup
            print(f"Канал: {is_channel}, Группа: {is_group}")
            
            # Пробуем отправить
            try:
                await client.send_message(entity, TEXT)
                print("✓ Сообщение отправлено!")
            except Exception as e:
                print(f"✗ Ошибка: {type(e).__name__}: {e}")
        
        # Пробуем отправить себе (me) для проверки
        print(f"\n--- Отправка себе (me) ---")
        await client.send_message('me', '[TEST] Проверка')
        print("✓ Сообщение себе отправлено!")
        
    finally:
        await client.disconnect()
        print("\nОтключено.")

if __name__ == "__main__":
    asyncio.run(test_send())
