"""
Авторизация с проверкой прокси
Автоматическая проверка IP перед входом в аккаунт

Запуск: python login_with_proxy.py
"""

import asyncio
import os
import sys
import socket
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError

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

SESSION_PATH = BASE_DIR / 'sessions' / 'userbot'

# =============================================================================
# ЛОГГЕР
# =============================================================================

class Colors:
    INFO = '\033[94m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def log_info(msg):
    print(f"{Colors.INFO}[INFO]{Colors.RESET} {msg}")


def log_success(msg):
    print(f"{Colors.SUCCESS}[OK]{Colors.RESET} {msg}")


def log_warning(msg):
    print(f"{Colors.WARNING}[WARN]{Colors.RESET} {msg}")


def log_error(msg):
    print(f"{Colors.ERROR}[ERROR]{Colors.RESET} {msg}")


def header(msg):
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}", flush=True)


# =============================================================================
# ПРОВЕРКА ПРОКСИ
# =============================================================================

async def check_proxy_ip() -> tuple[bool, str, dict]:
    """
    Проверка IP через прокси с замером задержки
    
    Returns:
        (success: bool, ip_address: str, stats: dict)
    """
    import time
    
    if not PROXY_ENABLED or not PROXY_HOST:
        return False, "Прокси отключён", {}
    
    stats = {
        'dns_ms': 0,
        'connect_ms': 0,
        'total_ms': 0
    }
    
    try:
        start_time = time.time()
        
        # Получаем IP прокси (DNS запрос)
        dns_start = time.time()
        proxy_ip = socket.gethostbyname(PROXY_HOST)
        dns_ms = (time.time() - dns_start) * 1000
        stats['dns_ms'] = round(dns_ms, 2)
        
        log_info(f"Прокси: {PROXY_HOST} → {proxy_ip}:{PROXY_PORT}")
        log_info(f"DNS запрос: {stats['dns_ms']} мс")
        
        # ПРАВИЛЬНЫЙ формат для python-socks (Telethon 1.42+)
        # Используем dict с правильными ключами
        proxy_dict = {
            'proxy_type': 'socks5',
            'addr': proxy_ip,
            'port': PROXY_PORT,
        }
        # Только добавляем username/password если они есть
        if PROXY_USERNAME and PROXY_PASSWORD:
            proxy_dict['username'] = PROXY_USERNAME
            proxy_dict['password'] = PROXY_PASSWORD
        
        client = TelegramClient(str(BASE_DIR / 'sessions' / 'proxy_check'), API_ID, API_HASH)
        client.set_proxy(proxy_dict)
        
        # Подключение с замером
        log_info("Подключение для проверки IP...")
        connect_start = time.time()
        await client.connect()
        connect_ms = (time.time() - connect_start) * 1000
        stats['connect_ms'] = round(connect_ms, 2)
        
        log_success(f"✓ Подключено за {stats['connect_ms']} мс")
        
        # Проверяем IP через бота
        me = None
        try:
            me = await client.get_me()
        except Exception:
            pass
        
        await client.disconnect()
        
        stats['total_ms'] = round((time.time() - start_time) * 1000, 2)
        
        # Очищаем тестовую сессию
        test_session = BASE_DIR / 'sessions' / 'proxy_check.session'
        if test_session.exists():
            test_session.unlink()
        
        if me:
            log_success(f"✓ Прокси работает! IP: {proxy_ip}")
            log_info(f"Общее время: {stats['total_ms']} мс")
            return True, proxy_ip, stats
        else:
            log_success(f"✓ Прокси подключается! IP: {proxy_ip}")
            log_info(f"Общее время: {stats['total_ms']} мс")
            return True, proxy_ip, stats
        
    except Exception as e:
        log_error(f"✗ Прокси не работает: {type(e).__name__}: {e}")
        stats['error'] = str(e)
        return False, str(e), stats


async def check_real_ip() -> str:
    """Проверка реального IP (без прокси)"""
    try:
        # Получаем внешний IP
        import urllib.request
        try:
            with urllib.request.urlopen('https://api.ipify.org', timeout=5) as response:
                return response.read().decode('utf-8')
        except Exception:
            # Альтернативный способ
            with urllib.request.urlopen('https://ifconfig.me', timeout=5) as response:
                return response.read().decode('utf-8')
    except Exception:
        return "Не удалось определить"


# =============================================================================
# АВТОРИЗАЦИЯ
# =============================================================================

async def auto_login_with_proxy() -> bool:
    """
    Автоматический вход с проверкой прокси
    
    Алгоритм:
    1. Проверка прокси
    2. Удаление старой сессии
    3. Если прокси работает — вход
    4. Если не работает — предложение войти без прокси
    """
    
    header("АВТОРИЗАЦИЯ С ПРОВЕРКОЙ ПРОКСИ")
    
    # Проверка конфигурации
    if API_ID == 0 or not API_HASH:
        log_error("Заполните API_ID и API_HASH в .env")
        return False
    
    phone = input(f"Телефон [{PHONE}]: ").strip()
    if not phone:
        phone = PHONE
    
    if not phone:
        log_error("Телефон не указан!")
        return False
    
    # =========================================================
    # ШАГ 0: Удаление старой сессии (ВАЖНО!)
    # =========================================================
    
    header("ПОДГОТОВКА")
    
    session_file = SESSION_PATH.with_suffix('.session')
    if session_file.exists():
        log_info(f"Найдена старая сессия: {session_file}")
        choice = input("Удалить старую сессию и войти заново? (y/n): ").strip().lower()
        if choice == 'y':
            try:
                session_file.unlink()
                log_success("Старая сессия удалена")
            except Exception as e:
                log_error(f"Не удалось удалить сессию: {e}")
                log_info("Закройте все процессы Python и попробуйте снова")
                return False
        else:
            log_warning("Продолжаем со старой сессией (прокси может не работать)")
    else:
        log_info("Старая сессия не найдена (чистый вход)")
    
    # =========================================================
    # ШАГ 1: Проверка прокси
    # =========================================================
    
    header("ШАГ 1: ПРОВЕРКА ПРОКСИ")
    
    if PROXY_ENABLED and PROXY_HOST:
        proxy_ok, proxy_ip, stats = await check_proxy_ip()
        
        if proxy_ok:
            log_success(f"✓ Прокси подключён: {proxy_ip}")
            log_info(f"  DNS: {stats.get('dns_ms', 'N/A')} мс")
            log_info(f"  Подключение: {stats.get('connect_ms', 'N/A')} мс")
            log_info(f"  Всего: {stats.get('total_ms', 'N/A')} мс")
            log_info("Вход будет выполнен через прокси")
        else:
            log_error(f"✗ Прокси не работает: {proxy_ip}")
            
            choice = input("\nПродолжить без прокси? (y/n): ").strip().lower()
            if choice != 'y':
                return False
            
            log_info("Вход без прокси...")
            use_proxy = False
    else:
        log_info("Прокси отключён в .env")
        use_proxy = False
    
    # =========================================================
    # ШАГ 2: Подключение и авторизация
    # =========================================================
    
    header("ШАГ 2: ПОДКЛЮЧЕНИЕ")
    
    # Создаём клиента с прокси или без
    use_proxy_flag = PROXY_ENABLED and PROXY_HOST
    
    if use_proxy_flag:
        try:
            proxy_ip = socket.gethostbyname(PROXY_HOST)
            
            # ПРАВИЛЬНЫЙ формат для python-socks (Telethon 1.42+)
            # Используем dict вместо кортежа
            proxy_dict = {
                'proxy_type': 'socks5',
                'addr': proxy_ip,
                'port': PROXY_PORT,
            }
            if PROXY_USERNAME and PROXY_PASSWORD:
                proxy_dict['username'] = PROXY_USERNAME
                proxy_dict['password'] = PROXY_PASSWORD
            
            client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
            client.set_proxy(proxy_dict)
            
            log_info(f"Клиент создан с SOCKS5 прокси: {proxy_ip}:{PROXY_PORT}")
            log_info(f"Прокси установлен через set_proxy(dict)")
        except Exception as e:
            log_error(f"Ошибка создания клиента с прокси: {e}")
            return False
    else:
        client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
        log_info("Клиент создан без прокси")
    
    try:
        await client.connect()
        log_success("✓ Подключено")
        
        # Проверка существующей сессии
        if await client.is_user_authorized():
            me = await client.get_me()
            log_success(f"✓ Уже авторизовано: {me.first_name} (@{me.username})")
            
            # Проверка IP текущей сессии
            log_info("\nПроверьте последнее уведомление от Telegram:")
            log_info("• Если видите IP прокси — всё верно")
            log_info("• Если видите свой IP — сессия создана без прокси")
            
            choice = input("\nВыйти и войти заново через прокси? (y/n): ").strip().lower()
            
            if choice == 'y':
                await client.log_out()
                log_info("Выполнен выход из сессии")
                # Продолжаем авторизацию заново
            else:
                await client.disconnect()
                return True
        
        # =========================================================
        # ШАГ 3: Отправка кода
        # =========================================================
        
        header("ШАГ 3: ОТПРАВКА КОДА")
        
        log_info(f"Отправка кода на {phone}...")
        await client.send_code_request(phone)
        log_success("✓ Код отправлен")
        
        # =========================================================
        # ШАГ 4: Ввод кода (с обработкой)
        # =========================================================
        
        header("ШАГ 4: ВВОД КОДА")
        
        print("\nПроверьте Telegram или SMS", flush=True)
        print("Ожидание ввода кода...", flush=True)
        
        # Используем правильный ввод для Windows
        if sys.platform == 'win32':
            # Для Windows с буферизированным stdout
            code = input("Введите код: ").strip()
        else:
            code = input("Введите код: ").strip()
        
        if not code:
            log_error("✗ Код не введён!")
            await client.disconnect()
            return False
        
        log_info(f"Введён код: {code}")
        
        # =========================================================
        # ШАГ 5: Вход по коду
        # =========================================================
        
        header("ШАГ 5: ВХОД")
        
        try:
            await client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            log_info("2FA включён")
            pwd = input("Введите пароль: ").strip()
            await client.sign_in(password=pwd)
        
        me = await client.get_me()
        log_success(f"✓ Успешный вход: {me.first_name} (@{me.username})")
        
        # =========================================================
        # ШАГ 6: Финальная проверка
        # =========================================================
        
        header("ПРОВЕРКА")
        
        log_info("Telegram должен прислать уведомление о входе")
        log_info("Проверьте:")
        
        if PROXY_ENABLED and PROXY_HOST:
            log_success(f"• Должен быть IP прокси: {PROXY_HOST}")
        else:
            log_warning("• Вход выполнен без прокси")
        
        log_info("\nЕсли видите уведомление с вашим реальным IP:")
        log_info("1. Выйдите из сессии через меню")
        log_info("2. Запустите этот скрипт заново")
        
        await client.disconnect()
        log_success("\n✓ Сессия сохранена")
        
        return True
        
    except FloodWaitError as e:
        log_error(f"FloodWait: ждите {e.seconds} сек")
        return False
    except Exception as e:
        log_error(f"Ошибка: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


# =============================================================================
# МЕНЮ
# =============================================================================

def show_menu():
    """Главное меню"""
    
    while True:
        header("АВТОРИЗАЦИЯ С ПРОКСИ")
        
        print("  1. Войти с проверкой прокси")
        print("  2. Проверить прокси (без входа)")
        print("  3. Проверить текущий IP")
        print("  0. Выход")
        print()
        
        choice = input("Выбор (0-3): ").strip()
        
        if choice == '1':
            asyncio.run(auto_login_with_proxy())
        
        elif choice == '2':
            # Проверить прокси (без входа)
            header("ПРОВЕРКА ПРОКСИ")
            
            if PROXY_ENABLED and PROXY_HOST:
                result, ip, stats = asyncio.run(check_proxy_ip())
                if result:
                    log_success(f"✓ Прокси работает: {ip}")
                    log_info(f"  DNS запрос: {stats.get('dns_ms', 'N/A')} мс")
                    log_info(f"  Подключение: {stats.get('connect_ms', 'N/A')} мс")
                    log_info(f"  Общее время: {stats.get('total_ms', 'N/A')} мс")
                else:
                    log_error(f"✗ Прокси не работает: {ip}")
            else:
                log_warning("Прокси отключён в .env")
        
        elif choice == '3':
            # Проверить текущий IP
            header("ПРОВЕРКА IP")
            
            real_ip = asyncio.run(check_real_ip())
            log_info(f"Ваш реальный IP: {real_ip}")
            
            if PROXY_ENABLED and PROXY_HOST:
                try:
                    proxy_ip = socket.gethostbyname(PROXY_HOST)
                    log_info(f"IP прокси: {proxy_ip}")
                except Exception as e:
                    log_error(f"Не удалось получить IP прокси: {e}")
        
        elif choice == '0':
            log_info("Выход...")
            break
        
        input("\nНажмите Enter...")


# =============================================================================
# ЗАПУСК
# =============================================================================

if __name__ == "__main__":
    # Исправление для Windows (кодировка UTF-8)
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, errors='replace')
    
    try:
        show_menu()
    except KeyboardInterrupt:
        print("\nПрервано")
    except Exception as e:
        log_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
