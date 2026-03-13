"""
Полная авторизация и сбор чатов
Запустите в командной строке (cmd)
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.tl.types import Chat, Channel, User
from telethon.errors import SessionPasswordNeededError

load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')
SESSION_PATH = 'sessions/userbot'
OUTPUT_PATH = 'config/chats.json'


async def main():
    print("=" * 60)
    print("Telegram Automation - Авторизация и сбор чатов")
    print("=" * 60)
    print()
    
    # Проверка конфигурации
    if API_ID == 0 or not API_HASH or not PHONE:
        print("[ERROR] Не заполнены API credentials!")
        print("Проверьте файл .env")
        return
    
    print(f"API_ID: {API_ID}")
    print(f"API_HASH: {API_HASH[:8]}...")
    print(f"PHONE: {PHONE}")
    print()
    
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    print("Подключение...")
    await client.connect()
    
    if await client.is_user_authorized():
        print("[OK] Уже авторизовано!")
        me = await client.get_me()
        print(f"Вы вошли как: {me.first_name} {me.last_name or ''}")
        if me.username:
            print(f"Username: @{me.username}")
    else:
        print()
        print("Требуется авторизация...")
        print()
        
        # Отправка кода
        result = await client.send_code_request(PHONE)
        
        print(f"Код отправлен через: {result.type}")
        print()
        print("Проверьте:")
        print("  - Telegram на других устройствах")
        print("  - SMS")
        print("  - Push-уведомления")
        print()
        
        code = input("Введите код: ").strip()
        
        try:
            await client.sign_in(PHONE, code, phone_code_hash=result.phone_code_hash)
        except SessionPasswordNeededError:
            print()
            print("Включена 2FA защита")
            password = input("Введите пароль: ").strip()
            await client.sign_in(password=password)
        
        me = await client.get_me()
        print()
        print(f"[OK] Авторизация успешна: {me.first_name} {me.last_name or ''}")
    
    print()
    print("-" * 60)
    print("Сбор чатов...")
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
    
    print()
    print("=" * 60)
    print(f"[OK] Найдено чатов: {len(chats_data)}")
    print("=" * 60)
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
    print("=" * 60)
    print("ГОТОВО!")
    print("=" * 60)
    print()
    print("Далее:")
    print("  1. Откройте config/chats.json")
    print("  2. При необходимости измените 'enabled': false для чатов")
    print("  3. Запустите: python src\\main.py")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[INFO] Прервано пользователем")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
