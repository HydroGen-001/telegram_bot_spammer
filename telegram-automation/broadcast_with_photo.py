"""
Скрипт рассылки с поддержкой фото

Отправляет сообщения с фото в чаты, которые поддерживают медиа.
Если чат не принимает фото — отправляет только текст.
Без тестовой отправки — сразу рабочая рассылка.

Использование:
    python broadcast_with_photo.py
    
Конфигурация:
    - API credentials из .env
    - Шаблоны: config/templates.json
    - Чаты: config/chats.json
    - Фото: указывается в templates.json (default_photo)
"""

import asyncio
import json
import os
import sys
import io
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.errors import (
    ChatWriteForbiddenError,
    ChannelPrivateError,
    UserNotParticipantError,
    FloodWaitError,
    MediaEmptyError,
    PhotoInvalidError,
    MessageTooLongError
)

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

load_dotenv()

# Базовая директория — где лежит скрипт
BASE_DIR = Path(__file__).parent.resolve()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')

SESSION_PATH = BASE_DIR / 'sessions/userbot'
TEMPLATES_PATH = BASE_DIR / 'config/templates.json'
CHATS_PATH = BASE_DIR / 'config/chats.json'
LOG_PATH = BASE_DIR / 'logs/broadcast_log.json'

# Лимиты
DAILY_LIMIT = 40
HOURLY_LIMIT = 10
MIN_DELAY = 90  # секунд
MAX_DELAY = 180  # секунд


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

def load_templates() -> Dict:
    """Загрузить шаблоны"""
    if not TEMPLATES_PATH.exists():
        log.error(f"Шаблоны не найдены: {TEMPLATES_PATH}")
        return {}
    
    with open(TEMPLATES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_chats() -> List[Dict]:
    """Загрузить активные чаты"""
    if not CHATS_PATH.exists():
        log.error(f"Чаты не найдены: {CHATS_PATH}")
        return []
    
    with open(CHATS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chats = data.get('chats', [])
    active = [c for c in chats if c.get('enabled', True)]
    
    log.success(f"Загружено {len(active)} активных чатов")
    return active


def get_template_with_photo(templates_data: Dict) -> Optional[Dict]:
    """Получить шаблон с фото (id=3 contract_offer)"""
    templates = templates_data.get('templates', [])
    
    # Ищем шаблон с has_photo=true
    for t in templates:
        if t.get('has_photo', False):
            return t
    
    # Если нет, берём первый
    return templates[0] if templates else None


def get_photo_path(templates_data: Dict) -> Optional[Path]:
    """Получить путь к фото"""
    photo_path = templates_data.get('default_photo')
    if photo_path:
        p = Path(photo_path)
        if p.exists():
            return p
        else:
            log.warning(f"Фото не найдено: {p}")
    return None


async def send_message_with_fallback(
    client: TelegramClient,
    chat_id: str,
    text: str,
    photo_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Отправить сообщение с фото. Если ошибка — отправить только текст.
    
    Returns:
        dict с результатом отправки
    """
    result = {
        'chat_id': chat_id,
        'success': False,
        'sent_photo': False,
        'sent_text': False,
        'error': None
    }
    
    # Пробуем отправить фото + текст
    if photo_path:
        try:
            await client.send_file(chat_id, str(photo_path), caption=text)
            result['success'] = True
            result['sent_photo'] = True
            result['sent_text'] = True
            return result
        except Exception as e:
            result['error'] = str(e)[:100]
            # Продолжаем, попробуем только текст
    
    # Отправляем только текст
    try:
        await client.send_message(chat_id, text)
        result['success'] = True
        result['sent_text'] = True
        return result
    except Exception as e:
        result['error'] = str(e)[:100]
        result['success'] = False
        return result


async def broadcast_with_photo(
    client: TelegramClient,
    chats: List[Dict],
    text: str,
    photo_path: Optional[Path],
    daily_limit: int = DAILY_LIMIT,
    hourly_limit: int = HOURLY_LIMIT
) -> Dict[str, Any]:
    """
    Рассылка с поддержкой фото
    
    Returns:
        статистика рассылки
    """
    stats = {
        'total': len(chats),
        'sent': 0,
        'sent_with_photo': 0,
        'sent_text_only': 0,
        'failed': 0,
        'skipped_limit': 0,
        'errors': []
    }
    
    # Перемешиваем чаты
    random.shuffle(chats)
    
    sent_today = 0
    sent_this_hour = 0
    
    for i, chat in enumerate(chats, 1):
        chat_id = chat['id']
        chat_name = chat.get('name', chat_id)
        
        print(f"\n[{i}/{len(chats)}] {chat_name}")
        
        # Проверка лимитов
        if sent_today >= daily_limit:
            log.warning(f"Дневной лимит ({daily_limit}) исчерпан")
            stats['skipped_limit'] += len(chats) - i + 1
            break
        
        if sent_this_hour >= hourly_limit:
            log.info(f"Пауза: часовой лимит ({hourly_limit})")
            await asyncio.sleep(60)  # Ждём 1 минуту
            sent_this_hour = 0
        
        # Отправка
        result = await send_message_with_fallback(
            client, chat_id, text, photo_path
        )
        
        if result['success']:
            stats['sent'] += 1
            sent_today += 1
            sent_this_hour += 1
            
            if result['sent_photo']:
                stats['sent_with_photo'] += 1
                log.success(f"✓ Фото + текст")
            else:
                stats['sent_text_only'] += 1
                log.success(f"✓ Только текст")
        else:
            stats['failed'] += 1
            log.error(f"✗ {result['error']}")
            stats['errors'].append({
                'chat_id': chat_id,
                'chat_name': chat_name,
                'error': result['error']
            })
        
        # Сохраняем лог после каждого сообщения
        save_log(stats, chats[:i])
        
        # Задержка между сообщениями (кроме последнего)
        if i < len(chats) and result['success']:
            delay = random.randint(MIN_DELAY, MAX_DELAY)
            log.info(f"Задержка {delay} сек...")
            await asyncio.sleep(delay)
    
    return stats


def save_log(stats: Dict, processed_chats: List[Dict]):
    """Сохранить лог рассылки"""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'stats': stats,
        'processed_chats': [
            {'id': c['id'], 'name': c['name']} 
            for c in processed_chats
        ]
    }
    
    with open(LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)


def print_summary(stats: Dict):
    """Вывести итоги"""
    log.header("ИТОГИ РАССЫЛКИ")
    
    print(f"   Всего чатов:      {stats['total']}")
    print(f"   ✅ Отправлено:    {stats['sent']}")
    print(f"      • С фото:      {stats['sent_with_photo']}")
    print(f"      • Текст:       {stats['sent_text_only']}")
    print(f"   ❌ Ошибки:        {stats['failed']}")
    print(f"   ⏭️ Пропущено:     {stats['skipped_limit']}")
    
    if stats['errors']:
        print(f"\nОшибки ({len(stats['errors'])}):")
        for err in stats['errors'][:10]:  # Первые 10
            print(f"   • {err['chat_name']}: {err['error']}")
        if len(stats['errors']) > 10:
            print(f"   ... и ещё {len(stats['errors']) - 10}")


# =============================================================================
# MAIN
# =============================================================================

async def main():
    log.header("Рассылка с поддержкой фото")

    # Проверка конфигурации
    if API_ID == 0 or not API_HASH or not PHONE:
        log.error("❌ Не заполнены API credentials!")
        log.error("Проверьте файл .env (API_ID, API_HASH, PHONE)")
        return

    log.info(f"API_ID: {API_ID}")
    log.info(f"PHONE: {PHONE}")
    log.info(f"Сессия: {SESSION_PATH}")

    # Загрузка шаблонов
    templates_data = load_templates()
    if not templates_data:
        return

    # Загрузка чатов
    chats = load_chats()
    if not chats:
        log.error("❌ Список чатов пуст!")
        return

    # Получение шаблона с фото
    template = get_template_with_photo(templates_data)
    if not template:
        log.error("❌ Шаблоны не найдены!")
        return

    log.info(f"📝 Шаблон: {template['name']} (ID={template['id']})")
    log.info(f"📄 Текст: {len(template['text'])} символов")

    # Получение фото
    photo_path = get_photo_path(templates_data)
    if photo_path:
        log.success(f"📷 Фото: {photo_path}")
    else:
        log.warning("📷 Фото не найдено, будет отправляться только текст")

    # Используем готовую сессию
    log.info("🔑 Загрузка сессии...")
    log.info(f"📁 Сессия: {SESSION_PATH}.session")
    
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)

    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            log.error("❌ Сессия не активна!")
            log.error("Запустите: python auth_and_collect.py")
            await client.disconnect()
            return
        
        me = await client.get_me()
        log.success(f"✅ В системе: {me.first_name} (@{me.username or 'no username'})")

        # Запуск рассылки
        log.info("🚀 Запуск рассылки...")
        stats = await broadcast_with_photo(
            client,
            chats,
            template['text'],
            photo_path
        )

        # Итоги
        print_summary(stats)

        log.success("✅ Рассылка завершена!")

    except Exception as e:
        log.error(f"❌ Ошибка: {e}")
        log.error(f"Тип ошибки: {type(e).__name__}")
        import traceback
        traceback.print_exc()
    finally:
        log.info("🔄 Отключение...")
        try:
            await client.disconnect()
        except:
            pass
        log.success("✅ Отключено")


if __name__ == "__main__":
    # Настройка вывода для Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True  # Буферизация по строкам для мгновенного вывода
        )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем")
    except Exception as e:
        log.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
