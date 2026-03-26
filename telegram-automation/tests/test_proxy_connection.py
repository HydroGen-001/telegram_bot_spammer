"""
Тест подключения через прокси
Проверяет, что TelegramClient использует прокси при подключении
"""

import asyncio
import os
import socket
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')

# Прокси
PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
PROXY_HOST = os.getenv('PROXY_HOST', '')
PROXY_PORT = int(os.getenv('PROXY_PORT', '0'))
PROXY_USERNAME = os.getenv('PROXY_USERNAME', '')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')

SESSION_PATH = BASE_DIR / 'sessions' / 'proxy_test'


def log_info(msg):
    print(f"[INFO] {msg}")


def log_ok(msg):
    print(f"[OK] {msg}")


def log_error(msg):
    print(f"[ERROR] {msg}")


async def check_ip_without_proxy():
    """Проверка IP без прокси"""
    log_info("\n=== ПРОВЕРКА БЕЗ ПРОКСИ ===")
    
    try:
        ip = socket.gethostbyname('api.telegram.org')
        log_info(f"IP api.telegram.org: {ip}")
    except Exception as e:
        log_error(f"Не удалось получить IP: {e}")


async def check_ip_with_proxy():
    """Проверка IP через прокси"""
    if not PROXY_ENABLED or not PROXY_HOST:
        log_info("Прокси отключён")
        return None
    
    try:
        # Получаем IP прокси
        proxy_ip = socket.gethostbyname(PROXY_HOST)
        log_info(f"IP прокси {PROXY_HOST}: {proxy_ip}")
        return proxy_ip
    except Exception as e:
        log_error(f"Не удалось получить IP прокси: {e}")
        return None


async def test_connection_with_proxy():
    """Тест подключения с прокси"""
    
    log_info("\n=== ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ ===")
    log_info(f"API_ID: {API_ID}")
    log_info(f"API_HASH: {API_HASH}")
    log_info(f"PHONE: {PHONE}")
    log_info(f"Прокси: {PROXY_ENABLED}")
    
    if PROXY_ENABLED and PROXY_HOST:
        log_info(f"Прокси: {PROXY_HOST}:{PROXY_PORT}")
        log_info(f"Логин: {PROXY_USERNAME}")
    
    # Создаём клиента С ПРОКСИ
    if PROXY_ENABLED and PROXY_HOST:
        proxy_ip = socket.gethostbyname(PROXY_HOST)
        
        client = TelegramClient(
            str(SESSION_PATH),
            API_ID,
            API_HASH,
            proxy=('socks5', proxy_ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
        )
        
        log_info("Клиент создан с proxy=('socks5', ...)")
    else:
        client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
        log_info("Клиент создан без прокси")
    
    try:
        # Подключаемся
        log_info("Подключение...")
        await client.connect()
        
        # Проверяем авторизацию
        if await client.is_user_authorized():
            me = await client.get_me()
            log_ok(f"✓ Авторизовано: {me.first_name} (@{me.username})")
            
            # Отправляем тестовое сообщение себе
            log_info("Отправка тестового сообщения...")
            await client.send_message('me', f'[PROXY TEST] Connection test')
            log_ok("✓ Тестовое сообщение отправлено")
            
            # Проверяем IP через бота
            log_info("\nПроверьте последнее сообщение в Telegram!")
            log_info("Если видите это сообщение — подключение работает.")
            log_info("Если получили уведомление о входе с вашего IP — прокси НЕ работает!")
            
        else:
            log_error("Не авторизовано!")
            log_info("Для проверки прокси нужно сначала авторизоваться.")
            
            # Отправляем код
            log_info(f"Отправка кода на {PHONE}...")
            await client.send_code_request(PHONE)
            log_ok("Код отправлен")
            
            code = input("\nВведите код: ").strip()
            if code:
                try:
                    await client.sign_in(phone=PHONE, code=code)
                    me = await client.get_me()
                    log_ok(f"✓ Авторизовано: {me.first_name}")
                    
                    # Проверяем прокси
                    log_info("\n=== ПРОВЕРКА ПРОКСИ ===")
                    log_info("Telegram должен показать вход через прокси IP")
                    log_info(f"IP прокси: {PROXY_HOST} → {proxy_ip if PROXY_ENABLED else 'N/A'}")
                    log_info("\nЕсли видите вход с вашего реального IP — прокси не работает!")
                    
                except Exception as e:
                    log_error(f"Ошибка входа: {e}")
        
        await client.disconnect()
        log_info("\nОтключено")
        
    except Exception as e:
        log_error(f"Ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Главная функция"""
    print("=" * 60)
    print("ТЕСТ ПОДКЛЮЧЕНИЯ ЧЕРЕЗ ПРОКСИ")
    print("=" * 60)
    
    # Проверка IP
    await check_ip_without_proxy()
    await check_ip_with_proxy()
    
    # Тест подключения
    await test_connection_with_proxy()
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 60)
    print("\nВАЖНО:")
    print("1. Проверьте уведомления от Telegram о входе")
    print("2. Если видите свой реальный IP — прокси не работает")
    print("3. Если видите IP прокси — всё настроено верно")


if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрервано")
