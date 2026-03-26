"""
Проверка: применяется ли прокси реально при подключении
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
PHONE = os.getenv('PHONE', '')

# Прокси
PROXY_HOST = 'mobpool.proxy.market'
PROXY_PORT = 10000
PROXY_USERNAME = 'rTtqcDc4t0Kg'
PROXY_PASSWORD = 'wkLYa1bq'

SESSION_PATH = BASE_DIR / 'sessions' / 'debug_proxy'


async def debug_proxy():
    """Пошаговая отладка прокси"""
    
    print("=" * 60)
    print("ОТЛАДКА ПРОКСИ")
    print("=" * 60)
    
    proxy_ip = socket.gethostbyname(PROXY_HOST)
    print(f"\nПрокси: {PROXY_HOST} → {proxy_ip}:{PROXY_PORT}")
    
    # Удаляем старую сессию
    session_file = SESSION_PATH.with_suffix('.session')
    if session_file.exists():
        session_file.unlink()
        print("Старая сессия удалена")
    
    # Создаём клиента
    print("\n1. Создание TelegramClient...")
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    print(f"   client._proxy до установки: {client._proxy}")
    
    # Устанавливаем прокси
    print("\n2. Установка прокси...")
    proxy_tuple = ('socks5', proxy_ip, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)
    client.set_proxy(proxy_tuple)
    print(f"   client._proxy после установки: {client._proxy}")
    
    # Проверяем что будет при connect
    print("\n3. Подключение...")
    
    try:
        await client.connect()
        print("   ✓ Подключено")
        
        # Проверяем _sender и _connection
        print("\n4. Проверка внутренних атрибутов...")
        
        if hasattr(client, '_sender'):
            print(f"   client._sender: {type(client._sender)}")
            if hasattr(client._sender, '_proxy'):
                print(f"   client._sender._proxy: {client._sender._proxy}")
        
        if hasattr(client, '_connection'):
            print(f"   client._connection: {type(client._connection)}")
        
        # Проверяем авторизацию
        print("\n5. Проверка авторизации...")
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"   ✓ Авторизовано: {me.first_name}")
            
            # Получаем информацию о DC
            print(f"   DC ID: {me.dc_id}")
            
            print("\n" + "!" * 60)
            print("ПРОВЕРЬТЕ УВЕДОМЛЕНИЕ ОТ TELEGRAM!")
            print("!" * 60)
            print(f"Если видите IP: {proxy_ip} — прокси работает ✓")
            print(f"Если видите Пермь — прокси НЕ работает ✗")
        else:
            print("   ✗ Не авторизовано")
            print("   Отправляем код...")
            
            await client.send_code_request(PHONE)
            print("   ✓ Код отправлен")
            
            code = input("\nВведите код: ").strip()
            
            if code:
                await client.sign_in(PHONE, code)
                me = await client.get_me()
                print(f"   ✓ Авторизовано: {me.first_name}")
                print(f"   DC ID: {me.dc_id}")
                
                print("\n" + "!" * 60)
                print("ПРОВЕРЬТЕ УВЕДОМЛЕНИЕ ОТ TELEGRAM!")
                print("!" * 60)
        
        await client.disconnect()
        print("\n6. Отключено")
        
    except Exception as e:
        print(f"   ✗ Ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_proxy())
