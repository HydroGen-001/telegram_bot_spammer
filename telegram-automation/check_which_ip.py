"""
Проверка: какой IP видит Telegram при подключении
Сравниваем подключение с прокси и без
"""

import asyncio
import os
import socket
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
import time

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')

# Прокси
PROXY_HOST = 'mobpool.proxy.market'
PROXY_PORT = 10000
PROXY_USERNAME = 'rTtqcDc4t0Kg'
PROXY_PASSWORD = 'wkLYa1bq'


async def check_connection_type(use_proxy: bool):
    """Проверка подключения с прокси или без"""
    
    session_name = 'test_proxy' if use_proxy else 'test_no_proxy'
    session_path = BASE_DIR / 'sessions' / session_name
    
    # Удаляем старую сессию
    session_file = session_path.with_suffix('.session')
    if session_file.exists():
        session_file.unlink()
    
    print("\n" + "=" * 60)
    print(f"ТЕСТ: {'С ПРОКСИ' if use_proxy else 'БЕЗ ПРОКСИ'}")
    print("=" * 60)
    
    # Создаём клиента
    client = TelegramClient(str(session_path), API_ID, API_HASH)
    
    if use_proxy:
        proxy_ip = socket.gethostbyname(PROXY_HOST)
        proxy_tuple = ('socks5', proxy_ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
        client.set_proxy(proxy_tuple)
        print(f"Прокси установлен: {proxy_ip}:{PROXY_PORT}")
    
    # Подключаемся
    print("Подключение...")
    start = time.time()
    await client.connect()
    elapsed = (time.time() - start) * 1000
    print(f"✓ Подключено за {elapsed:.0f} мс")
    
    # Проверяем авторизацию
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"✓ Авторизовано: {me.first_name}")
        print(f"  DC ID: {me.dc_id}")
        
        # Отправляем тестовое сообщение себе
        await client.send_message('me', f'[TEST] {"Proxy" if use_proxy else "No Proxy"} connection test')
        print("  ✓ Тестовое сообщение отправлено в избранное")
        
        print("\n" + "!" * 60)
        print("ПРОВЕРЬТЕ УВЕДОМЛЕНИЕ ОТ TELEGRAM!")
        print("!" * 60)
        if use_proxy:
            print(f"Должен быть IP прокси: {socket.gethostbyname(PROXY_HOST)}")
        else:
            print("Должен быть ваш реальный IP (Пермь)")
    else:
        print("✗ Не авторизовано")
        print("  Нужно сначала авторизоваться через login_with_proxy.py")
    
    await client.disconnect()
    print("✓ Отключено")
    
    # Чистим сессию
    if session_file.exists():
        session_file.unlink()


async def main():
    print("=" * 60)
    print("СРАВНЕНИЕ: Прокси vs Без прокси")
    print("=" * 60)
    print(f"Прокси: {PROXY_HOST}:{PROXY_PORT}")
    print(f"Логин: {PROXY_USERNAME}")
    
    print("\nВЫБЕРИТЕ ТЕСТ:")
    print("  1. Тест с прокси")
    print("  2. Тест без прокси")
    print("  3. Оба теста (сначала с прокси)")
    
    choice = input("\nВыбор (1-3): ").strip()
    
    if choice == '1':
        await check_connection_type(True)
    elif choice == '2':
        await check_connection_type(False)
    elif choice == '3':
        await check_connection_type(True)
        await asyncio.sleep(3)
        await check_connection_type(False)
    else:
        print("Неверный выбор")


if __name__ == "__main__":
    asyncio.run(main())
