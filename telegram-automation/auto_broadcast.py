"""
Автоматический запуск рассылки (пункт 1)
"""
import asyncio
import random
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError

from multi_account import Config, AccountConfig, ProxyManager
from multi_account_start import send_message_with_photo, broadcast_with_account, log, SESSIONS_DIR

async def run_auto_broadcast():
    """Автоматический запуск рассылки"""
    log.header("ЗАПУСК РАССЫЛКИ")
    
    # 1. Проверка готовности аккаунтов
    from multi_account_start import check_accounts_ready
    ready_accounts = await check_accounts_ready()
    
    if not ready_accounts:
        log.error("Нет готовых аккаунтов!")
        return
    
    # 2. Загрузка чатов
    chats = Config.get_chats()
    if not chats:
        log.error("Чаты пусты!")
        return
    
    log.success(f"Загружено {len(chats)} чатов")
    
    # 3. Распределение (по 200 на аккаунт)
    log.header("РАСПРЕДЕЛЕНИЕ ЧАТОВ")
    distribution = {}
    chat_index = 0
    chats_per_account = 200
    
    for acc in ready_accounts:
        start = chat_index
        end = min(chat_index + chats_per_account, len(chats))
        distribution[acc['id']] = chats[start:end]
        chat_index = end
        print(f"  {acc.get('name')}: {len(distribution[acc['id']])} чатов")
        if chat_index >= len(chats):
            break
    
    print(f"\n  Старт через 5 сек...")
    await asyncio.sleep(5)
    
    # 4. Запуск
    log.info("=" * 60)
    log.info("НАЧАЛО РАССЫЛКИ")
    log.info("=" * 60)
    
    total_stats = {'total': 0, 'sent': 0, 'failed': 0, 'errors': []}
    start_time = datetime.now()
    
    for acc_id, acc_chats in distribution.items():
        if not acc_chats:
            continue
        
        acc = next((a for a in ready_accounts if a.get('id') == acc_id), None)
        if not acc:
            continue
        
        # Конфиг
        account_config = AccountConfig(acc)
        text = account_config.get_text()
        if not text:
            log.warning(f"Аккаунт {acc_id}: текст не настроен")
            continue
        
        photo_path = account_config.get_photo_path()
        limits = account_config.limits
        min_delay = limits.get('min_delay', 50)
        max_delay = limits.get('max_delay', 100)
        
        # Клиент с прокси
        proxy_manager = ProxyManager()
        client = proxy_manager.create_client_with_proxy(account_config)
        
        try:
            log.info(f"\n{'=' * 40}")
            log.info(f"{acc.get('name')}")
            log.info(f"{'=' * 40}")
            
            # Запуск рассылки
            stats = await broadcast_with_account(
                client, acc, acc_chats, text, photo_path, min_delay, max_delay, start_from=0
            )
            
            log.info(f"\n✓ Завершил: {stats['sent']}/{len(acc_chats)}")
            
            # Итог
            total_stats['total'] += stats['total']
            total_stats['sent'] += stats['sent']
            total_stats['failed'] += stats['failed']
            total_stats['errors'].extend(stats['errors'][:5])
            
        except Exception as e:
            log.error(f"Ошибка: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                await client.disconnect()
            except:
                pass
    
    # 5. Отчёт
    end_time = datetime.now()
    duration = end_time - start_time
    
    log.header("ОТЧЁТ О РАССЫЛКЕ")
    print(f"  Время:         {duration}")
    print(f"  Чатов всего:   {total_stats['total']}")
    print(f"  Успешно:       {total_stats['sent']}")
    print(f"  Ошибки:        {total_stats['failed']}")
    
    if total_stats['total'] > 0:
        rate = total_stats['sent'] / total_stats['total'] * 100
        print(f"  Процент:       {rate:.1f}%")
    
    if total_stats['errors']:
        print(f"\n  Ошибки ({len(total_stats['errors'])}):")
        for err in total_stats['errors'][:10]:
            print(f"    - {err.get('chat', 'Unknown')}: {err.get('error', 'Unknown')}")


if __name__ == '__main__':
    asyncio.run(run_auto_broadcast())
