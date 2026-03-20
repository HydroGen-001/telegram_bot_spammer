"""
Тест подключения мобильного прокси (несколько вариантов)
"""
import asyncio
import socket
import os
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')
SESSION_PATH = BASE_DIR / 'sessions' / 'userbot'

PROXY_HOST = os.getenv('PROXY_HOST', '')
PROXY_PORT = int(os.getenv('PROXY_PORT', '0'))
PROXY_USERNAME = os.getenv('PROXY_USERNAME', '')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')

print("=" * 60)
print("ТЕСТ МОБИЛЬНОГО ПРОКСИ")
print("=" * 60)
print(f"\nПрокси: {PROXY_HOST}:{PROXY_PORT}")
print(f"Логин: {PROXY_USERNAME}")
print(f"Пароль: {PROXY_PASSWORD}")
print()

async def test_variant(variant_name, client):
    """Тест варианта подключения"""
    print(f"\n--- {variant_name} ---")
    try:
        print("Подключение...")
        await asyncio.wait_for(client.connect(), timeout=15.0)
        
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"✓ УСПЕХ: {me.first_name}")
            return True
        else:
            print("✗ Не авторизовано")
            return False
    except asyncio.TimeoutError:
        print("✗ ТАЙМАУТ (15 сек)")
        return False
    except Exception as e:
        print(f"✗ Ошибка: {type(e).__name__}: {str(e)[:80]}")
        return False
    finally:
        try:
            await client.disconnect()
        except:
            pass

async def main():
    # Вариант 1: SOCKS5 с IP
    print("\n[1] Получение IP прокси...")
    try:
        ip = socket.gethostbyname(PROXY_HOST)
        print(f"    IP: {ip}")
        
        client1 = TelegramClient(
            str(SESSION_PATH),
            API_ID, API_HASH,
            proxy=('socks5', ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
        )
        result1 = await test_variant("SOCKS5 (IP)", client1)
        if result1:
            print("\n✓ ЭТОТ ВАРИАНТ РАБОТАЕТ!")
            return
    except Exception as e:
        print(f"    Ошибка: {e}")
    
    # Вариант 2: Прямое подключение (без прокси)
    print("\n[2] Без прокси...")
    client2 = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    result2 = await test_variant("Без прокси", client2)
    if result2:
        print("\n✓ Работает без прокси!")

if __name__ == "__main__":
    asyncio.run(main())
