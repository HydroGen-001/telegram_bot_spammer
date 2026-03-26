"""
Скрипт для сравнения чатов из папки Telegram с локальной базой
"""

import asyncio
import json
import os
import sys
import io
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.tl.types import Chat, Channel, User

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

load_dotenv()

# Базовая директория — где лежит скрипт
BASE_DIR = Path(__file__).parent.resolve()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')

SESSION_PATH = BASE_DIR / 'sessions/folder_compare'
BASE_PATH = BASE_DIR / 'config/chats.json'
REPORT_PATH = BASE_DIR / 'logs/folder_compare_report.json'

# Название папки для сравнения (как она называется в Telegram)
# FOLDER_NAME = None  # <-- оставьте None для сравнения основной папки
FOLDER_NAME = "Новые"  # <-- раскомментируйте и укажите точное название
FOLDER_ID = None  # ID папки для сравнения (будет найдена по названию)


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
        print(f"{self._c('bold')}{'=' * 60}{self._r()}")


log = Logger()


# =============================================================================
# ФУНКЦИИ
# =============================================================================

def load_base_chats() -> List[Dict[str, Any]]:
    """Загрузить чаты из базы"""
    if not BASE_PATH.exists():
        log.warning(f"База не найдена: {BASE_PATH}")
        return []
    
    with open(BASE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    chats = data.get('chats', [])
    log.success(f"Загружено {len(chats)} чатов из базы")
    return chats


async def get_telegram_chats(client: TelegramClient) -> List[Dict]:
    """Получить все чаты и папки"""
    log.info("Получение списка чатов из Telegram...")
    
    chats = []
    folders_info = {}  # folder_id -> folder_name
    
    # Получаем пользовательские папки через API
    try:
        from telethon.tl.functions.folders import GetDialogFiltersRequest
        from telethon.tl.types import DialogFilter
        
        filters = await client(GetDialogFiltersRequest())
        for f in filters:
            if isinstance(f, DialogFilter):
                folders_info[f.id] = f.title
                log.info(f"Найдена папка: {f.title} (ID={f.id})")
    except Exception as e:
        log.warning(f"Не удалось получить список папок: {e}")
    
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        
        if isinstance(entity, User):
            continue
        
        if isinstance(entity, (Chat, Channel)):
            chat_id = entity.username if entity.username else str(entity.id)
            title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            chat_type = "channel" if isinstance(entity, Channel) else "chat"
            folder_id = getattr(dialog, 'folder_id', 0)
            
            chats.append({
                'id': chat_id,
                'name': title,
                'type': chat_type,
                'folder_id': folder_id if folder_id is not None else 0
            })
    
    return chats, folders_info


def compare_chats(folder_chats: List[Dict], base_chats: List[Dict]) -> Dict:
    """Сравнить чаты"""
    folder_ids = {c['id'] for c in folder_chats}
    base_ids = {c['id'] for c in base_chats}
    
    only_in_folder = folder_ids - base_ids
    only_in_base = base_ids - folder_ids
    in_both = folder_ids & base_ids
    
    folder_map = {c['id']: c for c in folder_chats}
    base_map = {c['id']: c for c in base_chats}
    
    return {
        'summary': {
            'total_in_folder': len(folder_chats),
            'total_in_base': len(base_chats),
            'common_chats': len(in_both),
            'new_chats': len(only_in_folder),
            'missing_chats': len(only_in_base)
        },
        'new_chats': [folder_map[id] for id in sorted(only_in_folder)],
        'missing_chats': [base_map[id] for id in sorted(only_in_base)],
        'common_chats': [{'id': id, 'name': folder_map[id]['name']} for id in sorted(in_both)]
    }


def save_report(result: Dict, folder_name: str = "Основная"):
    """Сохранить отчет"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'folder_name': folder_name,
        'folder_id': FOLDER_ID,
        **result
    }
    
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    log.success(f"Отчет сохранен: {REPORT_PATH}")


def print_results(result: Dict, folder_name: str = "Основная"):
    """Вывести результаты"""
    log.header(f"РЕЗУЛЬТАТЫ СРАВНЕНИЯ (папка: {folder_name})")
    
    s = result['summary']
    print(f"\nСтатистика:")
    print(f"   В папке Telegram:  {s['total_in_folder']}")
    print(f"   В базе данных:     {s['total_in_base']}")
    print(f"   Общие:             {s['common_chats']}")
    print(f"   Новые:             {s['new_chats']}")
    print(f"   Отсутствуют:       {s['missing_chats']}")
    
    if result['new_chats']:
        log.header(f"НОВЫЕ ЧАТЫ ({len(result['new_chats'])})")
        for i, c in enumerate(result['new_chats'], 1):
            print(f"   {i}. {c['name']}")
            print(f"      ID: {c['id']} | Тип: {c['type']}")
    
    if result['missing_chats']:
        log.header(f"ОТСУТСТВУЮЩИЕ ЧАТЫ ({len(result['missing_chats'])})")
        for i, c in enumerate(result['missing_chats'], 1):
            print(f"   {i}. {c['name']}")
            print(f"      ID: {c['id']} | Тип: {c['type']}")


# =============================================================================
# MAIN
# =============================================================================

async def main():
    global FOLDER_ID
    
    log.header("Сравнение чатов из папки Telegram с базой")
    log.info(f"Искомая папка: '{FOLDER_NAME}'")
    
    # Проверка конфигурации
    if API_ID == 0 or not API_HASH or not PHONE:
        log.error("Не заполнены API credentials!")
        log.info("Проверьте файл .env")
        return
    
    # Загрузка базы
    base_chats = load_base_chats()
    
    # Подключение
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    
    try:
        await client.start(phone=PHONE)
        me = await client.get_me()
        log.success(f"Подключено: {me.first_name}")
        
        # Получение чатов и папок
        all_chats, folders_info = await get_telegram_chats(client)
        
        # Отображение всех папок
        folders: Dict[int, List[Dict]] = {}
        for c in all_chats:
            folders.setdefault(c['folder_id'], []).append(c)
        
        log.header("Обнаруженные папки")
        print(f"   ID=0: Основная ({len(folders.get(0, []))} чатов)")
        for fid, fname in folders_info.items():
            print(f"   ID={fid}: {fname} ({len(folders.get(fid, []))} чатов)")
        
        # Поиск нужной папки по названию
        if FOLDER_NAME:
            for fid, fname in folders_info.items():
                if fname.lower() == FOLDER_NAME.lower():
                    FOLDER_ID = fid
                    log.success(f"Найдена папка '{FOLDER_NAME}' (ID={FOLDER_ID})")
                    break
            
            if FOLDER_ID is None:
                log.error(f"Папка '{FOLDER_NAME}' не найдена!")
                log.info("Доступные папки:")
                for fid, fname in folders_info.items():
                    print(f"   - {fname} (ID={fid})")
                return
        
        # Сравнение
        folder_chats = folders.get(FOLDER_ID, [])
        if not folder_chats:
            log.warning("Папка пуста")
            return
        
        # Получаем название папки
        folder_label = FOLDER_NAME if FOLDER_NAME else f"ID={FOLDER_ID}"
        
        result = compare_chats(folder_chats, base_chats)
        print_results(result, folder_label)
        save_report(result, folder_label)
        
        log.success("Готово!")
        
    except Exception as e:
        log.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрервано")
    except Exception as e:
        log.error(f"Ошибка: {e}")
