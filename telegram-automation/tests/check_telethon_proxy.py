"""
Проверка внутренностей Telethon для правильной установки прокси
"""

import asyncio
import os
import socket
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
import inspect

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')

# Прокси
PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
PROXY_HOST = os.getenv('PROXY_HOST', '')
PROXY_PORT = int(os.getenv('PROXY_PORT', '0'))
PROXY_USERNAME = os.getenv('PROXY_USERNAME', '')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')


def explore_telethon():
    """Исследуем Telethon"""
    print("=" * 60)
    print("ИССЛЕДОВАНИЕ TELETHON")
    print("=" * 60)
    
    import telethon
    print(f"\nTelethon version: {telethon.__version__}")
    
    # Проверяем TelegramClient
    print("\nTelegramClient.__init__ signature:")
    sig = inspect.signature(TelegramClient.__init__)
    for name, param in sig.parameters.items():
        if name == 'proxy':
            print(f"  proxy: annotation={param.annotation}, default={param.default}")
    
    # Проверяем Connection
    from telethon.network import Connection
    print(f"\nConnection._parse_proxy:")
    if hasattr(Connection, '_parse_proxy'):
        src = inspect.getsource(Connection._parse_proxy)
        print(src[:500])
    
    # Проверяем есть ли _connector
    print("\nПроверка атрибутов TelegramClient:")
    client = TelegramClient(str(BASE_DIR / 'sessions' / 'temp'), API_ID, API_HASH)
    
    for attr in dir(client):
        if 'proxy' in attr.lower() or 'connect' in attr.lower():
            print(f"  {attr}")
    
    # Проверяем _client
    if hasattr(client, '_client'):
        print(f"\nclient._client type: {type(client._client)}")
        for attr in dir(client._client):
            if 'proxy' in attr.lower():
                print(f"  client._client.{attr}")


async def test_correct_proxy():
    """Тест правильного подключения прокси"""
    
    print("\n" + "=" * 60)
    print("ТЕСТ ПРАВИЛЬНОГО ПОДКЛЮЧЕНИЯ")
    print("=" * 60)
    
    if not PROXY_ENABLED or not PROXY_HOST:
        print("Прокси отключён")
        return
    
    proxy_ip = socket.gethostbyname(PROXY_HOST)
    print(f"\nПрокси: {proxy_ip}:{PROXY_PORT}")
    
    # Создаём клиента БЕЗ прокси сначала
    client = TelegramClient(
        str(BASE_DIR / 'sessions' / 'test_correct'),
        API_ID,
        API_HASH
    )
    
    # Проверяем что есть _proxy
    print(f"\nclient._proxy перед установкой: {getattr(client, '_proxy', 'NOT SET')}")
    
    # Устанавливаем прокси ПРАВИЛЬНЫМ форматом для Telethon 1.42+
    # Формат: (proxy_type, addr, port, username, password)
    # proxy_type: 1=HTTP, 2=SOCKS4, 3=SOCKS4A, 4=SOCKS5, 5=MTProxy
    # Используем SOCKS5 = 4
    
    client._proxy = (4, proxy_ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
    print(f"client._proxy установлен: {client._proxy}")
    
    try:
        print("\nПодключение...")
        await client.connect()
        print("✓ Подключено через прокси!")
        
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"✓ Авторизовано: {me.first_name}")
            print("\n!!! ПРОВЕРЬТЕ УВЕДОМЛЕНИЕ ОТ TELEGRAM !!!")
            print("Должен быть IP прокси, НЕ ваш реальный!")
        else:
            print("✗ Не авторизовано (но прокси работает)")
        
        await client.disconnect()
        print("✓ Отключено")
        
    except Exception as e:
        print(f"✗ Ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Чистим сессию
        session_file = BASE_DIR / 'sessions' / 'test_correct.session'
        if session_file.exists():
            session_file.unlink()


if __name__ == "__main__":
    explore_telethon()
    print("\n")
    asyncio.run(test_correct_proxy())
