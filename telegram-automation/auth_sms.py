"""
Авторизация Telegram с запросом кода по SMS
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
    print("Telegram Авторизация - Запрос кода по SMS")
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
            print()
            print("Закройте это окно и запустите:")
            print("  python collect_from_session.py")
            await client.disconnect()
            return
    except Exception as e:
        print(f"[WARNING] Ошибка проверки авторизации: {e}")
    
    print()
    print("-" * 60)
    print("Запрос кода по SMS...")
    print()
    
    try:
        # Сначала пробуем обычный запрос
        print("Отправка запроса кода...")
        result = await client.send_code_request(PHONE)
        
        print()
        print(f"Код отправлен через: {result.type}")
        print()
        
        # Если код отправлен в приложение, запрашиваем SMS
        if result.type == "app":
            print("Код отправлен в приложение Telegram")
            print()
            print("Запрос кода по SMS...")
            print()
            
            # Запрос SMS
            sms_result = await client.send_code_request(PHONE, force_sms=True)
            
            print()
            print("=" * 60)
            print("SMS ЗАПРОШЕНО!")
            print("=" * 60)
            print()
            print(f"Код будет отправлен по SMS на номер {PHONE}")
            print()
            print("Ожидайте SMS в течение 1-5 минут...")
            print()
            
            code = input_text("Введите код из SMS: ")
            
            if not code:
                print("[ERROR] Код не введён")
                await client.disconnect()
                return
            
            await client.sign_in(PHONE, code, phone_code_hash=sms_result.phone_code_hash)
            
        else:
            # Код уже отправлен через SMS
            print("=" * 60)
            print("КОД ОТПРАВЛЕН ПО SMS!")
            print("=" * 60)
            print()
            print(f"Проверьте SMS на номере {PHONE}")
            print()
            
            code = input_text("Введите код из SMS: ")
            
            if not code:
                print("[ERROR] Код не введён")
                await client.disconnect()
                return
            
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
        print("Закройте это окно и запустите:")
        print("  python collect_from_session.py")
        print()
        
    except SessionPasswordNeededError:
        print()
        print("-" * 60)
        print("Включена двухфакторная защита (2FA)")
        print("-" * 60)
        print()
        password = input_text("Введите пароль 2FA: ")
        
        if not password:
            print("[ERROR] Пароль не введён")
            await client.disconnect()
            return
        
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
        
    except FloodWaitError as e:
        print()
        print(f"[ERROR] Слишком много попыток. Подождите {e.seconds} секунд")
        print("Попробуйте позже")
        
    except Exception as e:
        print()
        print(f"[ERROR] {e}")
        print()
        error_msg = str(e)
        if "PHONE_NUMBER_INVALID" in error_msg:
            print("Возможно, номер телефона указан неверно")
            print(f"Проверьте: {PHONE}")
        elif "PHONE_CODE_INVALID" in error_msg:
            print("Неверный код")
        elif "SESSION_PASSWORD_NEEDED" in error_msg:
            print("Нужен пароль 2FA")
    
    await client.disconnect()
    
    print()
    print("Нажмите Enter для выхода...")
    input_text("")


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
