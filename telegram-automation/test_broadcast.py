"""
Тест рассылки
"""
import asyncio
import json
import os
import random
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')
SESSION_PATH = BASE_DIR / 'sessions/userbot'
CHATS_PATH = BASE_DIR / 'config/chats.json'

# Лимиты для теста
DAILY_LIMIT = 5
HOURLY_LIMIT = 5
MIN_DELAY = 5
MAX_DELAY = 10

TEXT = "🫵 ТЕСТ рассылки! Не обращайте внимания."

async def test_broadcast():
    # Загружаем чаты
    with open(CHATS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    chats = [c for c in data.get('chats', []) if c.get('enabled', True)][:5]  # Только 5 для теста
    
    print(f"Тестируем на {len(chats)} чатах")
    
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    
    try:
        print("Подключение...")
        await client.connect()
        print("Подключено!")
        
        if not await client.is_user_authorized():
            print("НЕ авторизовано!")
            return
        
        me = await client.get_me()
        print(f"В системе: {me.first_name}")
        
        # Рассылка
        for i, chat in enumerate(chats, 1):
            chat_id = chat['id']
            chat_name = chat.get('name', chat_id)
            print(f"\n[{i}/{len(chats)}] {chat_name}...")
            
            try:
                await client.send_message(chat_id, TEXT)
                print("✓ Отправлено")
            except Exception as e:
                print(f"✗ Ошибка: {e}")
            
            if i < len(chats):
                delay = random.randint(MIN_DELAY, MAX_DELAY)
                print(f"Пауза {delay} сек...")
                await asyncio.sleep(delay)
        
        print("\n✓ Тест завершён!")
        
    finally:
        await client.disconnect()
        print("Отключено.")

if __name__ == "__main__":
    asyncio.run(test_broadcast())
