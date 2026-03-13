"""
Авторизация Telegram с выбором метода получения кода
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError

load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')
SESSION_PATH = 'sessions/userbot'


def input_text(prompt):
    """Безопасный ввод текста"""
    try:
        return input(prompt).strip()
    except EOFError:
        return None


async def main():
    print("=" * 60)
    print("Telegram Авторизация")
    print("=" * 60)
    print()
    
    # Проверка конфигурации
    if API_ID == 0 or not API_HASH or not PHONE:
        print("[ERROR] Не заполнены API credentials!")
        print("Проверьте файл .env")
        return
    
    print(f"API_ID: {API_ID}")
    print(f"API_HASH: {API_HASH[:8]}...")
    print(f"PHONE: {PHONE}")
    print()
    
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    print("Подключение к Telegram...")
    await client.connect()
    
    # Проверка существующей авторизации
    try:
        if await client.is_user_authorized():
            print()
            print("[OK] Уже авторизовано!")
            me = await client.get_me()
            print(f"Вы вошли как: {me.first_name} {me.last_name or ''}")
            if me.username:
                print(f"Username: @{me.username}")
            print()
            print("Закройте это окно и запустите сбор чатов:")
            print("  python collect_from_session.py")
            await client.disconnect()
            return
    except Exception as e:
        print(f"[WARNING] Ошибка проверки авторизации: {e}")
    
    print()
    print("-" * 60)
    print("Начинаем процесс авторизации...")
    print()
    
    # Попытка отправки кода
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print(f"Попытка {retry_count + 1} из {max_retries}")
            print()
            
            # Отправка кода
            result = await client.send_code_request(PHONE)
            
            print()
            print("=" * 60)
            print("КОД ОТПРАВЛЕН!")
            print("=" * 60)
            print()
            print(f"Способ отправки: {result.type}")
            print()
            
            # Расшифровка типа отправки
            if result.type == "app":
                print("Код отправлен в ПРИЛОЖЕНИЕ Telegram")
                print("Проверьте:")
                print("  1. Откройте Telegram на ТЕЛЕФОНЕ")
                print("  2. Проверьте чат 'Telegram' (системные уведомления)")
                print("  3. Код выглядит как: 12345")
                print()
            elif result.type == "sms":
                print("Код отправлен по SMS")
                print("Проверьте сообщения на телефоне")
                print()
            elif result.type == "call":
                print("Будет звонок с кодом")
                print("Ответьте на звонок и запишите код")
                print()
            else:
                print(f"Тип отправки: {result.type}")
                print()
            
            # Предложение альтернативы
            print("-" * 60)
            print("Если код не пришёл в течение 1-2 минут:")
            print("  1. Проверьте, что номер указан верно: +79223610891")
            print("  2. Убедитесь, что аккаунт активен в Telegram")
            print("  3. Попробуйте перезапустить Telegram на телефоне")
            print()
            
            # Ввод кода
            code = input_text("Введите код из Telegram: ")
            
            if not code:
                print()
                print("[ERROR] Не удалось получить код")
                retry_count += 1
                continue
            
            # Вход с кодом
            await client.sign_in(PHONE, code, phone_code_hash=result.phone_code_hash)
            
            # Успешная авторизация
            me = await client.get_me()
            print()
            print("=" * 60)
            print(f"[OK] АВТОРИЗАЦИЯ УСПЕШНА!")
            print("=" * 60)
            print()
            print(f"Вы вошли как: {me.first_name} {me.last_name or ''}")
            if me.username:
                print(f"Username: @{me.username}")
            print()
            print("Теперь закройте это окно и запустите:")
            print("  python collect_from_session.py")
            print()
            
            await client.disconnect()
            return
            
        except FloodWaitError as e:
            print()
            print(f"[ERROR] Слишком много попыток. Подождите {e.seconds} секунд")
            print("Попробуйте позже")
            retry_count = max_retries
            
        except SessionPasswordNeededError:
            print()
            print("-" * 60)
            print("Включена двухфакторная защита (2FA)")
            print("-" * 60)
            print()
            password = input_text("Введите пароль: ")
            
            if not password:
                print("[ERROR] Пароль не введён")
                retry_count += 1
                continue
            
            await client.sign_in(password=password)
            
            me = await client.get_me()
            print()
            print("=" * 60)
            print(f"[OK] АВТОРИЗАЦИЯ УСПЕШНА!")
            print("=" * 60)
            print()
            print(f"Вы вошли как: {me.first_name} {me.last_name or ''}")
            print()
            print("Закройте это окно и запустите:")
            print("  python collect_from_session.py")
            print()
            
            await client.disconnect()
            return
            
        except Exception as e:
            print()
            print(f"[ERROR] {e}")
            print()
            
            # Анализ ошибки
            error_msg = str(e)
            if "PHONE_NUMBER_INVALID" in error_msg:
                print("Возможно, номер телефона указан неверно")
                print(f"Проверьте: {PHONE}")
            elif "PHONE_CODE_INVALID" in error_msg:
                print("Неверный код")
            elif "SESSION_PASSWORD_NEEDED" in error_msg:
                print("Нужен пароль 2FA")
            
            retry_count += 1
        
        print()
        print("-" * 60)
    
    print()
    print("[ERROR] Не удалось авторизоваться после нескольких попыток")
    print()
    print("Что делать:")
    print("  1. Убедитесь, что номер верный: +79223610891")
    print("  2. Проверьте, что аккаунт активен в Telegram")
    print("  3. Подождите 1 час и попробуйте снова")
    print("  4. Попробуйте войти в Telegram на телефоне")
    print()
    
    await client.disconnect()


if __name__ == "__main__":
    # Настройка кодировки для Windows
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[INFO] Прервано пользователем")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
