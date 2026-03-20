"""
Тест прокси с проверкой реального IP через Telegram
"""

import asyncio
import os
import socket
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.network import Connection

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


async def test_with_different_methods():
    """Тест разных способов подключения прокси"""
    
    print("=" * 60)
    print("ТЕСТ РАЗНЫХ МЕТОДОВ ПОДКЛЮЧЕНИЯ ПРОКСИ")
    print("=" * 60)
    
    if not PROXY_ENABLED or not PROXY_HOST:
        print("Прокси отключён в .env")
        return
    
    proxy_ip = socket.gethostbyname(PROXY_HOST)
    print(f"\nПрокси: {PROXY_HOST} → {proxy_ip}:{PROXY_PORT}")
    print(f"Логин: {PROXY_USERNAME}")
    
    # =========================================================
    # МЕТОД 1: Через параметр proxy (dict)
    # =========================================================
    print("\n" + "=" * 60)
    print("МЕТОД 1: proxy={'proxy_type': 'socks5', ...}")
    print("=" * 60)
    
    proxy_config = {
        'proxy_type': 'socks5',
        'addr': proxy_ip,
        'port': PROXY_PORT,
    }
    if PROXY_USERNAME and PROXY_PASSWORD:
        proxy_config['username'] = PROXY_USERNAME
        proxy_config['password'] = PROXY_PASSWORD
    
    client1 = TelegramClient(
        str(BASE_DIR / 'sessions' / 'test1'),
        API_ID,
        API_HASH,
        proxy=proxy_config
    )
    
    try:
        await client1.connect()
        print("✓ Подключено")
        
        # Проверяем IP через получение DC ID
        if await client1.is_user_authorized():
            me = await client1.get_me()
            print(f"✓ Авторизовано: {me.first_name}")
            print("  ПРОВЕРЬТЕ УВЕДОМЛЕНИЕ ОТ TELEGRAM!")
        else:
            print("✗ Не авторизовано")
        
        await client1.disconnect()
        print("✓ Отключено")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    finally:
        # Чистим сессию
        session_file = BASE_DIR / 'sessions' / 'test1.session'
        if session_file.exists():
            session_file.unlink()
    
    # =========================================================
    # МЕТОД 2: Через _proxy атрибут (внутренний API)
    # =========================================================
    print("\n" + "=" * 60)
    print("МЕТОД 2: client._client._proxy = (...)")
    print("=" * 60)
    
    client2 = TelegramClient(
        str(BASE_DIR / 'sessions' / 'test2'),
        API_ID,
        API_HASH
    )
    
    # Устанавливаем прокси напрямую
    from telethon import _telethon
    print(f"Telethon version: {getattr(_telethon, '__version__', 'unknown')}")
    
    # Пробуем установить прокси через _connector
    try:
        # Формат для Telethon 1.42+
        client2._proxy = (8, proxy_ip, PROXY_PORT, 1, PROXY_USERNAME, PROXY_PASSWORD)
        print(f"Прокси установлен: {proxy_ip}:{PROXY_PORT}")
        
        await client2.connect()
        print("✓ Подключено")
        
        if await client2.is_user_authorized():
            me = await client2.get_me()
            print(f"✓ Авторизовано: {me.first_name}")
            print("  ПРОВЕРЬТЕ УВЕДОМЛЕНИЕ ОТ TELEGRAM!")
        
        await client2.disconnect()
        print("✓ Отключено")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    finally:
        session_file = BASE_DIR / 'sessions' / 'test2.session'
        if session_file.exists():
            session_file.unlink()
    
    # =========================================================
    # МЕТОД 3: Через monkey-patch Connection
    # =========================================================
    print("\n" + "=" * 60)
    print("МЕТОД 3: Прямая установка в Connection")
    print("=" * 60)
    
    # Сохраняем оригинальный _parse_proxy
    original_parse = Connection._parse_proxy
    
    def custom_parse_proxy(cls, proxy):
        print(f"  _parse_proxy вызван с: {proxy}")
        return original_parse(proxy)
    
    # Пробуем переопределить
    try:
        Connection._parse_proxy = classmethod(custom_parse_proxy)
        
        client3 = TelegramClient(
            str(BASE_DIR / 'sessions' / 'test3'),
            API_ID,
            API_HASH,
            proxy=proxy_config
        )
        
        await client3.connect()
        print("✓ Подключено")
        
        if await client3.is_user_authorized():
            me = await client3.get_me()
            print(f"✓ Авторизовано: {me.first_name}")
        
        await client3.disconnect()
        print("✓ Отключено")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    finally:
        Connection._parse_proxy = original_parse
        session_file = BASE_DIR / 'sessions' / 'test3.session'
        if session_file.exists():
            session_file.unlink()
    
    print("\n" + "=" * 60)
    print("ИТОГИ:")
    print("=" * 60)
    print("Проверьте уведомления от Telegram для каждого метода.")
    print("Если везде ваш IP — прокси не работает на уровне системы.")


if __name__ == "__main__":
    asyncio.run(test_with_different_methods())
