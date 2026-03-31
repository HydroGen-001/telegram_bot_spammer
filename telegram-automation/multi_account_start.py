"""
Multi-Account Telegram Broadcaster
Главное меню для управления мультиаккаунтной рассылкой

Запуск: python multi_account_start.py
"""

import asyncio
import json
import os
import sys
import io
import socket
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Добавляем parent directory в path для импорта multi_account
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from multi_account import Config, AccountConfig, AccountManager, MultiAccountBroadcaster, ProxyManager, ChatJoinManager

# Загружаем .env
load_dotenv()

# Глобальные API для новых аккаунтов (если не указаны в accounts.json)
DEFAULT_API_ID = int(os.getenv('API_ID', '0'))
DEFAULT_API_HASH = os.getenv('API_HASH', '')
DEFAULT_PHONE = os.getenv('PHONE', '')

# Путь к сессиям
SESSIONS_DIR = BASE_DIR / 'sessions'


# =============================================================================
# ЛОГГЕР
# =============================================================================

class Logger:
    COLORS = {
        'info': '\033[94m',
        'success': '\033[92m',
        'warning': '\033[93m',
        'error': '\033[91m',
        'reset': '\033[0m',
        'bold': '\033[1m'
    }

    def _c(self, level: str) -> str:
        return self.COLORS.get(level, '')

    def _r(self) -> str:
        return self.COLORS.get('reset', '')

    def info(self, msg: str):
        print(f"{self._c('info')}[INFO]{self._r()} {msg}")

    def success(self, msg: str):
        print(f"{self._c('success')}[OK]{self._r()} {msg}")

    def warning(self, msg: str):
        print(f"{self._c('warning')}[WARN]{self._r()} {msg}")

    def error(self, msg: str):
        print(f"{self._c('error')}[ERROR]{self._r()} {msg}")

    def header(self, msg: str):
        print(f"\n{self._c('bold')}{'=' * 60}{self._r()}")
        print(f"{self._c('bold')}{msg}{self._r()}")
        print(f"{self._c('bold')}{'=' * 60}{self._r()}", flush=True)


log = Logger()


# =============================================================================
# УПРАВЛЕНИЕ АККАУНТАМИ
# =============================================================================

def show_accounts():
    """Показать список аккаунтов"""
    log.header("АККАУНТЫ")

    data = Config.load_accounts()
    accounts = data.get('accounts', [])

    if not accounts:
        log.warning("Аккаунты не настроены!")
        return

    for acc in accounts:
        status = "✓" if acc.get('enabled', True) else "✗"
        has_api = bool(acc.get('api_id') and acc.get('api_hash'))
        has_phone = bool(acc.get('phone'))
        ready = "✓" if (has_api and has_phone) else "✗"

        # Проверяем наличие session файла
        session_name = acc.get('session_name', 'N/A')
        session_path = SESSIONS_DIR / f"{session_name}.session"
        session_exists = "✓" if session_path.exists() else "✗"

        acc_name = acc.get('name', f"Аккаунт {acc.get('id')}")
        print(f"\n  {status} {acc_name}")
        print(f"      ID: {acc.get('id')}")
        print(f"      Готов: {ready}")
        print(f"      Сессия: {session_name} [{session_exists}]")
        print(f"      Телефон: {acc.get('phone', 'N/A')}")

        # Прокси
        proxy = acc.get('proxy', {})
        if proxy and proxy.get('enabled'):
            proxy_status = "✓" if proxy.get('host') else "✗"
            print(f"      Прокси: {proxy_status} {proxy.get('host', '')}:{proxy.get('port', '')}")
        else:
            print(f"      Прокси: отключено")

        # Скрипт
        script = acc.get('script', {})
        if script.get('enabled'):
            if script.get('custom_text'):
                text_preview = script['custom_text'][:50].replace('\n', ' ')
                print(f"      Скрипт: {text_preview}...")
            elif script.get('template_id'):
                print(f"      Шаблон: ID={script['template_id']}")
        else:
            print(f"      Скрипт: не настроен")

        # Фото
        photo = acc.get('photo', {})
        if photo.get('enabled'):
            if photo.get('custom_path'):
                print(f"      Фото: {photo['custom_path']}")
            elif photo.get('use_default'):
                print(f"      Фото: по умолчанию")
        else:
            print(f"      Фото: отключено")


# =============================================================================
# ЗАГРУЗКА И РАСПРЕДЕЛЕНИЕ ЧАТОВ
# =============================================================================

def load_chats() -> List[Dict]:
    """Загрузить базу чатов"""
    chats = Config.get_chats()
    if not chats:
        log.warning("Чаты пусты! Загрузите базу в config/chats.json")
        return []
    log.success(f"Загружено {len(chats)} чатов")
    return chats


def distribute_chats_evenly(chats: List[Dict], accounts: List[Dict], chats_per_account: int = 200) -> Dict[int, List[Dict]]:
    """
    Распределить чаты между аккаунтами по N чатов на аккаунт
    Остаток не распределяется (если чатов больше чем мест)

    Args:
        chats: Список чатов
        accounts: Список аккаунтов
        chats_per_account: Количество чатов на аккаунт (по умолчанию 200)

    Returns:
        Dict[account_id, List[chats]]
    """
    distribution = {}
    chat_index = 0

    for acc in accounts:
        start = chat_index
        end = min(chat_index + chats_per_account, len(chats))
        distribution[acc['id']] = chats[start:end]
        chat_index = end

        # Если все чаты распределены — выходим
        if chat_index >= len(chats):
            break

    # Если остались нераспределённые чаты (аккаунтов не хватило)
    if chat_index < len(chats):
        remaining = len(chats) - chat_index
        print(f"\n  ⚠ Осталось {remaining} чатов без аккаунтов!")
        print(f"    Добавьте ещё аккаунтов или увеличьте лимит на аккаунт")

    return distribution


async def check_accounts_ready() -> List[Dict]:
    """
    Проверить готовность аккаунтов к рассылке

    Returns:
        Список готовых аккаунтов
    """
    log.header("ПРОВЕРКА ГОТОВНОСТИ АККАУНТОВ")

    data = Config.load_accounts()
    accounts = data.get('accounts', [])

    if not accounts:
        log.error("Аккаунты не настроены!")
        return []

    ready_accounts = []

    for acc in accounts:
        if not acc.get('enabled', True):
            acc_name = acc.get('name', 'Аккаунт ' + str(acc.get('id', '')))
            print(f"  ✗ {acc_name} - отключён")
            continue

        # Проверка данных
        has_api = bool(acc.get('api_id') and acc.get('api_hash'))
        has_phone = bool(acc.get('phone'))
        has_session = False

        session_name = acc.get('session_name', '')
        session_path = SESSIONS_DIR / f"{session_name}.session"
        if session_path.exists():
            has_session = True

        # Проверка авторизации (без таймаута — подключение сразу)
        is_authorized = False
        proxy_info = None

        if has_session and has_api:
            try:
                # Используем ProxyManager для корректной настройки прокси
                from multi_account import ProxyManager
                proxy_manager = ProxyManager()

                # Создаём конфигурацию аккаунта
                account_config = AccountConfig(acc)

                # Создаём клиента с прокси
                client = proxy_manager.create_client_with_proxy(account_config)

                # Подключение БЕЗ таймаута
                await client.connect()

                if await client.is_user_authorized():
                    is_authorized = True
                    me = await client.get_me()
                    username = me.username or me.first_name

                    # Получаем информацию о прокси
                    proxy_state = proxy_manager.get_proxy_state(acc.get('id', 0))
                    if proxy_state and proxy_state.get('enabled'):
                        proxy_info = f"{proxy_state.get('host')} → {proxy_state.get('ip')}:{proxy_state.get('port')}"

                await client.disconnect()

            except Exception as e:
                # Логирование ошибки для отладки
                print(f"      [DEBUG] Ошибка подключения: {type(e).__name__}: {e}")

        # Статус
        is_ready = has_api and has_phone and has_session and is_authorized
        status = "✓" if is_ready else "✗"

        reason = []
        if not has_api:
            reason.append("нет API")
        if not has_phone:
            reason.append("нет телефона")
        if not has_session:
            reason.append("нет сессии")
        if not is_authorized:
            reason.append("не авторизован")

        reason_str = ", ".join(reason) if reason else "готов"
        acc_name = acc.get('name', f"Аккаунт {acc.get('id')}")

        # Вывод с информацией о прокси
        if is_ready:
            print(f"  {status} {acc_name} - готов")
            if proxy_info:
                print(f"      Прокси: ✓ {proxy_info}")
        else:
            print(f"  ✗ {acc_name} - {reason_str}")

        if is_ready:
            ready_accounts.append(acc)

    print(f"\n  Готово: {len(ready_accounts)} из {len(accounts)}")

    return ready_accounts


def add_account():
    """Добавить новый аккаунт"""
    log.header("ДОБАВИТЬ АККАУНТ")

    print("\n  1. Создать новый аккаунт (с нуля)")
    print("  2. Импортировать из .session файла")
    print("  0. Назад")

    choice = input("\nВыбор (0-2): ").strip()

    if choice == '1':
        return add_account_new()
    elif choice == '2':
        return add_account_from_session()
    else:
        return None


def add_account_new():
    """Добавить новый аккаунт (с нуля)"""
    log.header("ДОБАВИТЬ АККАУНТ")

    data = Config.load_accounts()
    accounts = data.get('accounts', [])

    # Генерируем новый ID
    new_id = max([a.get('id', 0) for a in accounts], default=0) + 1

    # Создаём конфигурацию
    new_account = {
        'id': new_id,
        'name': f'Аккаунт {new_id}',
        'enabled': True,
        'session_name': f'account_{new_id}',
        'api_id': DEFAULT_API_ID,
        'api_hash': DEFAULT_API_HASH,
        'phone': DEFAULT_PHONE,
        'script': {
            'enabled': False,
            'template_id': None,
            'custom_text': None
        },
        'photo': {
            'enabled': True,
            'use_default': True,
            'custom_path': None
        },
        'limits': {
            'use_global': True,
            'daily_limit': 500,
            'min_delay': 50,
            'max_delay': 100
        }
    }

    accounts.append(new_account)
    data['accounts'] = accounts

    Config.save_accounts(data)
    log.success(f"Добавлен аккаунт {new_id}")
    log.info("Теперь выберите 'Авторизовать аккаунт' для входа")

    return new_id


def add_account_from_session():
    """Импортировать аккаунт из .session файла"""
    log.header("ИМПОРТ ИЗ SESSION ФАЙЛА")

    data = Config.load_accounts()
    accounts = data.get('accounts', [])

    # Генерируем новый ID
    new_id = max([a.get('id', 0) for a in accounts], default=0) + 1

    # Поиск .session файлов
    sessions_dir = BASE_DIR / 'sessions'
    if not sessions_dir.exists():
        sessions_dir.mkdir(parents=True, exist_ok=True)

    session_files = list(sessions_dir.glob('*.session'))

    if not session_files:
        log.warning("Нет .session файлов в папке sessions/")
        log.info("Поместите .session файл в папку: sessions/")
        return None

    print("\nДоступные .session файлы:")
    for i, f in enumerate(session_files, 1):
        print(f"  {i}. {f.name}")

    print(f"\n  {len(session_files) + 1}. Ввести путь вручную")
    print("  0. Назад")

    choice = input("\nВыбор (0-{max}): ".format(max=len(session_files) + 1)).strip()

    if choice == '0':
        return None

    session_path = None

    if choice.isdigit() and 1 <= int(choice) <= len(session_files):
        session_path = session_files[int(choice) - 1]
    elif choice == str(len(session_files) + 1):
        path = input("Путь к .session файлу: ").strip()
        session_path = Path(path)
        if not session_path.exists():
            log.error("Файл не найден!")
            return None
    else:
        log.error("Неверный выбор!")
        return None

    # Проверяем сессию и извлекаем данные
    log.info(f"Проверка сессии: {session_path.name}")

    session_data = asyncio.run(extract_session_data(session_path))

    if not session_data:
        log.error("Не удалось прочитать сессию!")
        return None

    # Создаём имя сессии
    session_name = session_path.stem  # имя без .session

    # Создаём конфигурацию с данными из сессии
    new_account = {
        'id': new_id,
        'name': f'Аккаунт {new_id} ({session_data.get("username") or session_data.get("first_name", session_name.upper())})',
        'enabled': True,
        'session_name': session_name,
        'api_id': DEFAULT_API_ID,  # Используем дефолтный API
        'api_hash': DEFAULT_API_HASH,
        'phone': session_data.get('phone', ''),
        'proxy': {
            'enabled': False,
            'host': '',
            'port': 0,
            'username': '',
            'password': ''
        },
        'script': {
            'enabled': False,
            'template_id': None,
            'custom_text': None
        },
        'photo': {
            'enabled': True,
            'use_default': True,
            'custom_path': None
        },
        'limits': {
            'use_global': True,
            'daily_limit': 500,
            'min_delay': 50,
            'max_delay': 100
        }
    }

    accounts.append(new_account)
    data['accounts'] = accounts

    Config.save_accounts(data)
    log.success(f"Импортирован аккаунт {new_id} из {session_path.name}")
    log.info(f"  Телефон: {session_data.get('phone', 'N/A')}")
    log.info(f"  Username: @{session_data.get('username', 'N/A')}")
    log.info("Аккаунт готов к работе!")

    return new_id


async def validate_session(session_path: Path):
    """Проверить сессию и получить информацию"""
    from telethon import TelegramClient

    # Временный клиент для проверки
    client = TelegramClient(str(session_path), DEFAULT_API_ID, DEFAULT_API_HASH)

    try:
        await client.connect()

        if await client.is_user_authorized():
            me = await client.get_me()
            log.success(f"✓ Сессия активна: @{me.username or me.first_name}")
            log.info(f"  ID: {me.id}")
            log.info(f"  Телефон: {me.phone or 'скрыт'}")
            return {
                'user_id': me.id,
                'phone': me.phone,
                'username': me.username,
                'first_name': me.first_name
            }
        else:
            log.warning("Сессия не авторизована")
            return None

        await client.disconnect()

    except Exception as e:
        log.error(f"Ошибка сессии: {e}")
        return None


async def extract_session_data_to_account(account: Dict):
    """Извлечь данные из сессии и обновить аккаунт"""
    log.header(f"ИЗВЛЕЧЕНИЕ ДАННЫХ: {account.get('name', '')}")

    session_name = account.get('session_name', '')
    session_path = SESSIONS_DIR / f"{session_name}.session"

    if not session_path.exists():
        log.error(f"Сессия не найдена: {session_path}")
        return

    log.info(f"Чтение сессии: {session_path.name}")

    session_data = await extract_session_data(session_path)

    if not session_data:
        log.error("Не удалось прочитать данные из сессии!")
        return

    # Обновляем данные аккаунта
    if session_data.get('phone'):
        account['phone'] = session_data['phone']
        log.success(f"Телефон: {session_data['phone']}")

    if session_data.get('username'):
        log.success(f"Username: @{session_data['username']}")

    # Обновляем имя аккаунта
    current_name = account.get('name', '')
    new_username = session_data.get('username') or session_data.get('first_name', '')
    if new_username and current_name.startswith('Аккаунт'):
        account['name'] = f"Аккаунт {account.get('id')} ({new_username.upper()})"
        log.success(f"Название: {account['name']}")

    # Сохраняем
    data = Config.load_accounts()
    accounts = data.get('accounts', [])
    for i, acc in enumerate(accounts):
        if acc.get('id') == account.get('id'):
            accounts[i] = account
            break
    data['accounts'] = accounts
    Config.save_accounts(data)

    log.success("Данные сохранены!")


async def extract_session_data(session_path: Path) -> Optional[Dict]:
    """Извлечь данные из сессии (API ID, телефон, username)"""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    try:
        # Создаём клиента для чтения сессии
        client = TelegramClient(str(session_path), DEFAULT_API_ID, DEFAULT_API_HASH)
        await client.connect()

        if await client.is_user_authorized():
            me = await client.get_me()

            # Получаем данные сессии
            session_data = {
                'phone': me.phone,
                'user_id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name
            }

            await client.disconnect()
            return session_data

        await client.disconnect()
        return None

    except Exception as e:
        log.error(f"Ошибка при чтении сессии: {e}")
        return None


def edit_account(account_id: int):
    """Редактировать аккаунт"""
    log.header(f"РЕДАКТИРОВАТЬ АККАУНТ {account_id}")

    data = Config.load_accounts()
    accounts = data.get('accounts', [])

    account = next((a for a in accounts if a.get('id') == account_id), None)
    if not account:
        log.error("Аккаунт не найден!")
        return

    print("\nЧто изменить:")
    print("  1. Название")
    print("  2. API ID")
    print("  3. API Hash")
    print("  4. Телефон")
    print("  5. Включён/Выключен")
    print("  6. Настроить скрипт")
    print("  7. Настроить фото")
    print("  8. Настроить лимиты")
    print("  9. Извлечь данные из сессии")
    print("  10. Удалить аккаунт")
    print("  0. Назад")

    choice = input("\nВыбор (0-10): ").strip()

    if choice == '1':
        new_name = input(f"Название [{account.get('name', '')}]: ").strip()
        if new_name:
            account['name'] = new_name

    elif choice == '2':
        new_api_id = input(f"API ID [{account.get('api_id', '')}]: ").strip()
        if new_api_id:
            account['api_id'] = int(new_api_id)

    elif choice == '3':
        new_api_hash = input(f"API Hash [{account.get('api_hash', '')}]: ").strip()
        if new_api_hash:
            account['api_hash'] = new_api_hash

    elif choice == '4':
        new_phone = input(f"Телефон [{account.get('phone', '')}]: ").strip()
        if new_phone:
            account['phone'] = new_phone

    elif choice == '5':
        current = account.get('enabled', True)
        account['enabled'] = not current
        log.success(f"Аккаунт {'включён' if account['enabled'] else 'выключен'}")

    elif choice == '6':
        configure_script(account)

    elif choice == '7':
        configure_photo(account)

    elif choice == '8':
        configure_limits(account)

    elif choice == '9':
        asyncio.run(extract_session_data_to_account(account))

    elif choice == '10':
        confirm = input("Удалить аккаунт? (y/n): ").strip().lower()
        if confirm == 'y':
            accounts = [a for a in accounts if a.get('id') != account_id]
            data['accounts'] = accounts
            log.success("Аккаунт удалён")

    elif choice == '0':
        return
    
    data['accounts'] = accounts
    Config.save_accounts(data)
    log.success("Сохранено!")


def configure_script(account: Dict):
    """Настроить скрипт для аккаунта"""
    log.header(f"СКРИПТ: {account.get('name', '')}")
    
    print("\n  1. Включить скрипт")
    print("  2. Выбрать шаблон")
    print("  3. Ввести свой текст")
    print("  4. Отключить скрипт")
    print("  0. Назад")
    
    choice = input("\nВыбор (0-4): ").strip()
    
    if 'script' not in account:
        account['script'] = {}
    
    if choice == '1':
        account['script']['enabled'] = True
        log.success("Скрипт включён")
    
    elif choice == '2':
        templates = Config.get_templates()
        template_list = templates.get('templates', [])

        if not template_list:
            log.warning("Шаблоны не найдены!")
            return

        print("\nДоступные шаблоны:")
        for i, t in enumerate(template_list, 1):
            template_name = t.get('name', f"Шаблон {t.get('id')}")
            print(f"  {i}. {template_name}")

        idx = input(f"Выберите (1-{len(template_list)}): ").strip()
        try:
            idx = int(idx) - 1
            if 0 <= idx < len(template_list):
                account['script']['template_id'] = template_list[idx].get('id')
                account['script']['enabled'] = True
                log.success(f"Выбран шаблон: {template_list[idx].get('name')}")
        except ValueError:
            pass
    
    elif choice == '3':
        print("\nВведите текст (пустая строка = отмена):")
        text = input("> ").strip()
        if text:
            account['script']['custom_text'] = text
            account['script']['enabled'] = True
            log.success("Текст сохранён")
    
    elif choice == '4':
        account['script']['enabled'] = False
        log.success("Скрипт отключён")


def configure_photo(account: Dict):
    """Настроить фото для аккаунта"""
    log.header(f"ФОТО: {account.get('name', '')}")
    
    print("\n  1. Включить фото")
    print("  2. Использовать фото по умолчанию")
    print("  3. Указать свой путь")
    print("  4. Отключить фото")
    print("  0. Назад")
    
    choice = input("\nВыбор (0-4): ").strip()
    
    if 'photo' not in account:
        account['photo'] = {}
    
    if choice == '1':
        account['photo']['enabled'] = True
        log.success("Фото включено")
    
    elif choice == '2':
        account['photo']['use_default'] = True
        account['photo']['custom_path'] = None
        log.success("Будет использоваться фото по умолчанию")
    
    elif choice == '3':
        path = input("Путь к фото: ").strip()
        if path:
            p = Path(path)
            if p.exists():
                account['photo']['custom_path'] = str(p)
                account['photo']['use_default'] = False
                account['photo']['enabled'] = True
                log.success("Путь сохранён")
            else:
                log.error("Файл не найден!")
    
    elif choice == '4':
        account['photo']['enabled'] = False
        log.success("Фото отключено")


def configure_limits(account: Dict):
    """Настроить лимиты для аккаунта"""
    log.header(f"ЛИМИТЫ: {account.get('name', '')}")
    
    if 'limits' not in account:
        account['limits'] = {'use_global': True}
    
    print("\n  1. Использовать глобальные настройки")
    print("  2. Задать свои лимиты")
    print("  0. Назад")
    
    choice = input("\nВыбор (0-2): ").strip()
    
    if choice == '1':
        account['limits']['use_global'] = True
        log.success("Будут использоваться глобальные настройки")
    
    elif choice == '2':
        account['limits']['use_global'] = False
        
        daily = input(f"Дневной лимит [{account['limits'].get('daily_limit', 500)}]: ").strip()
        if daily:
            account['limits']['daily_limit'] = int(daily)
        
        min_delay = input(f"Мин. задержка [{account['limits'].get('min_delay', 50)}]: ").strip()
        if min_delay:
            account['limits']['min_delay'] = int(min_delay)
        
        max_delay = input(f"Макс. задержка [{account['limits'].get('max_delay', 100)}]: ").strip()
        if max_delay:
            account['limits']['max_delay'] = int(max_delay)
        
        log.success("Лимиты обновлены")


async def auth_account_interactive(account_id: int):
    """Авторизовать аккаунт интерактивно"""
    log.header(f"АВТОРИЗАЦИЯ: Аккаунт {account_id}")
    
    data = Config.load_accounts()
    account_data = next((a for a in data.get('accounts', []) if a.get('id') == account_id), None)
    
    if not account_data:
        log.error("Аккаунт не найден!")
        return
    
    account = AccountConfig(account_data)
    
    if not account.is_ready():
        log.error("Аккаунт не настроен! Заполните API credentials.")
        return
    
    client = TelegramClient(str(account.session_path), account.api_id, account.api_hash)
    
    try:
        await client.connect()
        
        # Проверяем, авторизован ли уже
        if await client.is_user_authorized():
            me = await client.get_me()
            log.success(f"Уже авторизовано: @{me.username or me.first_name}")
            await client.disconnect()
            return
        
        # Отправляем код
        log.info(f"Отправка кода на {account.phone}...")
        await client.send_code_request(account.phone)
        log.success("Код отправлен!")
        
        # Вводим код
        code = input("\nКод из Telegram: ").strip()
        if not code:
            log.error("Код не введён!")
            return
        
        # Пробуем войти
        try:
            await client.sign_in(phone=account.phone, code=code)
        except SessionPasswordNeededError:
            log.info("2FA включён")
            password = input("Пароль: ").strip()
            await client.sign_in(password=password)
        
        me = await client.get_me()
        log.success(f"✓ Авторизовано: @{me.username or me.first_name}")
        
    except Exception as e:
        log.error(f"Ошибка: {e}")
    
    finally:
        await client.disconnect()


# =============================================================================
# РАССЫЛКА
# =============================================================================

async def send_message_with_photo(
    client: TelegramClient,
    chat_id: str,
    text: str,
    photo_path: Optional[Path] = None,
    forward_from_msg_id: Optional[int] = None
) -> bool:
    """
    Отправить сообщение: текст + фото/пересылка
    Возвращает True если текст отправлен
    """
    from telethon.errors import FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError

    # Проверка: chat_id не должен быть пустым
    if not chat_id or not chat_id.strip():
        return False

    # 1. Отправляем текст
    try:
        await client.send_message(chat_id, text)
    except FloodWaitError as e:
        log.warning(f"FloodWait: ждём {e.seconds} сек")
        await asyncio.sleep(e.seconds)
        await client.send_message(chat_id, text)
    except ChatWriteForbiddenError:
        # Нет прав на запись в канале
        return False
    except ChannelPrivateError:
        # Частный канал, нет доступа
        return False
    except ValueError as e:
        # Ошибка: чат не найден
        log.warning(f"Чат не найден: {chat_id}")
        return False
    except Exception as e:
        error_name = type(e).__name__
        # Пропускаем ошибки записи в каналы
        if 'WriteForbidden' in error_name or 'ChannelPrivate' in error_name:
            return False
        else:
            log.error(f"Текст не отправлен: {error_name}: {e}")
            return False

    # 2. Отправляем фото или пересылаем из избранного
    if photo_path and photo_path.exists():
        try:
            await client.send_file(chat_id, photo_path)
        except FloodWaitError as e:
            log.warning(f"FloodWait (фото): {e.seconds} сек")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            # Фото не критично
            pass
    elif forward_from_msg_id:
        try:
            await client.forward_messages(chat_id, forward_from_msg_id, from_peer='me')
        except FloodWaitError as e:
            log.warning(f"FloodWait (пересылка): {e.seconds} сек")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            pass

    return True


async def broadcast_with_account(
    client: TelegramClient,
    account: Dict,
    chats: List[Dict],
    text: str,
    photo_path: Optional[Path] = None,
    min_delay: int = 50,
    max_delay: int = 100,
    start_from: int = 0
) -> Dict:
    """
    Рассылка с одного аккаунта с логированием и возможностью продолжения
    
    Args:
        start_from: Индекс чата, с которого продолжить (0 = с начала)
    """
    import random
    from telethon.errors import ChatWriteForbiddenError, ChannelPrivateError

    stats = {'total': len(chats), 'sent': 0, 'failed': 0, 'errors': [], 'last_index': start_from}
    
    # Перемешиваем только если начинаем с начала
    if start_from == 0:
        random.shuffle(chats)
    
    # Заголовок рассылки
    print(f"\n{'=' * 70}", flush=True)
    print(f"📤 РАССЫЛКА: {len(chats) - start_from} чатов, с позиции {start_from}", flush=True)
    print(f"{'=' * 70}", flush=True)
    
    for i, chat in enumerate(chats[start_from:], start_from):
        chat_id = chat['id']
        chat_name = chat.get('name', chat_id)[:55]

        # Отправка
        success = await send_message_with_photo(
            client,
            chat_id,
            text,
            photo_path,
            forward_from_msg_id=None
        )

        if success:
            stats['sent'] += 1
            print(f"  [{i + 1:3d}/{len(chats)}] ✅ ОТПРАВЛЕНО | {chat_name}", flush=True)
        else:
            stats['failed'] += 1
            stats['errors'].append({'chat': chat_name, 'id': chat_id, 'error': 'Нет доступа'})
            print(f"  [{i + 1:3d}/{len(chats)}] ❌ НЕ ВЫШЛО   | {chat_name}", flush=True)

        # Сохраняем прогресс
        stats['last_index'] = i + 1

        # Задержка
        if i < len(chats) - 1:
            delay = random.randint(min_delay, max_delay)
            mins, secs = divmod(delay, 60)
            print(f"\r      ⏳ Пауза: {mins:02d}:{secs:02d}  ", end='', flush=True)
            await asyncio.sleep(delay)
            print("          ", end='', flush=True)  # Очистка строки
            print("\r", end='', flush=True)

    # Итоговый отчёт
    print(f"\n{'=' * 70}", flush=True)
    print(f"📊 ОТЧЁТ О РАССЫЛКЕ", flush=True)
    print(f"{'=' * 70}", flush=True)
    print(f"\n  ✅ Успешно:     {stats['sent']}", flush=True)
    print(f"  ❌ Ошибки:      {stats['failed']}", flush=True)
    print(f"  📋 Всего:       {stats['total']}", flush=True)
    
    if stats['total'] > 0:
        rate = stats['sent'] / stats['total'] * 100
        print(f"  📈 Процент:     {rate:.1f}%", flush=True)
    
    if stats['errors']:
        print(f"\n⚠️  ОШИБКИ ({len(stats['errors'])}):", flush=True)
        for err in stats['errors'][:10]:
            print(f"     • {err.get('chat', 'Unknown')[:50]}: {err.get('error', 'Unknown')}", flush=True)
        if len(stats['errors']) > 10:
            print(f"     ... и ещё {len(stats['errors']) - 10}", flush=True)
    
    print(f"\n{'=' * 70}\n", flush=True)

    return stats


async def broadcast_with_account_resume(
    client: TelegramClient,
    account: Dict,
    chats: List[Dict],
    text: str,
    photo_path: Optional[Path] = None,
    min_delay: int = 50,
    max_delay: int = 100,
    start_from: int = 0
) -> Dict:
    """Обёртка для совместимости — использует broadcast_with_account"""
    return await broadcast_with_account(
        client, account, chats, text, photo_path, min_delay, max_delay, start_from
    )


async def run_broadcast():
    """Запустить рассылку с проверкой готовности и логированием"""
    log.header("ЗАПУСК РАССЫЛКИ")

    # 1. Проверка готовности аккаунтов
    ready_accounts = await check_accounts_ready()

    if not ready_accounts:
        log.error("Нет готовых аккаунтов!")
        log.info("Настройте аккаунты в меню 'Аккаунты'")
        return

    # 2. Загрузка чатов
    chats = load_chats()
    if not chats:
        log.error("Чаты пусты!")
        return

    # 3. Выбор стратегии распределения
    print("\nРаспределение чатов:")
    print("  1. По 200 чатов на аккаунт")
    print("  2. Равномерно (поровну между всеми)")
    print("  3. Пропорционально лимитам")

    strategy_choice = input("Выбор (1-3, Enter=1): ").strip()

    if strategy_choice == '2':
        strategy = 'balanced'
    elif strategy_choice == '3':
        strategy = 'weighted'
    else:
        strategy = 'even_200'

    # 4. Распределение чатов
    if strategy == 'even_200':
        distribution = distribute_chats_evenly(chats, ready_accounts, chats_per_account=200)
    else:
        # Используем встроенное распределение из AccountManager
        manager = AccountManager()
        manager.accounts = [AccountConfig(acc) for acc in ready_accounts]
        distribution = manager.distribute_chats(chats, strategy)

    # Предпросмотр распределения
    log.header("РАСПРЕДЕЛЕНИЕ ЧАТОВ")
    print(f"  Чатов всего: {len(chats)}")
    print(f"  Аккаунтов готово: {len(ready_accounts)}")
    print()
    print("  Распределение по аккаунтам:")
    for acc_id, acc_chats in distribution.items():
        acc = next((a for a in ready_accounts if a.get('id') == acc_id), None)
        if acc:
            print(f"    {acc.get('name', f'Аккаунт {acc_id}')}: {len(acc_chats)} чатов")
    print()
    print("  1. Начать рассылку")
    print("  2. Изменить распределение")
    print("  3. Выйти в меню")
    print()

    choice = input("  Выбор (1-3, Enter=1): ").strip()

    if choice == '2':
        # Вернуться к выбору стратегии
        return await run_broadcast()
    elif choice == '3':
        return

    # 5. Фото используется всегда
    use_photo = True
    log.info("\n✓ Фото будет использоваться")

    # 6. Запуск рассылки
    log.info("=" * 40)
    log.info("НАЧАЛО РАССЫЛКИ")
    log.info("=" * 40)

    total_stats = {'total': 0, 'sent': 0, 'failed': 0, 'errors': []}
    start_time = datetime.now()

    try:
        # Параллельный запуск для всех аккаунтов
        tasks = []

        for acc_id, acc_chats in distribution.items():
            if not acc_chats:
                continue

            acc = next((a for a in ready_accounts if a.get('id') == acc_id), None)
            if not acc:
                continue

            # Создаём клиента
            session_name = acc.get('session_name', '')
            session_path = SESSIONS_DIR / f"{session_name}.session"

            client = TelegramClient(
                str(session_path),
                acc.get('api_id', 0),
                acc.get('api_hash', '')
            )

            # Настройка прокси
            proxy = acc.get('proxy', {})
            if proxy and proxy.get('enabled') and proxy.get('host'):
                import socket
                try:
                    proxy_ip = socket.gethostbyname(proxy.get('host'))
                    # Определяем тип прокси (по умолчанию HTTP для мобильных прокси)
                    proxy_type = proxy.get('proxy_type', 'http')
                    proxy_dict = {
                        'proxy_type': proxy_type,
                        'addr': proxy_ip,
                        'port': proxy.get('port', 0),
                    }
                    if proxy.get('username'):
                        proxy_dict['username'] = proxy.get('username')
                    if proxy.get('password'):
                        proxy_dict['password'] = proxy.get('password')
                    client.set_proxy(proxy_dict)
                    log.info(f"Прокси: {proxy.get('host')} → {proxy_ip}:{proxy.get('port')} ({proxy_type})")
                except Exception as e:
                    log.warning(f"Не удалось настроить прокси: {e}")

            # Получаем текст
            acc_config = AccountConfig(acc)
            text = acc_config.get_text()
            if not text:
                log.warning(f"Аккаунт {acc_id}: текст не настроен, пропускаем")
                continue

            # Получаем фото
            photo_path = None
            if use_photo:
                photo_path = acc_config.get_photo_path()

            # Запуск с индексом 0 (с начала)
            tasks.append(
                broadcast_task(client, acc, acc_chats, text, photo_path, start_from=0)
            )

        # Выполняем все задачи
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Собираем статистику
        for result in results:
            if isinstance(result, dict):
                total_stats['total'] += result.get('total', 0)
                total_stats['sent'] += result.get('sent', 0)
                total_stats['failed'] += result.get('failed', 0)
                total_stats['errors'].extend(result.get('errors', [])[:5])

    except KeyboardInterrupt:
        log.info("\n\nПрервано пользователем!")
    except Exception as e:
        log.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

    # 7. Итоговый отчёт
    end_time = datetime.now()
    duration = end_time - start_time

    log.header("ОТЧЁТ О РАССЫЛКЕ")
    print(f"  Время:         {duration}")
    print(f"  Чатов всего:   {total_stats['total']}")
    print(f"  Успешно:       {total_stats['sent']}")
    print(f"  Ошибки:        {total_stats['failed']}")

    if total_stats['total'] > 0:
        success_rate = total_stats['sent'] / total_stats['total'] * 100
        print(f"  Процент:       {success_rate:.1f}%")

    if total_stats['errors']:
        print(f"\n  Ошибки ({len(total_stats['errors'])}):")
        for err in total_stats['errors'][:10]:
            print(f"    - {err.get('chat', 'Unknown')}: {err.get('error', 'Unknown')}")


async def broadcast_task(
    client: TelegramClient,
    account: Dict,
    chats: List[Dict],
    text: str,
    photo_path: Optional[Path] = None,
    start_from: int = 0
):
    """
    Задача рассылки для одного аккаунта с авто-перезапуском
    
    Args:
        start_from: Индекс чата, с которого продолжить (для перезапуска)
    """
    import random
    from telethon.errors import ChatWriteForbiddenError, ChannelPrivateError, FloodWaitError
    
    acc_name = account.get('name', f"Аккаунт {account.get('id')}")
    reconnect_attempts = 0
    max_reconnect_attempts = 5
    
    stats = {'total': len(chats), 'sent': 0, 'failed': 0, 'errors': [], 'last_index': start_from}
    
    while reconnect_attempts < max_reconnect_attempts:
        try:
            # Подключение
            if not await client.is_user_authorized():
                await client.connect()
            
            if not await client.is_user_authorized():
                log.error(f"{acc_name}: не авторизован")
                await client.disconnect()
                return {'total': len(chats), 'sent': 0, 'failed': len(chats), 'errors': [], 'last_index': start_from}
            
            me = await client.get_me()
            
            # Если это перезапуск — логируем
            if start_from > 0:
                log.info(f"\n{'=' * 40}")
                log.info(f"{acc_name} (@{me.username or me.first_name}) - ПЕРЕЗАПУСК с чата #{start_from}")
                log.info(f"{'=' * 40}")
            else:
                log.info(f"\n{'=' * 40}")
                log.info(f"{acc_name} (@{me.username or me.first_name})")
                log.info(f"Чатов: {len(chats)}")
                log.info(f"{'=' * 40}")
            
            limits = account.get('limits', {})
            min_delay = limits.get('min_delay', 50)
            max_delay = limits.get('max_delay', 100)
            
            # Рассылка с продолжения
            stats = await broadcast_with_account_resume(
                client,
                account,
                chats,
                text,
                photo_path,
                min_delay,
                max_delay,
                start_from
            )
            
            log.info(f"\n✓ {acc_name} завершил: {stats['sent']}/{len(chats) - start_from}")
            
            await client.disconnect()
            return stats
            
        except (ChatWriteForbiddenError, ChannelPrivateError) as e:
            # Эти ошибки не критичны — просто пропускаем чат
            reconnect_attempts += 1
            continue
            
        except FloodWaitError as e:
            log.warning(f"{acc_name}: FloodWait {e.seconds} сек, ждём...")
            await asyncio.sleep(e.seconds)
            reconnect_attempts += 1
            
        except Exception as e:
            error_name = type(e).__name__
            log.error(f"{acc_name}: {error_name}: {e}")
            
            # Критические ошибки — пробуем переподключиться
            if 'ConnectionError' in error_name or 'DisconnectError' in error_name or 'TimeoutError' in error_name:
                reconnect_attempts += 1
                if reconnect_attempts < max_reconnect_attempts:
                    log.info(f"{acc_name}: Переподключение (попытка {reconnect_attempts}/{max_reconnect_attempts})...")
                    await asyncio.sleep(5)
                    try:
                        await client.disconnect()
                        await client.connect()
                    except:
                        pass
                    continue
            
            await client.disconnect()
            return {'total': len(chats), 'sent': stats.get('sent', 0), 'failed': stats.get('failed', 0), 'errors': stats.get('errors', []), 'last_index': stats.get('last_index', start_from)}
    
    # Превышено количество попыток
    log.error(f"{acc_name}: Превышено количество попыток подключения ({max_reconnect_attempts})")
    await client.disconnect()
    return {'total': len(chats), 'sent': stats.get('sent', 0), 'failed': stats.get('failed', 0), 'errors': stats.get('errors', []), 'last_index': stats.get('last_index', start_from)}


# =============================================================================
# МЕНЮ
# =============================================================================

def show_menu():
    """Главное меню"""

    while True:
        log.header("MULTI-ACCOUNT BROADCASTER")

        data = Config.load_accounts()
        accounts = data.get('accounts', [])
        enabled = len([a for a in accounts if a.get('enabled', True)])

        print(f"  Аккаунтов: {len(accounts)} (включено: {enabled})")
        print()
        print("  1. Запустить рассылку")
        print("  2. Проверить готовность аккаунтов")
        print("  3. Аккаунты")
        print("  4. Добавить аккаунт")
        print("  5. Загрузить чаты из Telegram")
        print("  6. Импортировать чаты из CSV")
        print("  7. Вступить в чаты (из базы)")
        print("  8. Распределить чаты (по 200 на аккаунт)")
        print("  9. Статистика чатов")
        print("  10. Проверить сессии")
        print("  0. Выход")
        print()

        choice = input("Выбор (0-10): ").strip()

        if choice == '1':
            asyncio.run(run_broadcast())

        elif choice == '2':
            asyncio.run(check_accounts_ready())

        elif choice == '3':
            show_accounts()

            # Меню редактирования
            acc_id = input("\nРедактировать аккаунт (ID или Enter=назад): ").strip()
            if acc_id:
                try:
                    edit_account(int(acc_id))
                except ValueError:
                    log.error("Неверный ID!")

        elif choice == '4':
            add_account()

        elif choice == '5':
            asyncio.run(auth_and_collect_chats())

        elif choice == '6':
            import_chats_from_csv_menu()

        elif choice == '7':
            asyncio.run(join_chats_from_base_menu())

        elif choice == '8':
            distribute_chats_menu()

        elif choice == '9':
            chats = Config.get_chats()
            log.header("СТАТИСТИКА ЧАТОВ")
            print(f"  Всего: {len(chats)}")

            channels = len([c for c in chats if c.get('type') == 'channel'])
            groups = len([c for c in chats if c.get('type') == 'group'])
            print(f"  Каналов: {channels}")
            print(f"  Групп: {groups}")

            if chats:
                print("\nПервые 10:")
                for i, c in enumerate(chats[:10], 1):
                    print(f"  {i}. {c.get('name', c.get('id'))}")

        elif choice == '8':
            asyncio.run(check_sessions())

        elif choice == '0':
            log.info("Выход...")
            break

        input("\nНажмите Enter...")


async def auth_and_collect_chats():
    """Авторизация и сбор чатов (с прокси)"""
    log.header("СБОР ЧАТОВ")

    data = Config.load_accounts()
    accounts = data.get('accounts', [])

    if not accounts:
        log.error("Аккаунты не настроены!")
        return

    # Используем первый доступный аккаунт
    account = None
    for acc in accounts:
        if acc.get('enabled') and acc.get('api_id') and acc.get('api_hash'):
            account = acc
            break

    if not account:
        log.error("Нет аккаунтов с API credentials!")
        return

    session_name = account.get('session_name', '')
    session_path = SESSIONS_DIR / f"{session_name}.session"

    client = TelegramClient(str(session_path), account.get('api_id', 0), account.get('api_hash', ''))

    # Настройка прокси если включено
    proxy = account.get('proxy', {})
    if proxy and proxy.get('enabled') and proxy.get('host'):
        import socket
        try:
            proxy_ip = socket.gethostbyname(proxy.get('host'))
            # Определяем тип прокси (по умолчанию HTTP для мобильных прокси)
            proxy_type = proxy.get('proxy_type', 'http')
            proxy_dict = {
                'proxy_type': proxy_type,
                'addr': proxy_ip,
                'port': proxy.get('port', 0),
            }
            if proxy.get('username'):
                proxy_dict['username'] = proxy.get('username')
            if proxy.get('password'):
                proxy_dict['password'] = proxy.get('password')
            client.set_proxy(proxy_dict)
            log.info(f"Прокси: {proxy.get('host')} → {proxy_ip}:{proxy.get('port')} ({proxy_type})")
        except Exception as e:
            log.warning(f"Не удалось настроить прокси: {e}")

    try:
        await client.connect()

        if not await client.is_user_authorized():
            log.error("Не авторизовано! Сначала авторизуйте аккаунт")
            await client.disconnect()
            return

        me = await client.get_me()
        log.success(f"В системе: @{me.username or me.first_name}")

        # Сбор чатов
        from telethon.tl.types import Chat, Channel, User

        chats_data = []
        log.info("Сбор чатов...")

        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, User):
                continue
            if isinstance(entity, (Chat, Channel)):
                chat_id = entity.username if hasattr(entity, 'username') and entity.username else str(entity.id)
                title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
                chat_type = "channel" if isinstance(entity, Channel) else "chat"
                chats_data.append({
                    'id': chat_id,
                    'name': title,
                    'type': chat_type,
                    'enabled': True
                })

        chats_data.sort(key=lambda x: x['name'].lower())

        # Сохранение
        chats_path = BASE_DIR / 'config' / 'chats.json'
        chats_path.parent.mkdir(parents=True, exist_ok=True)

        with open(chats_path, 'w', encoding='utf-8') as f:
            json.dump({
                '_comment': 'Чаты для рассылки',
                '_total': len(chats_data),
                'chats': chats_data
            }, f, ensure_ascii=False, indent=2)

        log.success(f"Сохранено {len(chats_data)} чатов")

        if chats_data:
            print("\nПервые 10:")
            for i, c in enumerate(chats_data[:10], 1):
                print(f"  {i}. {c['name']}")

        await client.disconnect()

    except Exception as e:
        log.error(f"Ошибка: {e}")
        if 'client' in locals():
            await client.disconnect()


def distribute_chats_menu():
    """Меню распределения чатов"""
    log.header("РАСПРЕДЕЛЕНИЕ ЧАТОВ")

    data = Config.load_accounts()
    accounts = data.get('accounts', [])
    enabled_accounts = [a for a in accounts if a.get('enabled', True)]

    if not enabled_accounts:
        log.error("Нет включённых аккаунтов!")
        return

    chats = Config.get_chats()
    if not chats:
        log.error("Чаты пусты! Загрузите базу чатов")
        return

    print(f"  Чатов: {len(chats)}")
    print(f"  Аккаунтов: {len(enabled_accounts)}")
    print()

    # Распределение по 200
    distribution = distribute_chats_evenly(chats, enabled_accounts, chats_per_account=200)

    print("Распределение (по 200 чатов на аккаунт):")
    for acc_id, acc_chats in distribution.items():
        acc = next((a for a in enabled_accounts if a.get('id') == acc_id), None)
        if acc:
            print(f"  {acc.get('name', f'Аккаунт {acc_id}')}: {len(acc_chats)} чатов")

    # Детальный просмотр
    print("\n  1. Показать чаты по аккаунтам")
    print("  2. Сохранить распределение")
    print("  0. Назад")
    print()

    choice = input("  Выбор (0-2): ").strip()

    if choice == '1':
        for acc_id, acc_chats in distribution.items():
            acc = next((a for a in enabled_accounts if a.get('id') == acc_id), None)
            if acc:
                print(f"\n  {acc.get('name', f'Аккаунт {acc_id}')} ({len(acc_chats)} чатов):")
                for i, c in enumerate(acc_chats[:10], 1):
                    print(f"    {i}. {c.get('name')}")
                if len(acc_chats) > 10:
                    print(f"    ... и ещё {len(acc_chats) - 10}")

    elif choice == '2':
        log.success("Распределение сохранено (будет использовано при рассылке)")

    log.success("Чаты распределены!")


async def join_chats_from_base_menu():
    """Меню вступления в чаты из базы для выбранного аккаунта"""
    log.header("ВСТУПЛЕНИЕ В ЧАТЫ (ИЗ БАЗЫ)")

    data = Config.load_accounts()
    accounts = data.get('accounts', [])
    enabled_accounts = [a for a in accounts if a.get('enabled', True)]

    if not enabled_accounts:
        log.error("Нет включённых аккаунтов!")
        return

    chats = Config.get_chats()
    if not chats:
        log.error("Чаты пусты! Загрузите базу чатов")
        return

    # Выбор аккаунта
    print("  Доступные аккаунты:")
    for acc in enabled_accounts:
        acc_name = acc.get('name', 'Аккаунт ' + str(acc.get('id', '')))
        print(f"    {acc.get('id')}. {acc_name}")
    print()

    acc_choice = input(f"  Выберите аккаунт (1-{len(enabled_accounts)}, Enter=1): ").strip()
    try:
        acc_idx = int(acc_choice) - 1 if acc_choice else 0
        acc_idx = max(0, min(acc_idx, len(enabled_accounts) - 1))
    except ValueError:
        acc_idx = 0

    selected_account = enabled_accounts[acc_idx]
    log.info(f"Выбран аккаунт: {selected_account.get('name')}")

    # Выбор количества чатов
    print("\nСколько чатов вступить?")
    max_chats = input("  Введите число (Enter=50): ").strip()
    max_join = int(max_chats) if max_chats.isdigit() else 50

    # Создаём менеджер вступления
    join_manager = ChatJoinManager()

    try:
        # Подключение аккаунта с повторными попытками
        print("\nПодключение аккаунта...")

        session_name = selected_account.get('session_name', '')
        session_path = SESSIONS_DIR / f"{session_name}.session"

        if not session_path.exists():
            log.error(f"Сессия не найдена: {session_path}")
            return

        connected = False
        
        # Получаем и настраиваем прокси (как в start.py)
        proxy_config = selected_account.get('proxy', {})
        proxy_dict = None
        proxy_info = ""
        
        if proxy_config and proxy_config.get('enabled') and proxy_config.get('host'):
            try:
                proxy_ip = socket.gethostbyname(proxy_config.get('host'))
                proxy_info = f"{proxy_config.get('host')} → {proxy_ip}:{proxy_config.get('port')}"
                log.info(f"Прокси: {proxy_info}")
                
                # Формат для HTTP-прокси (мобильные прокси)
                # Используем http вместо socks5
                proxy_dict = {
                    'proxy_type': 'http',  # HTTP CONNECT для мобильных прокси
                    'addr': proxy_ip,
                    'port': proxy_config.get('port', 0),
                }
                if proxy_config.get('username'):
                    proxy_dict['username'] = proxy_config.get('username')
                if proxy_config.get('password'):
                    proxy_dict['password'] = proxy_config.get('password')
            except Exception as e:
                log.warning(f"Не удалось получить IP прокси: {e}")
                proxy_ip = proxy_config.get('host')
        
        # 5 попыток подключения
        for attempt in range(5):
            try:
                # Пауза перед повторной попыткой
                if attempt > 0:
                    wait_time = (attempt + 1) * 10
                    log.info(f"Попытка {attempt + 1}/5 через {wait_time} сек...")
                    await asyncio.sleep(wait_time)
                
                # Создаём клиента С ПРОКСИ (как в start.py)
                client = TelegramClient(str(session_path), 
                                        selected_account.get('api_id', 0), 
                                        selected_account.get('api_hash', ''))
                
                # Настраиваем прокси ПОСЛЕ создания клиента (как в start.py)
                if proxy_dict:
                    client.set_proxy(proxy_dict)
                    log.info("SOCKS5 прокси настроен через set_proxy(dict)")
                
                # Подключение
                log.info(f"Подключение (попытка {attempt + 1}/5)...")
                await client.connect()
                
                if await client.is_user_authorized():
                    await join_manager.add_client(selected_account.get('id'), client)
                    log.success(f"✓ {selected_account.get('name')} подключён")
                    connected = True
                    break
                else:
                    log.error(f"✗ {selected_account.get('name')}: не авторизован")
                    await client.disconnect()
                    break
                    
            except asyncio.TimeoutError:
                log.warning(f"Таймаут подключения (попытка {attempt + 1}/5)")
                continue
            except OSError as e:
                log.warning(f"Ошибка сети (попытка {attempt + 1}/5): {type(e).__name__}")
                continue
            except Exception as e:
                error_msg = str(e)
                if 'Server closed' in error_msg or 'Connection error' in error_msg:
                    log.warning(f"Разрыв соединения (попытка {attempt + 1}/5)")
                    continue
                else:
                    log.error(f"Ошибка: {type(e).__name__}: {e}")
                    break
        
        # Финальная проверка
        if not connected:
            log.error("Не удалось подключиться после 5 попыток")
            log.info("Попробуйте:")
            log.info("  1. Проверить прокси (пункт 10)")
            log.info("  2. Сменить прокси на другой порт")
            log.info("  3. Проверить интернет-соединение")
            return

        # Вступление в чаты
        print("\n" + "=" * 40)
        print("ВСТУПЛЕНИЕ В ЧАТЫ ИЗ БАЗЫ")
        print(f"Лимит: {max_join} чатов")
        print("=" * 40)

        stats = await join_manager.join_chats_for_account(
            selected_account.get('id'),
            chats,  # Все чаты из базы
            max_join_per_session=max_join,
            delay_between_joins=(30, 60),
            delay_already_member=(5, 15)
        )

        # Статистика
        log.header("ИТОГ")
        print(f"  Вступил: {stats.get('joined', 0)}")
        print(f"  Уже был: {stats.get('already', 0)}")
        print(f"  Ошибки: {stats.get('failed', 0)}")

        if stats.get('failed', 0) > 0:
            print(f"\n  ⚠ {stats['failed']} чатов недоступны для вступления")

    except Exception as e:
        log.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await join_manager.disconnect_all()


async def join_chats_menu():
    """Меню вступления в чаты"""
    log.header("ВСТУПЛЕНИЕ В ЧАТЫ")

    data = Config.load_accounts()
    accounts = data.get('accounts', [])
    enabled_accounts = [a for a in accounts if a.get('enabled', True)]

    if not enabled_accounts:
        log.error("Нет включённых аккаунтов!")
        return

    chats = Config.get_chats()
    if not chats:
        log.error("Чаты пусты! Загрузите базу чатов")
        return

    print(f"  Чатов в базе: {len(chats)}")
    print(f"  Аккаунтов включено: {len(enabled_accounts)}")
    print()

    # Выбор количества чатов на аккаунт
    print("Сколько чатов выделять на аккаунт?")
    chats_per_acc = input("  Введите число (Enter=50): ").strip()
    chats_per_account = int(chats_per_acc) if chats_per_acc.isdigit() else 50

    # Создаём менеджер вступления
    join_manager = ChatJoinManager()

    try:
        # Подключаем аккаунты с повторными попытками
        print("\nПодключение аккаунтов...")

        for acc in enabled_accounts:
            session_name = acc.get('session_name', '')
            session_path = SESSIONS_DIR / f"{session_name}.session"

            if not session_path.exists():
                print(f"  ✗ {acc.get('name')}: сессия не найдена")
                continue

            # Попытки подключения (до 3 раз)
            connected = False
            for attempt in range(3):
                try:
                    client = TelegramClient(
                        str(session_path),
                        acc.get('api_id', 0),
                        acc.get('api_hash', ''),
                        timeout=30,  # Увеличенный таймаут
                        flood_sleep_threshold=300
                    )

                    # Настройка прокси
                    proxy = acc.get('proxy', {})
                    if proxy and proxy.get('enabled') and proxy.get('host'):
                        try:
                            proxy_ip = socket.gethostbyname(proxy.get('host'))
                            proxy_dict = {
                                'proxy_type': 'socks5',
                                'addr': proxy_ip,
                                'port': proxy.get('port', 0),
                            }
                            if proxy.get('username'):
                                proxy_dict['username'] = proxy.get('username')
                            if proxy.get('password'):
                                proxy_dict['password'] = proxy.get('password')
                            client.set_proxy(proxy_dict)
                        except Exception as e:
                            print(f"  ⚠ Не удалось настроить прокси: {e}")

                    # Подключение с таймаутом
                    await asyncio.wait_for(client.connect(), timeout=30)

                    if await client.is_user_authorized():
                        await join_manager.add_client(acc.get('id'), client)
                        print(f"  ✓ {acc.get('name')} подключён")
                        connected = True
                        break
                    else:
                        print(f"  ✗ {acc.get('name')}: не авторизован")
                        await client.disconnect()
                        break

                except asyncio.TimeoutError:
                    if attempt < 2:
                        print(f"  ⚠ {acc.get('name')}: таймаут (попытка {attempt + 1}/3), повтор...")
                        await asyncio.sleep(5)
                    else:
                        print(f"  ✗ {acc.get('name')}: не удалось подключиться (3 попытки)")
                        break
                except OSError as e:
                    if attempt < 2:
                        print(f"  ⚠ {acc.get('name')}: ошибка сети (попытка {attempt + 1}/3), повтор...")
                        await asyncio.sleep(5)
                    else:
                        print(f"  ✗ {acc.get('name')}: ошибка сети - {e}")
                        break
                except Exception as e:
                    print(f"  ✗ {acc.get('name')}: {type(e).__name__}: {e}")
                    break

            if not connected:
                continue

        # Распределение и вступление
        print("\n" + "=" * 40)
        print("РАСПРЕДЕЛЕНИЕ И ВСТУПЛЕНИЕ")
        print("=" * 40)

        distribution = await join_manager.distribute_and_join(
            enabled_accounts,
            chats,
            chats_per_account=chats_per_account
        )

        # Вступление для каждого аккаунта
        for acc_id, acc_chats in distribution.items():
            if not acc_chats:
                continue

            acc = next((a for a in enabled_accounts if a.get('id') == acc_id), None)
            if not acc:
                continue

            print(f"\n{'=' * 40}")
            print(f"Аккаунт: {acc.get('name', f'Аккаунт {acc_id}')}")
            print(f"{'=' * 40}")

            stats = await join_manager.join_chats_for_account(
                acc_id,
                acc_chats,
                max_join_per_session=50,
                delay_between_joins=(30, 60),      # Задержка после вступления (30-60 сек)
                delay_already_member=(5, 15)       # Задержка если уже в чате (5-15 сек)
            )

            # Статистика
            print(f"\n  Статистика:")
            print(f"    Вступил: {stats.get('joined', 0)}")
            print(f"    Уже был: {stats.get('already', 0)}")
            print(f"    Ошибки: {stats.get('failed', 0)}")

        # Итог
        log.header("ИТОГ")
        total_joined = sum(s.get('joined', 0) for s in join_manager.get_all_stats().values())
        total_already = sum(s.get('already', 0) for s in join_manager.get_all_stats().values())
        total_failed = sum(s.get('failed', 0) for s in join_manager.get_all_stats().values())

        print(f"  Вступили: {total_joined}")
        print(f"    Уже были: {total_already}")
        print(f"  Ошибки: {total_failed}")

        if total_failed > 0:
            print(f"\n  ⚠ {total_failed} чатов недоступны для вступления")
            print("    (частные каналы или требуется приглашение)")

    except Exception as e:
        log.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await join_manager.disconnect_all()


def import_chats_from_csv_menu():
    """Меню импорта чатов из CSV"""
    log.header("ИМПОРТ ЧАТОВ ИЗ CSV")

    print("Введите путь к CSV файлу:")
    print(f"  (по умолчанию: C:\\Users\\ACER\\OneDrive\\Desktop\\chat sorter\\suitable_chats_rf_*.csv)")
    print()

    csv_path_str = input("Путь: ").strip()

    if not csv_path_str:
        # Используем последний найденный файл
        import glob
        mask = r"C:\Users\ACER\OneDrive\Desktop\chat sorter\suitable_chats_rf_*.csv"
        files = glob.glob(mask)
        if files:
            csv_path_str = max(files)  # Последний по дате
            log.info(f"Выбран файл: {csv_path_str}")
        else:
            log.error("CSV файлы не найдены!")
            return

    csv_path = Path(csv_path_str)

    if not csv_path.exists():
        log.error(f"Файл не найден: {csv_path}")
        return

    # Импорт
    log.info("Импорт чатов...")

    try:
        import csv
        from urllib.parse import urlparse

        chats_data = []

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            for row in reader:
                chat_link = row.get('chat_link', '')
                chat_title = row.get('chat_title', '')
                users_count = row.get('users_count', '0')
                dau_metric = row.get('dau_metric', '')

                if not chat_title:
                    continue

                # Извлекаем ID из ссылки
                chat_id = chat_link.strip()
                if 't.me/' in chat_link:
                    parsed = urlparse(chat_link)
                    path = parsed.path.strip('/')
                    if '?' in path:
                        path = path.split('?')[0]
                    chat_id = path

                # Пропускаем чаты без ID
                if not chat_id or not chat_id.strip():
                    continue

                chat_type = "channel"

                chats_data.append({
                    'id': chat_id,
                    'name': chat_title,
                    'type': chat_type,
                    'enabled': True,
                    'users_count': int(users_count) if users_count.isdigit() else 0,
                    'dau_metric': dau_metric
                })

        # Сортировка
        chats_data.sort(key=lambda x: x['name'].lower())

        # Сохранение
        chats_path = BASE_DIR / 'config' / 'chats.json'
        chats_path.parent.mkdir(parents=True, exist_ok=True)

        with open(chats_path, 'w', encoding='utf-8') as f:
            json.dump({
                '_comment': 'Чаты для рассылки (импорт из CSV)',
                '_version': '1.0.0',
                '_source': str(csv_path),
                '_total': len(chats_data),
                'chats': chats_data
            }, f, ensure_ascii=False, indent=2)

        log.success(f"Импортировано {len(chats_data)} чатов!")
        log.info(f"Файл: {chats_path}")

        if chats_data:
            # Статистика
            total_users = sum(c.get('users_count', 0) for c in chats_data)
            print(f"\n  Всего чатов: {len(chats_data)}")
            print(f"  Суммарно участников: {total_users:,}")

            print("\nПервые 10 чатов:")
            for i, c in enumerate(chats_data[:10], 1):
                users = c.get('users_count', 0)
                dau = c.get('dau_metric', '')
                print(f"  {i}. {c['name']} ({users:,} уч. | DAU {dau})")

    except Exception as e:
        log.error(f"Ошибка импорта: {e}")
        import traceback
        traceback.print_exc()


async def check_sessions():
    """Проверить все сессии с прокси"""
    log.header("ПРОВЕРКА СЕССИЙ")

    data = Config.load_accounts()
    accounts = data.get('accounts', [])

    if not accounts:
        log.warning("Аккаунты не настроены!")
        return

    # Создаём прокси менеджер
    proxy_manager = ProxyManager()

    for acc_data in accounts:
        account = AccountConfig(acc_data)

        if not account.is_ready():
            print(f"  ✗ {account.name}: не настроен")
            continue

        # Создаём клиента с прокси
        client = proxy_manager.create_client_with_proxy(account)

        try:
            await asyncio.wait_for(client.connect(), timeout=10)

            if await client.is_user_authorized():
                me = await client.get_me()

                # Инфо о прокси
                proxy_state = proxy_manager.get_proxy_state(account.id)
                if proxy_state and proxy_state.get('enabled'):
                    proxy_info = f"✓ {proxy_state.get('host')} → {proxy_state.get('ip')}:{proxy_state.get('port')}"
                else:
                    proxy_info = "Без прокси"

                print(f"  ✓ {account.name}: @{me.username or me.first_name}")
                print(f"    Прокси: {proxy_info}")
            else:
                print(f"  ✗ {account.name}: не авторизован")

            await client.disconnect()

        except asyncio.TimeoutError:
            print(f"  ✗ {account.name}: таймаут подключения")
        except Exception as e:
            print(f"  ✗ {account.name}: {type(e).__name__}: {str(e)[:50]}")


# =============================================================================
# ЗАПУСК
# =============================================================================

if __name__ == "__main__":
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    try:
        show_menu()
    except KeyboardInterrupt:
        print("\nПрервано")
    except Exception as e:
        log.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
