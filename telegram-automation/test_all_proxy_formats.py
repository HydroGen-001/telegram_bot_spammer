"""
Тест всех форматов прокси для mobpool.proxy.market
"""

import asyncio
import os
import socket
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')

# Прокси из вашего конфига
PROXY_HOST = 'mobpool.proxy.market'
PROXY_PORT = 10000
PROXY_USERNAME = 'rTtqcDc4t0Kg'
PROXY_PASSWORD = 'wkLYa1bq'

SESSION_PATH = BASE_DIR / 'sessions' / 'proxy_test_format'


async def test_format(format_name, proxy_value):
    """Тест одного формата прокси"""
    print(f"\n{'=' * 60}")
    print(f"ТЕСТ: {format_name}")
    print(f"{'=' * 60}")
    print(f"Прокси: {proxy_value}")
    
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    
    # Устанавливаем прокси
    if isinstance(proxy_value, dict):
        client.set_proxy(proxy_value)
    else:
        client.set_proxy(proxy_value)
    
    try:
        await client.connect()
        print("✓ Подключено")
        
        # Проверяем авторизацию
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"✓ Авторизовано: {me.first_name}")
            print("\n!!! ПРОВЕРЬТЕ УВЕДОМЛЕНИЕ ОТ TELEGRAM !!!")
        else:
            print("✗ Не авторизовано")
        
        await client.disconnect()
        print("✓ Отключено")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка: {type(e).__name__}: {e}")
        return False
    finally:
        # Чистим сессию
        session_file = SESSION_PATH.with_suffix('.session')
        if session_file.exists():
            try:
                session_file.unlink()
            except Exception:
                pass


async def main():
    """Тест всех форматов"""
    print("=" * 60)
    print("ТЕСТ ВСЕХ ФОРМАТОВ ПРОКСИ")
    print("=" * 60)
    print(f"Прокси: {PROXY_HOST}:{PROXY_PORT}")
    print(f"Логин: {PROXY_USERNAME}")
    
    # Получаем IP
    try:
        proxy_ip = socket.gethostbyname(PROXY_HOST)
        print(f"IP прокси: {proxy_ip}")
    except Exception as e:
        print(f"✗ Не удалось получить IP: {e}")
        return
    
    # =========================================================
    # ФОРМАТ 1: SOCKS5 кортеж
    # =========================================================
    result1 = await test_format(
        "SOCKS5 (кортеж)",
        ('socks5', proxy_ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
    )
    
    await asyncio.sleep(2)
    
    # =========================================================
    # ФОРМАТ 2: SOCKS5 dict
    # =========================================================
    result2 = await test_format(
        "SOCKS5 (dict)",
        {
            'proxy_type': 'socks5',
            'addr': proxy_ip,
            'port': PROXY_PORT,
            'username': PROXY_USERNAME,
            'password': PROXY_PASSWORD
        }
    )
    
    await asyncio.sleep(2)
    
    # =========================================================
    # ФОРМАТ 3: HTTP кортеж (может работать лучше для мобильных)
    # =========================================================
    result3 = await test_format(
        "HTTP (кортеж)",
        ('http', proxy_ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
    )
    
    await asyncio.sleep(2)
    
    # =========================================================
    # ФОРМАТ 4: HTTP dict
    # =========================================================
    result4 = await test_format(
        "HTTP (dict)",
        {
            'proxy_type': 'http',
            'addr': proxy_ip,
            'port': PROXY_PORT,
            'username': PROXY_USERNAME,
            'password': PROXY_PASSWORD
        }
    )
    
    # =========================================================
    # ИТОГИ
    # =========================================================
    print("\n" + "=" * 60)
    print("ИТОГИ")
    print("=" * 60)
    print(f"SOCKS5 (кортеж): {'✓' if result1 else '✗'}")
    print(f"SOCKS5 (dict): {'✓' if result2 else '✗'}")
    print(f"HTTP (кортеж): {'✓' if result3 else '✗'}")
    print(f"HTTP (dict): {'✓' if result4 else '✗'}")
    
    print("\n" + "=" * 60)
    print("РЕКОМЕНДАЦИЯ")
    print("=" * 60)
    
    if result3 or result4:
        print("✓ HTTP прокси работает лучше для mobpool.proxy.market!")
        print("  Используйте формат: ('http', ip, port, user, pass)")
    elif result1 or result2:
        print("✓ SOCKS5 прокси работает")
        print("  Используйте формат: ('socks5', ip, port, user, pass)")
    else:
        print("✗ Ни один формат не работает")
        print("  Проверьте логин/пароль прокси")
        print("  Проверьте что порт 10000 открыт")


if __name__ == "__main__":
    asyncio.run(main())
