"""
Test Multi-Account Proxy
Проверка прокси для каждого аккаунта из accounts.json

Запуск: python tests/test_multi_account_proxy.py
"""

import asyncio
import sys
from pathlib import Path

# Добавляем parent directory для импорта multi_account
BASE_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from multi_account import Config, ProxyManager


# =============================================================================
# ЦВЕТА
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
# ТЕСТИРОВАНИЕ
# =============================================================================

async def test_account_proxy(account: dict) -> bool:
    """
    Протестировать прокси для одного аккаунта

    Returns:
        True если прокси работает
    """
    acc_id = account.get('id')
    acc_name = account.get('name', f'Аккаунт {acc_id}')
    session_name = account.get('session_name', f'account_{acc_id}')
    api_id = int(account.get('api_id', 0))
    api_hash = account.get('api_hash', '')
    phone = account.get('phone', '')

    print(f"\n{'-' * 50}")
    print(f"АККАУНТ: {acc_name}")
    print(f"{'-' * 50}")

    # Проверка конфигурации
    if not api_id or not api_hash or not phone:
        log_warning("API credentials не заполнены!")
        return False

    # Проверка прокси
    proxy_config = account.get('proxy', {})
    if not proxy_config.get('enabled', False):
        log_info("Прокси отключён")
        return True  # Не ошибка, просто без прокси

    proxy_host = proxy_config.get('host', '')
    proxy_port = proxy_config.get('port', 0)

    if not proxy_host or not proxy_port:
        log_error("Прокси включён, но не настроен!")
        return False

    log_info(f"Прокси: {proxy_host}:{proxy_port}")

    # Создаём прокси менеджер
    from multi_account import AccountConfig
    from multi_account.proxy_manager import ProxyManager

    acc_config = AccountConfig(account)
    proxy_manager = ProxyManager()

    # Создаём клиента с прокси
    log_info("Создание клиента с прокси...")
    client = proxy_manager.create_client_with_proxy(acc_config)

    # Проверяем состояние прокси
    proxy_state = proxy_manager.get_proxy_state(acc_id)
    if proxy_state:
        if proxy_state.get('enabled'):
            log_success(f"Прокси настроен: {proxy_state.get('host')} → {proxy_state.get('ip')}:{proxy_state.get('port')}")
        else:
            log_error(f"Ошибка прокси: {proxy_state.get('error', 'Неизвестная')}")
            return False
    else:
        log_warning("Не удалось получить состояние прокси")

    # Подключаем
    log_info("Подключение к Telegram...")
    try:
        await client.connect()

        # Проверяем авторизацию
        if not await client.is_user_authorized():
            log_warning("Аккаунт не авторизован!")
            await client.disconnect()
            return False

        # Получаем информацию
        me = await client.get_me()
        log_success(f"✓ Подключено: {me.first_name} (@{me.username or 'no username'})")

        # Проверка IP через Telegram
        log_info("\nПроверьте уведомление от Telegram:")
        log_info(f"  Должен быть IP прокси: {proxy_host}")

        await client.disconnect()
        log_success("✓ Тест завершён успешно")

        return True

    except Exception as e:
        log_error(f"Ошибка подключения: {type(e).__name__}: {e}")
        await client.disconnect()
        return False


async def test_all_accounts():
    """Протестировать все аккаунты"""
    header("ТЕСТИРОВАНИЕ ПРОКСИ МУЛЬТИАККАУНТОВ")

    # Загружаем аккаунты
    accounts = Config.get_enabled_accounts()

    if not accounts:
        log_error("Нет включённых аккаунтов!")
        log_info("Настройте accounts.json")
        return

    log_info(f"Найдено аккаунтов: {len(accounts)}")

    # Тестируем каждый аккаунт
    results = {}
    for account in accounts:
        acc_id = account['id']
        success = await test_account_proxy(account)
        results[acc_id] = success

    # Итоги
    header("РЕЗУЛЬТАТЫ")

    total = len(results)
    success_count = sum(1 for v in results.values() if v)
    failed_count = total - success_count

    print(f"\n  Всего аккаунтов: {total}")
    print(f"  ✓ Успешно: {success_count}")
    print(f"  ✗ Ошибки: {failed_count}")

    if failed_count > 0:
        print(f"\n  Аккаунты с ошибками:")
        for acc_id, success in results.items():
            if not success:
                acc_name = next((a['name'] for a in accounts if a['id'] == acc_id), f"Аккаунт {acc_id}")
                print(f"    - {acc_name}")


def show_menu():
    """Главное меню"""
    while True:
        header("ТЕСТ ПРОКСИ МУЛЬТИАККАУНТОВ")

        print("\n  1. Тестировать все аккаунты")
        print("  2. Тестировать один аккаунт")
        print("  3. Показать конфигурацию аккаунтов")
        print("  0. Выход")
        print()

        choice = input("Выбор (0-3): ").strip()

        if choice == '1':
            # Тестировать все
            asyncio.run(test_all_accounts())

        elif choice == '2':
            # Тестировать один
            accounts = Config.get_enabled_accounts()

            if not accounts:
                log_error("Нет включённых аккаунтов!")
                continue

            print("\nДоступные аккаунты:")
            for acc in accounts:
                print(f"  {acc['id']}. {acc['name']}")

            acc_id = input("\nID аккаунта: ").strip()
            try:
                acc_id = int(acc_id)
                account = next((a for a in accounts if a['id'] == acc_id), None)

                if not account:
                    log_error("Аккаунт не найден!")
                    continue

                asyncio.run(test_account_proxy(account))
            except ValueError:
                log_error("Некорректный ID!")

        elif choice == '3':
            # Показать конфигурацию
            header("КОНФИГУРАЦИЯ АККАУНТОВ")

            accounts = Config.get_enabled_accounts()

            for acc in accounts:
                print(f"\n  Аккаунт {acc['id']}: {acc['name']}")
                print(f"    Сессия: {acc.get('session_name', 'N/A')}")
                print(f"    Телефон: {acc.get('phone', 'N/A')}")

                proxy = acc.get('proxy', {})
                if proxy.get('enabled'):
                    print(f"    Прокси: {proxy.get('host')}:{proxy.get('port')}")
                else:
                    print(f"    Прокси: отключён")

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
        input("\nНажмите Enter...")
