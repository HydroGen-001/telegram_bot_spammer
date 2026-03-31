"""
Автоматический запуск рассылки (пункт 1 меню)
"""
import asyncio
import random
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError

from multi_account import Config, AccountConfig, ProxyManager

SESSIONS_DIR = Path('sessions')

async def send_message_with_photo(client, chat_id, text, photo_path=None):
    """Отправка текста + фото"""
    if not chat_id or not chat_id.strip():
        return False, 'Пустой chat_id'
    
    try:
        await client.send_message(chat_id, text)
    except FloodWaitError as e:
        return False, f'FloodWait {e.seconds} сек'
    except ChatWriteForbiddenError:
        return False, 'Нет доступа на запись'
    except ChannelPrivateError:
        return False, 'Частный канал'
    except ValueError as e:
        return False, f'Чат не найден: {str(e)[:30]}'
    except Exception as e:
        return False, f'{type(e).__name__}: {str(e)[:50]}'
    
    # Фото
    if photo_path and photo_path.exists():
        try:
            await client.send_file(chat_id, photo_path)
        except Exception as e:
            pass  # Фото не критично
    
    return True, 'OK'


async def broadcast_task(client, account, chats, text, photo_path, min_delay, max_delay):
    """Рассылка по чатам"""
    acc_name = account.get('name', f"Аккаунт {account.get('id')}")
    stats = {'total': len(chats), 'sent': 0, 'failed': 0, 'errors': []}
    
    random.shuffle(chats)
    
    for i, chat in enumerate(chats, 1):
        chat_id = chat['id']
        chat_name = chat.get('name', chat_id)[:50]
        
        success, error = await send_message_with_photo(client, chat_id, text, photo_path)
        
        if success:
            stats['sent'] += 1
            print(f'  [{i}/{len(chats)}] ✓ {chat_name}')
        else:
            stats['failed'] += 1
            stats['errors'].append({'chat': chat_name, 'error': error})
            print(f'  [{i}/{len(chats)}] ✗ {chat_name} ({error})')
        
        # Задержка
        if i < len(chats):
            delay = random.randint(min_delay, max_delay)
            mins, secs = divmod(delay, 60)
            print(f'\r      Пауза: {mins:02d}:{secs:02d}  ', end='', flush=True)
            await asyncio.sleep(delay)
            print()
    
    return stats


async def run_broadcast():
    """Запуск рассылки"""
    print('=' * 60)
    print('ЗАПУСК РАССЫЛКИ')
    print('=' * 60)
    
    # 1. Загрузка аккаунтов
    print('\n1. Загрузка аккаунтов...')
    data = Config.load_accounts()
    accounts = [a for a in data.get('accounts', []) if a.get('enabled', True)]
    print(f'   Включено: {len(accounts)}')
    
    if not accounts:
        print('   ✗ Нет включённых аккаунтов!')
        return
    
    # 2. Загрузка чатов
    print('\n2. Загрузка чатов...')
    chats = Config.get_chats()
    print(f'   Чатов: {len(chats)}')
    
    if not chats:
        print('   ✗ Чаты пусты!')
        return
    
    # 3. Распределение (по 200 на аккаунт)
    print('\n3. Распределение чатов...')
    distribution = {}
    chat_index = 0
    chats_per_account = 200
    
    for acc in accounts:
        start = chat_index
        end = min(chat_index + chats_per_account, len(chats))
        distribution[acc['id']] = chats[start:end]
        chat_index = end
        print(f'   {acc.get("name")}: {len(distribution[acc["id"]])} чатов')
        if chat_index >= len(chats):
            break
    
    # 4. Предпросмотр
    print(f'\n4. Предпросмотр:')
    print(f'   Чатов всего: {len(chats)}')
    print(f'   Аккаунтов: {len(accounts)}')
    print(f'   Старт через 3 сек...')
    await asyncio.sleep(3)
    
    # 5. Запуск
    print('\n' + '=' * 60)
    print('НАЧАЛО РАССЫЛКИ')
    print('=' * 60)
    
    total_stats = {'total': 0, 'sent': 0, 'failed': 0, 'errors': []}
    start_time = datetime.now()
    
    for acc_id, acc_chats in distribution.items():
        if not acc_chats:
            continue
        
        acc = next((a for a in accounts if a.get('id') == acc_id), None)
        if not acc:
            continue
        
        # Конфиг
        account_config = AccountConfig(acc)
        text = account_config.get_text()
        if not text:
            print(f'\n   ✗ {acc.get("name")}: текст не настроен')
            continue
        
        photo_path = account_config.get_photo_path()
        limits = account_config.limits
        min_delay = limits.get('min_delay', 50)
        max_delay = limits.get('max_delay', 100)
        
        # Клиент
        proxy_manager = ProxyManager()
        client = proxy_manager.create_client_with_proxy(account_config)
        
        try:
            print(f'\n{'=' * 40}')
            print(f'{acc.get("name")}')
            print(f'{'=' * 40}')
            
            await client.connect()
            
            if not await client.is_user_authorized():
                print(f'   ✗ Не авторизован')
                await client.disconnect()
                continue
            
            me = await client.get_me()
            print(f'   {me.username or me.first_name}')
            print(f'   Чатов: {len(acc_chats)}')
            
            # Рассылка
            stats = await broadcast_task(
                client, acc, acc_chats, text, photo_path, min_delay, max_delay
            )
            
            print(f'\n   ✓ Завершил: {stats["sent"]}/{len(acc_chats)}')
            
            # Итог
            total_stats['total'] += stats['total']
            total_stats['sent'] += stats['sent']
            total_stats['failed'] += stats['failed']
            total_stats['errors'].extend(stats['errors'][:5])
            
            await client.disconnect()
            
        except Exception as e:
            print(f'   ✗ Ошибка: {type(e).__name__}: {e}')
            if 'client' in locals():
                await client.disconnect()
    
    # 6. Общий отчёт
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{'=' * 60}")
    print('ОТЧЁТ О РАССЫЛКЕ')
    print(f'{'=' * 60}')
    print(f'  Время:         {duration}')
    print(f'  Чатов всего:   {total_stats["total"]}')
    print(f'  Успешно:       {total_stats["sent"]}')
    print(f'  Ошибки:        {total_stats["failed"]}')
    
    if total_stats['total'] > 0:
        rate = total_stats['sent'] / total_stats['total'] * 100
        print(f'  Процент:       {rate:.1f}%')
    
    if total_stats['errors']:
        print(f'\n  Ошибки ({len(total_stats["errors"])}):')
        for err in total_stats['errors'][:10]:
            print(f'    - {err.get("chat", "Unknown")}: {err.get("error", "Unknown")}')


if __name__ == '__main__':
    asyncio.run(run_broadcast())
