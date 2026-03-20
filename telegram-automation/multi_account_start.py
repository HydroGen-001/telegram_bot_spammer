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
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Добавляем parent directory в path для импорта multi_account
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from multi_account import Config, AccountConfig, AccountManager, MultiAccountBroadcaster

# Загружаем .env
load_dotenv()

# Глобальные API для новых аккаунтов (если не указаны в accounts.json)
DEFAULT_API_ID = int(os.getenv('API_ID', '0'))
DEFAULT_API_HASH = os.getenv('API_HASH', '')
DEFAULT_PHONE = os.getenv('PHONE', '')


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
        ready = "✓" if (acc.get('api_id') and acc.get('api_hash') and acc.get('phone')) else "✗"
        
        print(f"\n  {status} {acc.get('name', f'Аккаунт {acc.get(\"id\")}')}")
        print(f"      ID: {acc.get('id')}")
        print(f"      Готов: {ready}")
        print(f"      Сессия: {acc.get('session_name', 'N/A')}")
        print(f"      Телефон: {acc.get('phone', 'N/A')}")
        
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


def add_account():
    """Добавить новый аккаунт"""
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
    print("  9. Удалить аккаунт")
    print("  0. Назад")
    
    choice = input("\nВыбор (0-9): ").strip()
    
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
            print(f"  {i}. {t.get('name', f'Шаблон {t.get(\"id\")}')}")
        
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

async def run_broadcast():
    """Запустить рассылку"""
    log.header("ЗАПУСК РАССЫЛКИ")
    
    # Проверка аккаунтов
    data = Config.load_accounts()
    enabled_accounts = [a for a in data.get('accounts', []) if a.get('enabled', True)]
    ready_accounts = [a for a in enabled_accounts if a.get('api_id') and a.get('api_hash') and a.get('phone')]
    
    if not ready_accounts:
        log.error("Нет готовых аккаунтов!")
        log.info("Добавьте и настройте аккаунты в меню 'Аккаунты'")
        return
    
    # Проверка чатов
    chats = Config.get_chats()
    if not chats:
        log.error("Чаты пусты!")
        log.info("Загрузите базу чатов в config/chats.json")
        return
    
    # Выбор стратегии распределения
    print("\nРаспределение чатов:")
    print("  1. Равномерно (поровну между всеми)")
    print("  2. Пропорционально лимитам")
    
    strategy_choice = input("Выбор (1-2, Enter=1): ").strip()
    strategy = 'weighted' if strategy_choice == '2' else 'balanced'
    
    # Использование фото
    photo_choice = input("\nИспользовать фото? (y/n, Enter=y): ").strip().lower()
    use_photo = photo_choice != 'n'
    
    # Запуск
    broadcaster = MultiAccountBroadcaster()
    
    try:
        await broadcaster.run_broadcast(
            distribute_strategy=strategy,
            use_photo=use_photo
        )
    except KeyboardInterrupt:
        log.info("\n\nПрервано пользователем!")
    except Exception as e:
        log.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()


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
        ready = len([a for a in accounts if a.get('enabled', True) and a.get('api_id') and a.get('api_hash') and a.get('phone')])
        
        print(f"  Аккаунтов: {len(accounts)} (включено: {enabled}, готово: {ready})")
        print()
        print("  1. Запустить рассылку")
        print("  2. Аккаунты")
        print("  3. Добавить аккаунт")
        print("  4. Проверить сессии")
        print("  5. Статистика чатов")
        print("  0. Выход")
        print()
        
        choice = input("Выбор (0-5): ").strip()
        
        if choice == '1':
            asyncio.run(run_broadcast())
        
        elif choice == '2':
            show_accounts()
            
            # Меню редактирования
            acc_id = input("\nРедактировать аккаунт (ID или Enter=назад): ").strip()
            if acc_id:
                try:
                    edit_account(int(acc_id))
                except ValueError:
                    log.error("Неверный ID!")
        
        elif choice == '3':
            add_account()
        
        elif choice == '4':
            asyncio.run(check_sessions())
        
        elif choice == '5':
            chats = Config.get_chats()
            log.header("СТАТИСТИКА ЧАТОВ")
            print(f"  Всего: {len(chats)}")
            
            channels = len([c for c in chats if c.get('type') == 'channel'])
            groups = len([c for c in chats if c.get('type') == 'group'])
            print(f"  Каналов: {channels}")
            print(f"  Групп: {groups}")
        
        elif choice == '0':
            log.info("Выход...")
            break
        
        input("\nНажмите Enter...")


async def check_sessions():
    """Проверить все сессии"""
    log.header("ПРОВЕРКА СЕССИЙ")
    
    data = Config.load_accounts()
    accounts = data.get('accounts', [])
    
    if not accounts:
        log.warning("Аккаунты не настроены!")
        return
    
    for acc_data in accounts:
        account = AccountConfig(acc_data)
        
        if not account.is_ready():
            print(f"  ✗ {account.name}: не настроен")
            continue
        
        client = TelegramClient(str(account.session_path), account.api_id, account.api_hash)
        
        try:
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"  ✓ {account.name}: @{me.username or me.first_name}")
            else:
                print(f"  ✗ {account.name}: не авторизован")
            
            await client.disconnect()
        
        except Exception as e:
            print(f"  ✗ {account.name}: {type(e).__name__}")


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
