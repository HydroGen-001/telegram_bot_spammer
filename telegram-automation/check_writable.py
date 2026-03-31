"""
Проверка: в каких чатах можно писать
"""
import asyncio
from telethon.tl.types import Channel, ChannelParticipantsAdmin
from multi_account import Config, AccountConfig, ProxyManager

async def check_writable_chats():
    print('=' * 60)
    print('ПРОВЕРКА: ДОСТУПНЫЕ ДЛЯ ПИСЬМА ЧАТЫ')
    print('=' * 60)
    
    # Загрузка чатов
    chats = Config.get_chats()
    print(f'\nВсего чатов в базе: {len(chats)}')
    
    # Подключение
    print('\nПодключение...')
    account_data = Config.load_accounts()
    account = account_data['accounts'][0]
    account_config = AccountConfig(account)
    
    proxy_manager = ProxyManager()
    client = proxy_manager.create_client_with_proxy(account_config)
    
    await client.connect()
    me = await client.get_me()
    print(f'Аккаунт: @{me.username or me.first_name}')
    
    # Загрузка диалогов
    print('\nЗагрузка диалогов...')
    dialog_ids = set()
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if hasattr(entity, 'username') and entity.username:
            dialog_ids.add(entity.username)
        dialog_ids.add(str(entity.id))
    
    print(f'Диалогов: {len(dialog_ids)}')
    
    # Проверка каждого чата
    writable = []
    not_member = []
    readonly = []
    errors = []
    
    print('\nПроверка чатов из базы...')
    for i, chat in enumerate(chats, 1):
        chat_id = chat['id']
        chat_name = chat.get('name', chat_id)[:50]
        
        if chat_id not in dialog_ids:
            not_member.append(chat)
            status = '✗ НЕ В ЧАТЕ'
        else:
            # Пробуем получить информацию о чате
            try:
                entity = await client.get_entity(chat_id)
                
                # Проверка типа
                if isinstance(entity, Channel):
                    if entity.broadcast:
                        # Это канал — проверяем, админ ли мы
                        is_admin = False
                        try:
                            async for p in client.iter_participants(chat_id, filter=ChannelParticipantsAdmin):
                                if p.id == me.id:
                                    is_admin = True
                                    break
                        except:
                            pass
                        
                        if is_admin:
                            writable.append(chat)
                            status = '✓ КАНАЛ (АДМИН)'
                        else:
                            readonly.append(chat)
                            status = '📢 КАНАЛ (только чтение)'
                    else:
                        # Группа
                        writable.append(chat)
                        status = '✓ ГРУППА'
                else:
                    writable.append(chat)
                    status = '✓ ЧАТ'
                    
            except Exception as e:
                errors.append({'chat': chat, 'error': str(e)})
                status = f'⚠ ОШИБКА: {type(e).__name__}'
        
        if i % 20 == 0:
            print(f'  Проверено: {i}/{len(chats)}')
    
    # Итог
    await client.disconnect()
    
    print(f"\n{'=' * 60}")
    print('ИТОГИ')
    print(f'{'=' * 60}')
    print(f'  Можно писать: {len(writable)}')
    print(f'  Каналы (чтение): {len(readonly)}')
    print(f'  Не состоим: {len(not_member)}')
    print(f'  Ошибки: {len(errors)}')
    
    if writable:
        print(f"\n{'=' * 40}")
        print('ЧАТЫ, ГДЕ МОЖНО ПИСАТЬ:')
        for i, c in enumerate(writable[:20], 1):
            print(f'  {i}. {c.get("name", c.get("id"))[:60]}')
        if len(writable) > 20:
            print(f'  ... ещё {len(writable) - 20}')

if __name__ == '__main__':
    asyncio.run(check_writable_chats())
