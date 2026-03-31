import asyncio
from multi_account import Config, AccountConfig, ProxyManager

async def test():
    print('=' * 60)
    print('ТЕСТ РАССЫЛКИ')
    print('=' * 60)
    
    print('\n1. Загрузка аккаунтов...')
    data = Config.load_accounts()
    accounts = data.get('accounts', [])
    enabled = [a for a in accounts if a.get('enabled')]
    print(f'   Включено аккаунтов: {len(enabled)}')
    
    for acc in enabled:
        print(f"\n{'=' * 40}")
        print(f"Аккаунт: {acc.get('name')}")
        print(f'{'=' * 40}')
        
        account_config = AccountConfig(acc)
        
        # Проверка текста
        print('\n  ПРОВЕРКА ТЕКСТА:')
        text = account_config.get_text()
        if text:
            print(f'    ✓ Текст: OK ({len(text)} симв.)')
            print(f'    Первые 50 симв: {text[:50]}...')
        else:
            print(f'    ✗ Текст: НЕ НАЙДЕН')
            print(f'    Script config: {account_config.script_config}')
        
        # Проверка фото
        print('\n  ПРОВЕРКА ФОТО:')
        photo = account_config.get_photo_path()
        if photo:
            print(f'    ✓ Фото: OK ({photo})')
        else:
            print(f'    ✗ Фото: НЕ НАЙДЕНО')
            print(f'    Photo config: {account_config.photo_config}')
        
        # Подключение
        print('\n  ПОДКЛЮЧЕНИЕ:')
        proxy_manager = ProxyManager()
        client = proxy_manager.create_client_with_proxy(account_config)
        
        try:
            print('    Подключение к Telegram...')
            await client.connect()
            print('    ✓ Подключено')
            
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f'    ✓ Авторизовано: @{me.username or me.first_name}')
                
                # Проверка диалогов
                print('    Загрузка диалогов...')
                count = 0
                async for dialog in client.iter_dialogs():
                    count += 1
                print(f'    ✓ Диалогов: {count}')
            else:
                print(f'    ✗ Не авторизовано')
            
            print('    Отключение...')
            await client.disconnect()
            print('    ✓ Отключено')
        except Exception as e:
            print(f'    ✗ Ошибка: {type(e).__name__}: {e}')
            import traceback
            traceback.print_exc()
    
    # Проверка чатов
    print(f"\n{'=' * 60}")
    print('ПРОВЕРКА ЧАТОВ')
    print(f'{'=' * 60}')
    chats = Config.get_chats()
    print(f'Загружено чатов: {len(chats)}')
    if chats:
        print(f'Первые 5:')
        for c in chats[:5]:
            print(f'  - {c.get("name", c.get("id"))}')

if __name__ == '__main__':
    asyncio.run(test())
