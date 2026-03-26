"""
Быстрый тест рассылки - проверяем какие чаты работают
"""
import asyncio
import json
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
SESSION_PATH = BASE_DIR / 'sessions' / 'userbot'
CHATS_PATH = BASE_DIR / 'config' / 'chats.json'

TEXT = "🫵 ТЕСТ"

async def test():
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    
    try:
        print("Подключение...")
        await client.connect()
        print("Подключено!")
        
        if not await client.is_user_authorized():
            print("НЕ авторизовано!")
            return
        
        # Загружаем чаты
        with open(CHATS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        chats = [c for c in data.get('chats', []) if c.get('enabled', True)][:10]  # Первые 10
        
        print(f"\nТестируем {len(chats)} чатов...\n")
        
        for i, chat in enumerate(chats, 1):
            chat_id = chat['id']
            chat_name = chat.get('name', chat_id)
            print(f"[{i}] {chat_name} ({chat_id})...", end=" ")
            
            try:
                # Пробуем отправить с таймаутом
                await asyncio.wait_for(
                    client.send_message(chat_id, TEXT),
                    timeout=10.0
                )
                print("✓ ОК")
            except asyncio.TimeoutError:
                print("✗ ТАЙМАУТ")
            except FloodWaitError as e:
                print(f"✗ FLOOD WAIT ({e.seconds} сек)")
            except Exception as e:
                err = str(e)[:50]
                print(f"✗ {type(e).__name__}: {err}")
        
        print("\n\nТест завершён!")
        
    finally:
        client.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
