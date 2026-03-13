"""
Сбор чатов с использованием существующей сессии
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.tl.types import Chat, Channel, User

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_PATH = 'sessions/userbot'
OUTPUT_PATH = 'config/chats.json'


async def main():
    """Сбор чатов с использованием существующей сессии"""
    print("=" * 50)
    print("Сбор чатов Telegram (используем существующую сессию)")
    print("=" * 50)
    print()
    
    # Создание клиента
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    print("Подключение к Telegram...")
    
    await client.connect()
    
    if not await client.is_user_authorized():
        print("[ERROR] Сессия не авторизована!")
        print("Запустите auth_and_collect.py для авторизации")
        await client.disconnect()
        return
    
    me = await client.get_me()
    print(f"[OK] Подключено как: {me.first_name} {me.last_name or ''}")
    print()
    
    # Сбор чатов
    print("Сбор списка чатов...")
    print()
    
    chats_data = []
    
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        
        # Пропускаем личные сообщения
        if isinstance(entity, User):
            continue
        
        if isinstance(entity, (Chat, Channel)):
            if hasattr(entity, 'username') and entity.username:
                chat_id = entity.username
            else:
                chat_id = str(entity.id)
            
            title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            chat_type = "channel" if isinstance(entity, Channel) else "chat"
            
            chats_data.append({
                "id": chat_id,
                "name": title,
                "type": chat_type,
                "enabled": True
            })
    
    await client.disconnect()
    
    # Сортировка
    chats_data.sort(key=lambda x: x['name'].lower())
    
    # Статистика
    print()
    print("=" * 50)
    print(f"[OK] Найдено чатов: {len(chats_data)}")
    print("=" * 50)
    print()
    
    print("Первые 20 чатов:")
    for i, chat in enumerate(chats_data[:20], 1):
        status = "[+]" if chat['enabled'] else "[-]"
        print(f"  {i}. {status} {chat['name']} ({chat['id']})")
    
    if len(chats_data) > 20:
        print(f"  ... и ещё {len(chats_data) - 20} чатов")
    
    # Сохранение
    output_path = Path(OUTPUT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    result = {
        "_comment": "Список чатов для рассылки (автоматически собрано)",
        "_version": "1.0.0",
        "_total_found": len(chats_data),
        "chats": chats_data
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"[OK] Сохранено в: {output_path.absolute()}")
    print()
    print("Готово! Теперь можно запустить рассылку:")
    print("  python -m src.main")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INFO] Прервано пользователем")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
