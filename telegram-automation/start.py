"""
Telegram Automation - Главное меню
Вход через сессию или по номеру + рассылка
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
from telethon.tl.types import Chat, Channel, User
from telethon.errors import SessionPasswordNeededError

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
                log.success(f"✅ Отправлено: Фото + текст")
            else:
                stats['sent_text_only'] += 1
                log.success(f"✅ Отправлено: Только текст")
        else:
            stats['failed'] += 1
            log.error(f"❌ Ошибка отправки: {result['error']}")
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
            log.info(f"⏳ До следующей отправки: {delay} сек...")
            
            # Обратный отсчёт
            for sec in range(delay, 0, -1):
                print(f"\r   Осталось секунд: {sec}   ", end='', flush=True)
                await asyncio.sleep(1)
            print()  # Новая строка после отсчёта

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


# =============================================================================
# АВТОРИЗАЦИЯ
# =============================================================================

async def auth_by_phone():
    """Авторизация по номеру телефона"""
    print("\n" + "=" * 60)
    print("АВТОРИЗАЦИЯ ПО НОМЕРУ ТЕЛЕФОНА")
    print("=" * 60 + "\n")
    
    if API_ID == 0 or not API_HASH or not PHONE:
        log.error("❌ Не заполнены API credentials!")
        log.error("Проверьте файл .env")
        return
    
    log.info(f"API_ID: {API_ID}")
    log.info(f"PHONE: {PHONE}")
    
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    
    try:
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            log.success(f"✅ Уже авторизовано: {me.first_name} (@{me.username or 'no username'})")
            await client.disconnect()
            return
        
        log.info("📲 Отправка кода...")
        result = await client.send_code_request(PHONE)
        log.success(f"✅ Код отправлен: {result.type}")
        print("\nПроверьте:")
        print("  • Telegram (личные сообщения от Telegram)")
        print("  • SMS")
        print()
        
        code = input("Введите код: ").strip()
        
        try:
            await client.sign_in(PHONE, code, phone_code_hash=result.phone_code_hash)
        except SessionPasswordNeededError:
            print("\n🔐 Включена 2FA защита")
            password = input("Введите пароль: ").strip()
            await client.sign_in(password=password)
        
        me = await client.get_me()
        log.success(f"✅ Авторизация успешна: {me.first_name} (@{me.username or 'no username'})")
        
        # Сбор чатов
        print("\n" + "-" * 60)
        print("Сбор чатов...")
        
        chats_data = []
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, User):
                continue
            if isinstance(entity, (Chat, Channel)):
                chat_id = entity.username if hasattr(entity, 'username') and entity.username else str(entity.id)
                title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
                chat_type = "channel" if isinstance(entity, Channel) else "chat"
                chats_data.append({
                    "id": chat_id,
                    "name": title,
                    "type": chat_type,
                    "enabled": True
                })
        
        chats_data.sort(key=lambda x: x['name'].lower())
        
        CHATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CHATS_PATH, 'w', encoding='utf-8') as f:
            json.dump({
                "_comment": "Список чатов для рассылки",
                "_version": "1.0.0",
                "_total_found": len(chats_data),
                "chats": chats_data
            }, f, ensure_ascii=False, indent=2)
        
        log.success(f"✅ Сохранено чатов: {len(chats_data)}")
        log.info(f"📁 Файл: {CHATS_PATH}")
        
    except Exception as e:
        log.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()
        log.success("✅ Готово!")


async def check_session_status():
    """Проверка статуса сессии"""
    print("\n" + "=" * 60)
    print("ПРОВЕРКА СТАТУСА СЕССИИ")
    print("=" * 60 + "\n")
    
    # Проверяем с расширением .session
    session_file = SESSION_PATH.with_suffix('.session')
    if not session_file.exists():
        log.error(f"❌ Сессия не найдена: {session_file}")
        log.info("Запустите: 1. Войти по номеру")
        return
    
    if API_ID == 0 or not API_HASH or not PHONE:
        log.error("❌ Не заполнены API credentials!")
        return
    
    log.info(f"📁 Сессия: {session_file}")
    
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    
    try:
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            log.success("✅ Сессия активна")
            log.info(f"👤 Пользователь: {me.first_name} (@{me.username or 'no username'})")
            log.info(f"📱 Телефон: {me.phone or 'скрыт'}")
        else:
            log.error("❌ Сессия не активна")
            log.info("Запустите: 1. Войти по номеру")
            
    except Exception as e:
        log.error(f"❌ Ошибка: {e}")
    finally:
        await client.disconnect()


def show_chat_stats():
    """Показать статистику чатов"""
    print("\n" + "=" * 60)
    print("СТАТИСТИКА ЧАТОВ")
    print("=" * 60 + "\n")
    
    if not CHATS_PATH.exists():
        log.error(f"❌ Файл чатов не найден: {CHATS_PATH}")
        return
    
    with open(CHATS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chats = data.get('chats', [])
    enabled = [c for c in chats if c.get('enabled', True)]
    disabled = [c for c in chats if not c.get('enabled', True)]
    
    log.info(f"📊 Всего чатов: {len(chats)}")
    log.success(f"✅ Активных: {len(enabled)}")
    log.error(f"❌ Отключено: {len(disabled)}")
    
    if enabled:
        print(f"\n📋 Первые 10 активных:")
        for i, chat in enumerate(enabled[:10], 1):
            print(f"   {i}. {chat['name']} ({chat['id']})")
        if len(enabled) > 10:
            print(f"   ... и ещё {len(enabled) - 10}")


# =============================================================================
# МЕНЮ
# =============================================================================

async def show_menu():
    """Показать главное меню"""
    while True:
        print("\n" + "=" * 60)
        print("       TELEGRAM AUTOMATION - ГЛАВНОЕ МЕНЮ")
        print("=" * 60 + "\n")
        print("Выберите действие:")
        print()
        print("  1. 🔑 Войти по номеру (создать сессию)")
        print("  2. 📡 Запустить рассылку (используя сессию)")
        print("  3. 📋 Проверить статус сессии")
        print("  4. 📊 Показать статистику чатов")
        print("  5. 🚪 Выход")
        print()
        
        choice = input("Ваш выбор (1-5): ").strip()
        
        if choice == '1':
            await auth_by_phone()
        elif choice == '2':
            await main()
        elif choice == '3':
            await check_session_status()
        elif choice == '4':
            show_chat_stats()
        elif choice == '5':
            print("\n👋 Выход...")
            break
        else:
            print("\n❌ Неверный выбор, попробуйте снова")
        
        input("\nНажмите Enter для продолжения...")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Настройка вывода для Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )

    try:
        asyncio.run(show_menu())
    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем")
    except Exception as e:
        log.error(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
