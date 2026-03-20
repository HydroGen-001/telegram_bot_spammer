"""
Проверка IP через прокси
"""
import asyncio
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

async def check_ip():
    import socket
    proxy_ip = socket.gethostbyname(PROXY_HOST)
    
    client = TelegramClient(
        str(SESSION_PATH),
        API_ID, API_HASH,
        proxy=('socks5', proxy_ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
    )
    
    try:
        print("Подключение через прокси...")
        await client.connect()
        
        # Получаем информацию о подключении
        print(f"Прокси: {PROXY_HOST}:{PROXY_PORT}")
        print(f"IP прокси: {proxy_ip}")
        
        # Проверяем кто мы
        me = await client.get_me()
        print(f"\n✓ Подключено как: {me.first_name}")
        
        # Отправляем себе тест
        await client.send_message('me', f'[TEST] Proxy check via {proxy_ip}')
        print("✓ Тестовое сообщение отправлено")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(check_ip())
