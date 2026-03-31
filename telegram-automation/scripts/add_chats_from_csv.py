"""
Add Chats from CSV Script
Добавление чатов из CSV файла в базу рассылки

Запуск: python scripts/add_chats_from_csv.py
"""

import csv
import json
import re
from pathlib import Path
from typing import List, Dict


# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

BASE_DIR = Path(__file__).parent.parent.resolve()
CHATS_FILE = BASE_DIR / 'config' / 'chats.json'

# Путь к CSV файлу
CSV_FILE = Path(r"C:\Users\ACER\OneDrive\Desktop\chat sorter\suitable_chats_rf_2026-03-25_14-33-54.csv")

# Сколько чатов добавить
CHATS_TO_ADD = 100


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
# ФУНКЦИИ
# =============================================================================

def extract_chat_id_from_link(link: str) -> str:
    """
    Извлечь ID чата из ссылки Telegram
    
    Примеры:
        https://t.me/channel_name -> channel_name
        https://t.me/+AbCdEfGhIjK -> +AbCdEfGhIjK
        https://t.me/c/1234567890 -> c/1234567890
    """
    if not link:
        return ""
    
    # Убираем пробелы
    link = link.strip()
    
    # Извлекаем username после t.me/
    match = re.search(r't\.me/([^\s,?]+)', link)
    if match:
        return match.group(1)
    
    return link


def load_existing_chats() -> List[Dict]:
    """Загрузить существующие чаты"""
    if not CHATS_FILE.exists():
        log_warning(f"Файл чатов не найден: {CHATS_FILE}")
        return []
    
    with open(CHATS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chats = data.get('chats', [])
    log_info(f"Загружено {len(chats)} существующих чатов")
    
    return chats


def load_chats_from_csv(csv_path: Path, limit: int = 100) -> List[Dict]:
    """
    Загрузить чаты из CSV файла простым построчным чтением
    
    CSV формат:
        chat_link,chat_title,users_count,dau_metric
    """
    if not csv_path.exists():
        log_error(f"CSV файл не найден: {csv_path}")
        return []
    
    chats = []
    existing_usernames = set()
    
    # Пробуем разные кодировки
    encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'latin-1']
    
    for encoding in encodings:
        try:
            with open(csv_path, 'r', encoding=encoding, errors='ignore') as f:
                lines = f.readlines()
                
            log_info(f"Прочитано строк: {len(lines)}")
            
            # Пропускаем заголовок
            start_idx = 0
            if lines and 'chat_link' in lines[0]:
                log_info(f"Кодировка определена: {encoding}")
                start_idx = 1
            
            count = 0
            for line in lines[start_idx:]:
                if count >= limit:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                # Разделяем по первой запятой (в названии могут быть запятые)
                parts = line.split(',', 3)
                
                if len(parts) < 2:
                    continue
                
                link = parts[0].strip()
                title = parts[1].strip()
                users_count = parts[2].strip() if len(parts) > 2 else '0'
                
                # Пропускаем пустые
                if not link or not title:
                    continue
                
                # Извлекаем username из ссылки
                username = extract_chat_id_from_link(link)
                
                if not username:
                    log_warning(f"Не удалось извлечь ID из ссылки: {link}")
                    continue
                
                # Проверяем дубликаты в CSV
                if username in existing_usernames:
                    continue
                
                existing_usernames.add(username)
                
                chats.append({
                    'id': username,
                    'name': title,
                    'type': 'channel',
                    'enabled': True,
                    'source': 'csv_import',
                    'users_count': int(users_count) if users_count.isdigit() else 0
                })
                
                count += 1
            
            log_success(f"Загружено {len(chats)} чатов из CSV")
            return chats
                    
        except Exception as e:
            log_warning(f"Кодировка {encoding} не подошла: {e}")
            continue
    
    log_error("Не удалось прочитать CSV ни в одной кодировке!")
    return []


def merge_chats(existing: List[Dict], new: List[Dict]) -> List[Dict]:
    """
    Объединить чаты, избегая дубликатов
    
    Returns:
        Обновлённый список чатов
    """
    # Создаём множество существующих ID
    existing_ids = {chat['id'] for chat in existing}
    
    # Добавляем только новые
    added_count = 0
    for chat in new:
        if chat['id'] not in existing_ids:
            existing.append(chat)
            added_count += 1
    
    log_info(f"Добавлено {added_count} новых чатов")
    log_info(f"Пропущено {len(new) - added_count} дубликатов")
    
    return existing


def save_chats(chats: List[Dict], total_added: int):
    """Сохранить чаты в JSON файл"""
    # Сортируем по имени
    chats.sort(key=lambda x: x.get('name', '').lower())
    
    # Создаём структуру
    data = {
        '_comment': f'Чаты для рассылки (+{total_added} из CSV)',
        '_version': '1.0.0',
        '_total': len(chats),
        '_last_updated': '2026-03-30',
        'chats': chats
    }
    
    # Создаём папку если нет
    CHATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем
    with open(CHATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    log_success(f"Сохранено {len(chats)} чатов в {CHATS_FILE}")


# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

def main():
    header("ДОБАВЛЕНИЕ ЧАТОВ ИЗ CSV")
    
    print(f"\n📁 CSV файл: {CSV_FILE}")
    print(f"📁 Файл чатов: {CHATS_FILE}")
    print(f"📊 Добавить чатов: {CHATS_TO_ADD}")
    print()
    
    # Проверка CSV файла
    if not CSV_FILE.exists():
        log_error(f"CSV файл не найден: {CSV_FILE}")
        log_info("Проверьте путь к файлу")
        input("\nНажмите Enter...")
        return
    
    # Загружаем существующие чаты
    log_info("Загрузка существующих чатов...")
    existing_chats = load_existing_chats()
    
    if not existing_chats:
        log_warning("Существующие чаты пусты!")
        log_info("Будет создана новая база")
    
    # Загружаем чаты из CSV
    log_info(f"Загрузка {CHATS_TO_ADD} чатов из CSV...")
    new_chats = load_chats_from_csv(CSV_FILE, CHATS_TO_ADD)
    
    if not new_chats:
        log_error("Не удалось загрузить чаты из CSV!")
        input("\nНажмите Enter...")
        return
    
    # Показываем превью
    print(f"\n📋 Первые 10 новых чатов:")
    for i, chat in enumerate(new_chats[:10], 1):
        print(f"  {i}. {chat['name']} (@{chat['id']})")
    
    # Подтверждение
    print()
    confirm = input(f"Добавить {len(new_chats)} чатов? (y/n): ").strip().lower()
    
    if confirm != 'y':
        log_info("Отменено")
        input("\nНажмите Enter...")
        return
    
    # Объединяем
    log_info("Объединение чатов...")
    updated_chats = merge_chats(existing_chats, new_chats)
    
    # Сохраняем
    log_info("Сохранение...")
    save_chats(updated_chats, len(new_chats))
    
    # Итоги
    header("ИТОГИ")
    print(f"\n✅ Добавлено чатов: {len(new_chats)}")
    print(f"📊 Всего чатов в базе: {len(updated_chats)}")
    print(f"\n📁 Файл: {CHATS_FILE}")
    
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
        main()
    except KeyboardInterrupt:
        print("\nПрервано")
    except Exception as e:
        log_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("\nНажмите Enter...")
