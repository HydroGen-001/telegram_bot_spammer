"""
Тест правильного формата прокси для Telethon 1.42+
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

# Прокси
PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
PROXY_HOST = os.getenv('PROXY_HOST', '')
PROXY_PORT = int(os.getenv('PROXY_PORT', '0'))
PROXY_USERNAME = os.getenv('PROXY_USERNAME', '')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')


async def test_correct_format():
    """Тест ПРАВИЛЬНОГО формата прокси для Telethon 1.42+"""
    
    print("=" * 60)
    print("ТЕСТ ПРАВИЛЬНОГО ФОРМАТА ПРОКСИ (Telethon 1.42+)")
    print("=" * 60)
    
    if not PROXY_ENABLED or not PROXY_HOST:
        print("Прокси отключён")
        return
    
    proxy_ip = socket.gethostbyname(PROXY_HOST)
    print(f"\nПрокси: {PROXY_HOST} → {proxy_ip}:{PROXY_PORT}")
    print(f"Логин: {PROXY_USERNAME}")
    
    # =========================================================
    # ПРАВИЛЬНЫЙ ФОРМАТ для Telethon 1.42+
    # =========================================================
    # Через set_proxy() с строковым типом!
    # =========================================================
    
    print("\n" + "=" * 60)
    print("МЕТОД: client.set_proxy('socks5', addr, port, username, password)")
    print("=" * 60)
    
    # Создаём клиента БЕЗ прокси
    client = TelegramClient(
        str(BASE_DIR / 'sessions' / 'test_final'),
        API_ID,
        API_HASH
    )
    
    # Устанавливаем прокси ЧЕРЕЗ set_proxy (кортеж!)
    print(f"\nУстановка прокси через set_proxy(tuple)...")
    proxy_tuple = ('socks5', proxy_ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
    client.set_proxy(proxy_tuple)
    print(f"✓ Прокси установлен: {proxy_tuple}")
    
    try:
        print("\nПодключение...")
        await client.connect()
        print("✓ Подключено через прокси!")
        
        # Проверяем авторизацию
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"✓ Авторизовано: {me.first_name} (@{me.username})")
            print("\n" + "!" * 60)
            print("!!! ПРОВЕРЬТЕ УВЕДОМЛЕНИЕ ОТ TELEGRAM !!!")
            print("!" * 60)
            print(f"Должен быть IP прокси: {proxy_ip}")
            print("НЕ ваш реальный IP (Пермь)!")
        else:
            print("✗ Не авторизовано (но прокси работает)")
            print("\nНужно авторизоваться:")
            print("  1. Запустите login_with_proxy.py")
            print("  2. Или используйте start.py → Войти через прокси")
        
        await client.disconnect()
        print("\n✓ Отключено")
        
    except Exception as e:
        print(f"\n✗ Ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_correct_format())
