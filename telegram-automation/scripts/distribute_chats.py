"""
Distribute Chats Script
Распределение базы чатов по аккаунтам

Запуск: python scripts/distribute_chats.py
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

BASE_DIR = Path(__file__).parent.parent.resolve()
CONFIG_DIR = BASE_DIR / 'config'
ACCOUNTS_FILE = BASE_DIR / 'accounts.json'

# Пути к файлам
CHATS_BASE_FILE = CONFIG_DIR / 'chats_base.json'  # Общая база (3500 чатов)
CHATS_FILE = CONFIG_DIR / 'chats.json'  # Текущий файл с чатами

# Папки для аккаунтов
ACCOUNTS_DIR = CONFIG_DIR / 'accounts'

# Настройки распределения
CHATS_PER_ACCOUNT = 200  # Чатов на один аккаунт


# =============================================================================
# ЦВЕТА И ЛОГГЕР
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
# ЗАГРУЗКА ДАННЫХ
# =============================================================================

def load_chats_base() -> List[Dict]:
    """
    Загрузить базу чатов
    
    Пробует:
    1. chats_base.json (общая база)
    2. chats.json (текущий файл)
    """
    # Пробуем chats_base.json
    if CHATS_BASE_FILE.exists():
        log_info(f"Загрузка из {CHATS_BASE_FILE}")
        with open(CHATS_BASE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            chats = data.get('chats', [])
            log_success(f"Загружено {len(chats)} чатов из chats_base.json")
            return chats
    
    # Пробуем chats.json
    if CHATS_FILE.exists():
        log_info(f"Загрузка из {CHATS_FILE}")
        with open(CHATS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            chats = data.get('chats', [])
            log_success(f"Загружено {len(chats)} чатов из chats.json")
            return chats
    
    # Не найдено
    log_error("Файл с чатами не найден!")
    log_info(f"Создайте {CHATS_BASE_FILE} или {CHATS_FILE}")
    return []


def load_accounts() -> List[Dict]:
    """Загрузить список аккаунтов"""
    if not ACCOUNTS_FILE.exists():
        log_error(f"Файл {ACCOUNTS_FILE} не найден!")
        return []
    
    with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        accounts = data.get('accounts', [])
        enabled_accounts = [a for a in accounts if a.get('enabled', False)]
        
        log_info(f"Всего аккаунтов: {len(accounts)}")
        log_info(f"Включено аккаунтов: {len(enabled_accounts)}")
        
        return enabled_accounts


# =============================================================================
# РАСПРЕДЕЛЕНИЕ
# =============================================================================

def distribute_chats(chats: List[Dict], accounts: List[Dict], chats_per_account: int = 200) -> Dict[int, List[Dict]]:
    """
    Распределить чаты между аккаунтами
    
    Args:
        chats: Список чатов
        accounts: Список аккаунтов
        chats_per_account: Максимум чатов на аккаунт
    
    Returns:
        Dict[account_id, List[chats]]
    """
    distribution = {}
    chat_index = 0
    total_chats = len(chats)
    
    log_info(f"Распределение {total_chats} чатов на {len(accounts)} аккаунтов")
    log_info(f"Чатов на аккаунт: {chats_per_account}")
    
    for account in accounts:
        acc_id = account['id']
        acc_name = account.get('name', f"Аккаунт {acc_id}")
        
        # Выделяем чаты для этого аккаунта
        start_index = chat_index
        end_index = min(chat_index + chats_per_account, total_chats)
        
        acc_chats = chats[start_index:end_index]
        distribution[acc_id] = acc_chats
        
        log_info(f"  {acc_name}: {len(acc_chats)} чатов (#{start_index+1}-{end_index})")
        
        chat_index = end_index
        
        # Если чаты закончились
        if chat_index >= total_chats:
            log_warning("Чаты закончились!")
            break
    
    # Остаток чатов
    if chat_index < total_chats:
        remaining = total_chats - chat_index
        log_warning(f"Осталось {remaining} чатов без распределения")
        log_info("Увеличьте chats_per_account или добавьте аккаунты")
    
    return distribution


# =============================================================================
# СОХРАНЕНИЕ
# =============================================================================

def create_account_folders(distribution: Dict[int, List[Dict]]) -> Dict[int, Path]:
    """
    Создать папки для аккаунтов и сохранить чаты
    
    Returns:
        Dict[account_id, Path к файлу]
    """
    saved_files = {}
    
    # Создаём директорию
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    log_success(f"Папка аккаунтов: {ACCOUNTS_DIR}")
    
    for acc_id, chats in distribution.items():
        # Папка аккаунта
        acc_folder = ACCOUNTS_DIR / str(acc_id)
        acc_folder.mkdir(parents=True, exist_ok=True)
        
        # Файл с чатами
        chats_file = acc_folder / 'chats.json'
        
        # Данные для сохранения
        data = {
            "_comment": f"Чаты для аккаунта {acc_id} (автоматически распределено)",
            "_version": "1.0.0",
            "_created_at": datetime.now().isoformat(),
            "_total": len(chats),
            "chats": chats
        }
        
        # Сохраняем
        with open(chats_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        saved_files[acc_id] = chats_file
        log_success(f"  Аккаунт {acc_id}: сохранено {len(chats)} чатов → {chats_file}")
    
    return saved_files


# =============================================================================
# СТАТИСТИКА
# =============================================================================

def print_statistics(chats: List[Dict], accounts: List[Dict], distribution: Dict[int, List[Dict]], saved_files: Dict[int, Path]):
    """Вывести статистику распределения"""
    header("СТАТИСТИКА")
    
    total_chats = len(chats)
    total_distributed = sum(len(chats_list) for chats_list in distribution.values())
    total_accounts = len(accounts)
    
    print(f"\n📊 Общая база чатов: {total_chats}")
    print(f"👥 Аккаунтов: {total_accounts}")
    print(f"📁 Распределено: {total_distributed}")
    print(f"💾 Сохранено файлов: {len(saved_files)}")
    
    if total_distributed < total_chats:
        remaining = total_chats - total_distributed
        print(f"\n⚠️  Не распределено: {remaining} чатов")
        print(f"   Рекомендация: добавьте ещё {remaining // CHATS_PER_ACCOUNT + 1} аккаунт(а/ов)")
    
    print(f"\n📂 Файлы:")
    for acc_id, file_path in saved_files.items():
        print(f"   Аккаунт {acc_id}: {file_path}")
    
    print(f"\n📍 Папка аккаунтов: {ACCOUNTS_DIR}")


# =============================================================================
# МЕНЮ
# =============================================================================

def show_menu():
    """Главное меню"""
    
    while True:
        header("РАСПРЕДЕЛЕНИЕ ЧАТОВ")
        
        print(f"\n  База чатов: {CHATS_BASE_FILE.name}")
        print(f"  Аккаунты: {ACCOUNTS_FILE.name}")
        print(f"  Чатов на аккаунт: {CHATS_PER_ACCOUNT}")
        print(f"  Папка сохранения: {ACCOUNTS_DIR}")
        print()
        
        print("  1. Распределить чаты")
        print("  2. Изменить количество чатов на аккаунт")
        print("  3. Показать статистику текущей базы")
        print("  4. Открыть папку с аккаунтами")
        print("  0. Выход")
        print()
        
        choice = input("Выбор (0-4): ").strip()
        
        if choice == '1':
            # Распределить чаты
            header("РАСПРЕДЕЛЕНИЕ ЧАТОВ")
            
            chats = load_chats_base()
            if not chats:
                input("\nНажмите Enter...")
                continue
            
            accounts = load_accounts()
            if not accounts:
                input("\nНажмите Enter...")
                continue
            
            distribution = distribute_chats(chats, accounts, CHATS_PER_ACCOUNT)
            saved_files = create_account_folders(distribution)
            print_statistics(chats, accounts, distribution, saved_files)
            
            input("\nНажмите Enter...")
        
        elif choice == '2':
            # Изменить количество
            header("КОЛИЧЕСТВО ЧАТОВ НА АККАУНТ")
            
            print(f"\nТекущее значение: {CHATS_PER_ACCOUNT}")
            try:
                new_value = input("Новое значение (Enter для отмены): ").strip()
                if new_value:
                    global CHATS_PER_ACCOUNT
                    CHATS_PER_ACCOUNT = int(new_value)
                    log_success(f"Установлено: {CHATS_PER_ACCOUNT}")
            except ValueError:
                log_error("Некорректное число!")
            
            input("\nНажмите Enter...")
        
        elif choice == '3':
            # Статистика
            header("СТАТИСТИКА БАЗЫ")
            
            chats = load_chats_base()
            accounts = load_accounts()
            
            if chats and accounts:
                print(f"\n📊 Чатов в базе: {len(chats)}")
                print(f"👥 Аккаунтов: {len(accounts)}")
                print(f"📈 Нужно аккаунтов: {len(chats) // CHATS_PER_ACCOUNT + 1}")
                
                # Типы чатов
                channels = sum(1 for c in chats if c.get('type') == 'channel')
                chats_count = sum(1 for c in chats if c.get('type') == 'chat')
                print(f"\n📢 Каналов: {channels}")
                print(f"💬 Чатов: {chats_count}")
            
            input("\nНажмите Enter...")
        
        elif choice == '4':
            # Открыть папку
            header("ОТКРЫТИЕ ПАПКИ")
            
            if ACCOUNTS_DIR.exists():
                import os
                os.startfile(str(ACCOUNTS_DIR))
                log_success(f"Папка открыта: {ACCOUNTS_DIR}")
            else:
                log_warning("Папка ещё не создана")
            
            input("\nНажмите Enter...")
        
        elif choice == '0':
            # Выход
            log_info("Выход...")
            break
        
        else:
            log_warning("Неверный выбор")
            input("\nНажмите Enter...")


# =============================================================================
# ЗАПУСК
# =============================================================================

if __name__ == "__main__":
    import sys
    
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
