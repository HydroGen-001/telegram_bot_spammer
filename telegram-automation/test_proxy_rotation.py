"""
Тест ротации мобильного прокси
Проверяет меняется ли IP при переподключении
"""

import asyncio
import os
import socket
import time
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')

# Прокси
PROXY_HOST = 'mobpool.proxy.market'
PROXY_PORT = int(os.getenv('PROXY_PORT', '10000'))
PROXY_USERNAME = os.getenv('PROXY_USERNAME', '')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')


async def check_ip_change():
    """Проверка смены IP при переподключении"""
    
    print("=" * 60)
    print("ТЕСТ РОТАЦИИ МОБИЛЬНОГО ПРОКСИ")
    print("=" * 60)
    print(f"Прокси: {PROXY_HOST}:{PROXY_PORT}")
    print()
    
    for i in range(1, 6):
        print(f"\n{'=' * 40}")
        print(f"ПОДКЛЮЧЕНИЕ #{i}")
        print(f"{'=' * 40}")
        
        # Получаем IP прокси (DNS запрос)
        proxy_ip = socket.gethostbyname(PROXY_HOST)
        print(f"IP прокси (DNS): {proxy_ip}")
        
        # Создаём клиента
        session_path = BASE_DIR / 'sessions' / f'rotation_test_{i}'
        client = TelegramClient(str(session_path), API_ID, API_HASH)
        
        # Устанавливаем прокси
        proxy_dict = {
            'proxy_type': 'socks5',
            'addr': proxy_ip,
            'port': PROXY_PORT,
        }
        if PROXY_USERNAME and PROXY_PASSWORD:
            proxy_dict['username'] = PROXY_USERNAME
            proxy_dict['password'] = PROXY_PASSWORD
        
        client.set_proxy(proxy_dict)
        
        try:
            # Подключаемся
            print("Подключение к Telegram...")
            await client.connect()
            
            # Проверяем авторизацию
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"✓ Авторизовано: {me.first_name}")
                print(f"  DC ID: {me.dc_id}")
                
                # Отправляем себе тестовое сообщение
                await client.send_message('me', f'[ROTATION TEST #{i}] IP: {proxy_ip}')
                print(f"  ✓ Тестовое сообщение отправлено")
                
                print(f"\n  ПРОВЕРЬТЕ УВЕДОМЛЕНИЕ!")
                print(f"  Должен быть IP: {proxy_ip}")
            else:
                print("✗ Не авторизовано")
            
            await client.disconnect()
            print("✓ Отключено")
            
        except Exception as e:
            print(f"✗ Ошибка: {e}")
        finally:
            # Чистим сессию
            session_file = session_path.with_suffix('.session')
            if session_file.exists():
                try:
                    session_file.unlink()
                except Exception:
                    pass
        
        # Ждём перед следующим подключением
        if i < 5:
            wait_time = 30  # 30 секунд
            print(f"\nОжидание {wait_time} сек перед следующим подключением...")
            for sec in range(wait_time, 0, -1):
                print(f"\r  {sec} сек  ", end='', flush=True)
                await asyncio.sleep(1)
            print()
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 60)
    print("\nПроверьте 5 уведомлений от Telegram:")
    print("• Если IP менялся — ротация работает ✓")
    print("• Если IP одинаковый — ротация не работает ✗")


if __name__ == "__main__":
    asyncio.run(check_ip_change())
