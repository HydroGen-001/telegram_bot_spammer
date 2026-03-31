"""
Тест рассылки на 5 чатов
"""
import asyncio
import random
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import FloodWaitError

from multi_account import Config, AccountConfig, ProxyManager

API_ID = 26680307
API_HASH = '11fe6a7625e5c368e494c40f29066de0'
SESSION_PATH = Path('sessions/userbot.session')

async def test_broadcast():
    print('=' * 60)
    print('ТЕСТ РАССЫЛКИ НА 5 ЧАТОВ')
    print('=' * 60)
    
    # Загрузка данных
    print('\n1. Загрузка конфигурации...')
    chats = Config.get_chats()[:5]  # Первые 5 чатов
    print(f'   Чатов для теста: {len(chats)}')
    
    account_data = Config.load_accounts()
    account = account_data['accounts'][0]  # Первый аккаунт
    account_config = AccountConfig(account)
    
    text = account_config.get_text()
    photo_path = account_config.get_photo_path()
    
    print(f'   Текст: {len(text)} симв.')
    print(f'   Фото: {photo_path}')
    
    # Подключение
    print('\n2. Подключение...')
    proxy_manager = ProxyManager()
    client = proxy_manager.create_client_with_proxy(account_config)
    
    await client.connect()
    me = await client.get_me()
    print(f'   ✓ @{me.username or me.first_name}')
    
    # Рассылка
    print('\n3. Рассылка...')
    stats = {'sent': 0, 'failed': 0, 'errors': []}
    
    for i, chat in enumerate(chats, 1):
        chat_id = chat['id']
        chat_name = chat.get('name', chat_id)[:50]
        
        print(f'\n   [{i}/{len(chats)}] {chat_name}...', end=' ')
        
        try:
            # Отправка текста
            await client.send_message(chat_id, text)
            
            # Отправка фото
            if photo_path and photo_path.exists():
                await client.send_file(chat_id, photo_path)
            
            print('✓')
            stats['sent'] += 1
            
            # Задержка
            if i < len(chats):
                delay = random.randint(3, 7)
                print(f'      Пауза {delay} сек...')
                await asyncio.sleep(delay)
                
        except FloodWaitError as e:
            print(f'✗ FloodWait {e.seconds} сек')
            stats['failed'] += 1
            stats['errors'].append({'chat': chat_name, 'error': f'FloodWait {e.seconds}'})
            await asyncio.sleep(e.seconds)
            
        except Exception as e:
            print(f'✗ {type(e).__name__}: {str(e)[:50]}')
            stats['failed'] += 1
            stats['errors'].append({'chat': chat_name, 'error': str(e)})
    
    # Итог
    await client.disconnect()
    
    print(f"\n{'=' * 60}")
    print('ИТОГИ ТЕСТА')
    print(f'{'=' * 60}')
    print(f'   Отправлено: {stats["sent"]}/{len(chats)}')
    print(f'   Ошибки: {stats["failed"]}')
    
    if stats['errors']:
        print(f'\n   Ошибки:')
        for err in stats['errors']:
            print(f'     - {err["chat"]}: {err["error"]}')

if __name__ == '__main__':
    asyncio.run(test_broadcast())
