"""
Проверка работы прокси с реальным подключением
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


def log(msg):
    print(msg)


async def test_proxy_connection():
    """Тест подключения через прокси"""
    
    log("=" * 60)
    log("ПРОВЕРКА ПРОКСИ")
    log("=" * 60)
    
    if not PROXY_ENABLED or not PROXY_HOST:
        log("Прокси отключён в .env")
        return
    
    log(f"Прокси: {PROXY_HOST}:{PROXY_PORT}")
    log(f"Логин: {PROXY_USERNAME}")
    
    # Получаем IP прокси
    try:
        proxy_ip = socket.gethostbyname(PROXY_HOST)
        log(f"IP прокси: {proxy_ip}")
    except Exception as e:
        log(f"Не удалось получить IP прокси: {e}")
        return
    
    # Создаём клиента с прокси
    log("\nСоздание клиента с proxy=('socks5', ...)")
    
    client = TelegramClient(
        str(BASE_DIR / 'sessions' / 'proxy_test'),
        API_ID,
        API_HASH,
        proxy=('socks5', proxy_ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
    )
    
    try:
        log("Подключение...")
        await client.connect()
        
        log("✓ Подключено!")
        
        # Проверяем IP через mtproxy.com или аналогичный сервис
        log("\nПроверка IP...")
        
        try:
            # Пробуем получить IP через бота
            result = await client.get_me()
            log(f"✓ Авторизовано: {result.first_name}")
        except Exception as e:
            log(f"Не авторизовано: {e}")
        
        # Отключаемся
        await client.disconnect()
        log("\n✓ Отключено")
        
        # Удаляем тестовую сессию
        test_session = BASE_DIR / 'sessions' / 'proxy_test.session'
        if test_session.exists():
            test_session.unlink()
            log("Тестовая сессия удалена")
        
        log("\n" + "=" * 60)
        log("ИТОГ:")
        log(f"  Прокси: {PROXY_HOST}:{PROXY_PORT}")
        log(f"  IP прокси: {proxy_ip}")
        log(f"  Подключение: ✓ Успешно")
        log("\nТеперь проверьте уведомление от Telegram:")
        log("  • Если видите IP прокси — всё работает ✓")
        log("  • Если видите свой IP — прокси НЕ работает ✗")
        log("=" * 60)
        
    except Exception as e:
        log(f"\n✗ Ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_proxy_connection())
