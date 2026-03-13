"""
Скрипт для автоматического сбора списка чатов из Telegram
Сохраняет результат в config/chats.json

Версия с интерактивной авторизацией
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
PHONE = os.getenv('PHONE', '')
SESSION_PATH = 'sessions/chats_collector'
OUTPUT_PATH = 'config/chats.json'


async def collect_chats():
    """Собрать все чаты и сохранить в JSON"""
    
    # Fix for Windows console encoding
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
    
    print("=" * 50)
    print("Сборщик чатов Telegram")
    print("=" * 50)
    print()
    
    # Проверка конфигурации
    if API_ID == 0 or not API_HASH or not PHONE:
        print("[ERROR] Не заполнены API credentials!")
        print("Проверьте файл .env и заполните:")
        print("  API_ID=ваш_api_id")
        print("  API_HASH=ваш_api_hash")
        print("  PHONE=ваш_номер")
        return
    
    print(f"API_ID: {API_ID}")
    print(f"API_HASH: {API_HASH[:8]}...")
    print(f"PHONE: {PHONE}")
    print()
    
    # Создание клиента
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    print("Подключение к Telegram...")
    print("Если это первый запуск, будет запрошен код авторизации.")
    print()
    
    await client.start(phone=PHONE)
    me = await client.get_me()
    print(f"[OK] Подключено как: {me.first_name} {me.last_name or ''} (@{me.username or 'no_username'})")
    print()
    
    # Сбор чатов
    print("Получение списка чатов...")
    print("(это может занять некоторое время)")
    print()
    
    chats_data = []
    
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        
        # Пропускаем личные сообщения (User)
        if isinstance(entity, User):
            continue
        
        if isinstance(entity, (Chat, Channel)):
            # Получаем идентификатор
            if hasattr(entity, 'username') and entity.username:
                chat_id = entity.username
            else:
                chat_id = str(entity.id)
            
            # Получаем название
            title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            
            # Определяем тип
            chat_type = "channel" if isinstance(entity, Channel) else "chat"
            
            chats_data.append({
                "id": chat_id,
                "name": title,
                "type": chat_type,
                "enabled": True
            })
    
    await client.disconnect()
    
    # Сортировка по названию
    chats_data.sort(key=lambda x: x['name'].lower())
    
    # Статистика
    print()
    print("=" * 50)
    print(f"[OK] Найдено чатов: {len(chats_data)}")
    print("=" * 50)
    print()
    
    # Вывод первых 10 чатов для проверки
    print("Первые 10 чатов:")
    for i, chat in enumerate(chats_data[:10], 1):
        status = "[+]" if chat['enabled'] else "[-]"
        print(f"  {i}. {status} {chat['name']} ({chat['id']})")
    
    if len(chats_data) > 10:
        print(f"  ... и ещё {len(chats_data) - 10} чатов")
    
    # Сохранение в файл
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
    print("Далее:")
    print("  1. Откройте config/chats.json")
    print("  2. Отредактируйте 'enabled': false для чатов, куда не нужно писать")
    print("  3. Запустите: python src/main.py")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(collect_chats())
    except KeyboardInterrupt:
        print("\n[INFO] Прервано пользователем")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
