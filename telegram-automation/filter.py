"""Фильтрация чатов - только где можно писать"""
import asyncio
import json
import os
from telethon import TelegramClient
from telethon.tl.types import Chat, Channel, User
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_PATH = 'sessions/userbot'
OUTPUT_PATH = 'config/chats.json'

async def main():
    print("=" * 60)
    print("Фильтрация чатов - только где можно писать")
    print("=" * 60)
    
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()
    
    with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chats = data['chats']
    print(f"Загружено: {len(chats)} чатов")
    print()
    
    writable = []
    readonly = []
    
    for chat in chats:
        chat_id = chat['id']
        name = chat['name']
        
        try:
            if chat_id.startswith('@'):
                entity = await client.get_entity(chat_id[1:])
            elif chat_id.replace('-', '').isdigit():
                entity = await client.get_entity(int(chat_id))
            else:
                entity = await client.get_entity(chat_id)
            
            can_write = True
            if isinstance(entity, Channel) and entity.broadcast:
                try:
                    perms = await client.get_permissions(entity)
                    can_write = perms.post_messages if hasattr(perms, 'post_messages') else False
                except:
                    can_write = False
            
            if can_write:
                writable.append(chat)
                print(f"OK: {name}")
            else:
                readonly.append(chat)
                print(f"READ-ONLY: {name}")
        except Exception as e:
            writable.append(chat)
            print(f"ERR({e}): {name}")
    
    await client.disconnect()
    
    print()
    print("=" * 60)
    print(f"Можно писать: {len(writable)}")
    print(f"Только чтение: {len(readonly)}")
    print("=" * 60)
    
    if readonly:
        print()
        print("Исключены каналы:")
        for c in readonly:
            print(f"  - {c['name']}")
    
    result = {
        "_comment": "Только чаты где можно писать",
        "_version": "1.0.0",
        "_total_found": len(writable),
        "_filtered_out": len(readonly),
        "chats": writable
    }
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"Сохранено: {OUTPUT_PATH}")
    print("ГОТОВО!")

if __name__ == "__main__":
    asyncio.run(main())
