"""
Быстрая авторизация нескольких аккаунтов
Запуск: python auth_accounts.py
"""

import asyncio
import sys
import io
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()
SESSIONS_DIR = BASE_DIR / 'sessions'

# Быстрая настройка аккаунтов
ACCOUNTS = [
    {
        'id': 1,
        'name': 'Аккаунт 1',
        'phone': '',  # Заполните или оставьте пустым для ввода
        'api_id': 0,
        'api_hash': '',
    },
    {
        'id': 2,
        'name': 'Аккаунт 2',
        'phone': '',
        'api_id': 0,
        'api_hash': '',
    },
]


def log_info(msg):
    print(f"[INFO] {msg}", flush=True)


def log_ok(msg):
    print(f"[OK] {msg}", flush=True)


def log_error(msg):
    print(f"[ERROR] {msg}", flush=True)


async def auth_account(account: dict):
    """Авторизовать аккаунт"""
    
    print(f"\n{'=' * 40}")
    print(f"АВТОРИЗАЦИЯ: {account['name']}")
    print(f"{'=' * 40}")
    
    # Заполняем из .env если не указано
    if not account['phone']:
        account['phone'] = input("Телефон (+7...): ").strip()
    
    if not account['api_id']:
        api_id = input("API ID (или Enter для пропуска): ").strip()
        if api_id:
            account['api_id'] = int(api_id)
        else:
            account['api_id'] = int(input("API ID (обязательно): ").strip())
    
    if not account['api_hash']:
        account['api_hash'] = input("API Hash: ").strip()
    
    session_path = SESSIONS_DIR / f"account_{account['id']}"
    
    client = TelegramClient(str(session_path), account['api_id'], account['api_hash'])
    
    try:
        await client.connect()
        
        # Проверяем авторизацию
        if await client.is_user_authorized():
            me = await client.get_me()
            log_ok(f"Уже авторизовано: @{me.username or me.first_name}")
            return True
        
        # Отправляем код
        log_info(f"Отправка кода на {account['phone']}...")
        await client.send_code_request(account['phone'])
        log_ok("Код отправлен")
        
        # Вводим код
        code = input("\nКод из Telegram: ").strip()
        if not code:
            log_error("Код не введён!")
            return False
        
        # Пробуем войти
        try:
            await client.sign_in(phone=account['phone'], code=code)
        except SessionPasswordNeededError:
            log_info("2FA включён")
            password = input("Пароль: ").strip()
            await client.sign_in(password=password)
        
        me = await client.get_me()
        log_ok(f"✓ Авторизовано: @{me.username or me.first_name}")
        
        return True
    
    except Exception as e:
        log_error(f"Ошибка: {e}")
        return False
    
    finally:
        await client.disconnect()


async def main():
    """Основной цикл"""
    
    print("=" * 60)
    print("БЫСТРАЯ АВТОРИЗАЦИЯ АККАУНТОВ")
    print("=" * 60)
    
    for account in ACCOUNTS:
        success = await auth_account(account)
        
        if success:
            print(f"\n  ✓ {account['name']} готов!")
        else:
            print(f"\n  ✗ {account['name']} не авторизован")
        
        # Продолжать или нет?
        if account != ACCOUNTS[-1]:
            cont = input("\nПродолжить следующий аккаунт? (y/n): ").strip().lower()
            if cont != 'y':
                break
    
    print("\n" + "=" * 60)
    print("АВТОРИЗАЦИЯ ЗАВЕРШЕНА")
    print("=" * 60)
    
    # Инструкция
    print("\nТеперь отредактируйте accounts.json:")
    print("  1. Укажите api_id и api_hash для каждого аккаунта")
    print("  2. Укажите phone для каждого аккаунта")
    print("  3. Настройте скрипты и фото")
    print("\nИли используйте меню: python multi_account_start.py")


if __name__ == "__main__":
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрервано")
