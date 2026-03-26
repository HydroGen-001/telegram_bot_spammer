"""
Скрипт проверки чатов на поддержку медиа (фото)
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
from telethon.errors import (
    ChatWriteForbiddenError,
    ChannelPrivateError,
    UserNotParticipantError,
    FloodWaitError
)

load_dotenv()

# Базовая директория — где лежит скрипт
BASE_DIR = Path(__file__).parent.resolve()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')

SESSION_PATH = BASE_DIR / 'sessions/photo_check'
BASE_PATH = BASE_DIR / 'config/chats.json'
OUTPUT_PATH = BASE_DIR / 'config/chats_with_photo_support.json'
TEST_PHOTO_PATH = BASE_DIR / 'test_photo.jpg'


class Logger:
    COLORS = {'info': '\033[94m', 'success': '\033[92m', 'warning': '\033[93m', 'error': '\033[91m', 'reset': '\033[0m', 'bold': '\033[1m'}
    
    def _c(self, level): return self.COLORS.get(level, '')
    def _r(self): return self.COLORS.get('reset', '')
    
    def info(self, msg): print(f"{self._c('info')}[INFO]{self._r()} {msg}")
    def success(self, msg): print(f"{self._c('success')}[OK]{self._r()} {msg}")
    def warning(self, msg): print(f"{self._c('warning')}[WARN]{self._r()} {msg}")
    def error(self, msg): print(f"{self._c('error')}[ERROR]{self._r()} {msg}")
    
    def header(self, msg):
        print(f"\n{self._c('bold')}{'=' * 60}{self._r()}")
        print(f"{self._c('bold')}{msg}{self._r()}")
        print(f"{self._c('bold')}{'=' * 60}{self._r()}")


log = Logger()


def load_base_chats() -> List[Dict]:
    if not BASE_PATH.exists():
        log.error(f"База не найдена: {BASE_PATH}")
        return []
    
    with open(BASE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chats = data.get('chats', [])
    active = [c for c in chats if c.get('enabled', True)]
    log.success(f"Загружено {len(active)} активных чатов")
    return active


async def check_chat(client: TelegramClient, chat_id: str, photo_path: Path) -> Dict:
    result = {'chat_id': chat_id, 'supports_photo': False, 'error': None, 'error_type': None}
    
    try:
        if photo_path.exists():
            await client.send_file(chat_id, str(photo_path), caption="📷 Тест")
            result['supports_photo'] = True
        else:
            await client.send_message(chat_id, "📷 Тест")
            result['supports_photo'] = True
            result['note'] = 'no_photo_tested_text'
        return result
        
    except ChatWriteForbiddenError:
        result['error'] = 'Запись запрещена'
        result['error_type'] = 'write_forbidden'
    except ChannelPrivateError:
        result['error'] = 'Канал приватный'
        result['error_type'] = 'private'
    except FloodWaitError as e:
        result['error'] = f'Flood wait: {e.seconds}s'
        result['error_type'] = 'flood'
    except Exception as e:
        result['error'] = str(e)[:80]
        result['error_type'] = 'unknown'
    
    return result


async def check_all(client: TelegramClient, chats: List[Dict], photo_path: Path) -> Dict:
    photo_allowed = []
    text_only = []
    
    for i, chat in enumerate(chats, 1):
        chat_id = chat['id']
        chat_name = chat['name']
        print(f"\n[{i}/{len(chats)}] {chat_name}")
        
        result = await check_chat(client, chat_id, photo_path)
        
        if result['supports_photo']:
            photo_allowed.append({**chat, 'photo_support': True})
            log.success(f"✓ Фото OK")
        else:
            text_only.append({**chat, 'photo_support': False, 'error_type': result['error_type']})
            log.error(f"✗ {result['error']}")
        
        if i < len(chats):
            await asyncio.sleep(1)
    
    return {'photo_allowed': photo_allowed, 'text_only': text_only}


def save_results(results: Dict):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        '_comment': 'Чаты по поддержке фото',
        '_timestamp': datetime.now().isoformat(),
        '_summary': {
            'total': len(results['photo_allowed']) + len(results['text_only']),
            'photo_allowed': len(results['photo_allowed']),
            'text_only': len(results['text_only'])
        },
        'photo_allowed': results['photo_allowed'],
        'text_only': results['text_only']
    }
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    log.success(f"Сохранено: {OUTPUT_PATH}")


async def main():
    log.header("Проверка чатов на поддержку фото")
    
    if API_ID == 0 or not API_HASH or not PHONE:
        log.error("Нет API credentials!")
        return
    
    base_chats = load_base_chats()
    if not base_chats:
        return
    
    if not TEST_PHOTO_PATH.exists():
        log.warning(f"Фото не найдено: {TEST_PHOTO_PATH}")
        log.info("Проверка будет без фото")
    
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    
    try:
        await client.start(phone=PHONE)
        log.success(f"Подключено: {(await client.get_me()).first_name}")
        
        results = await check_all(client, base_chats, TEST_PHOTO_PATH)
        
        log.header("ИТОГИ")
        print(f"   Всего: {len(base_chats)}")
        print(f"   ✅ Фото: {len(results['photo_allowed'])}")
        print(f"   ❌ Текст: {len(results['text_only'])}")
        
        save_results(results)
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
