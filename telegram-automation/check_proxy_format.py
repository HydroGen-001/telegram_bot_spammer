"""
Проверка формата proxy для Telethon
"""

import sys
print(f"Python: {sys.version}")

try:
    from telethon import TelegramClient
    print(f"Telethon version: {TelegramClient.__module__}")
    
    import telethon
    print(f"Telethon: {telethon.__version__}")
    
    # Проверяем сигнатуру
    import inspect
    sig = inspect.signature(TelegramClient.__init__)
    print(f"\nTelegramClient.__init__ параметры:")
    for name, param in sig.parameters.items():
        if name == 'proxy':
            print(f"  proxy: {param.annotation}")
            print(f"  default: {param.default}")
    
    # Проверяем Connection
    from telethon.network import Connection
    print(f"\nConnection: {Connection}")
    
    if hasattr(Connection, '_parse_proxy'):
        print(f"_parse_proxy: {Connection._parse_proxy}")
    
    # Пробуем создать с proxy
    print("\n=== ТЕСТ СОЗДАНИЯ КЛИЕНТА ===")
    
    # Формат 1: Кортеж
    print("\nФормат 1: ('socks5', host, port, user, pass)")
    try:
        client1 = TelegramClient(
            'test',
            12345,
            'abc',
            proxy=('socks5', '127.0.0.1', 1080, 'user', 'pass')
        )
        print("  ✓ Успешно")
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
    
    # Формат 2: Словарь
    print("\nФормат 2: {'proxy_type': 'socks5', ...}")
    try:
        client2 = TelegramClient(
            'test',
            12345,
            'abc',
            proxy={'proxy_type': 'socks5', 'addr': '127.0.0.1', 'port': 1080}
        )
        print("  ✓ Успешно")
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
    
    # Формат 3: ProxyConfig
    print("\nФормат 3: ProxyConfig")
    try:
        if hasattr(Connection, 'ProxyConfig'):
            config = Connection.ProxyConfig(
                proxy_type='socks5',
                addr='127.0.0.1',
                port=1080
            )
            client3 = TelegramClient('test', 12345, 'abc', proxy=config)
            print("  ✓ Успешно")
        else:
            print("  ✗ ProxyConfig не найден")
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")
    
except Exception as e:
    print(f"Ошибка: {e}")
    import traceback
    traceback.print_exc()
