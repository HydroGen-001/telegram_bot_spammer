"""
Telegram Automation - Главное меню
Простая и надёжная версия
"""

import asyncio
import json
import os
import sys
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.tl.types import Chat, Channel, User
from telethon.errors import SessionPasswordNeededError, FloodWaitError

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')

SESSION_PATH = BASE_DIR / 'sessions' / 'userbot'
TEMPLATES_PATH = BASE_DIR / 'config' / 'templates.json'
CHATS_PATH = BASE_DIR / 'config' / 'chats.json'
LOG_PATH = BASE_DIR / 'logs' / 'broadcast_log.json'

# Прокси (опционально)
PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
PROXY_HOST = os.getenv('PROXY_HOST', '')
PROXY_PORT = int(os.getenv('PROXY_PORT', '0'))
PROXY_USERNAME = os.getenv('PROXY_USERNAME', '')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')

# Лимиты
DAILY_LIMIT = 1000  # Увеличил для бесконечной рассылки
MIN_DELAY = 50
MAX_DELAY = 100

# =============================================================================
# ЛОГГЕР TELETHON
# =============================================================================

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
telethon_logger = logging.getLogger('telethon')
telethon_logger.setLevel(logging.DEBUG)

# =============================================================================
# ЛОГГЕР
# =============================================================================

def log_info(msg):
    print(f"[INFO] {msg}", flush=True)

def log_ok(msg):
    print(f"[OK] {msg}", flush=True)

def log_warn(msg):
    print(f"[WARN] {msg}", flush=True)

def log_error(msg):
    print(f"[ERROR] {msg}", flush=True)

def header(msg):
    print(f"\n{'=' * 60}", flush=True)
    print(msg, flush=True)
    print(f"{'=' * 60}\n", flush=True)

# =============================================================================
# ЗАГРУЗКА ДАННЫХ
# =============================================================================

def load_templates() -> Dict:
    if not TEMPLATES_PATH.exists():
        log_error(f"Шаблоны не найдены: {TEMPLATES_PATH}")
        return {}
    with open(TEMPLATES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_chats() -> List[Dict]:
    if not CHATS_PATH.exists():
        log_error(f"Чаты не найдены: {CHATS_PATH}")
        return []
    with open(CHATS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    chats = data.get('chats', [])
    active = [c for c in chats if c.get('enabled', True)]
    log_ok(f"Загружено {len(active)} чатов")
    return active

def get_photo_path(templates_data: Dict) -> Optional[Path]:
    photo_path = templates_data.get('default_photo')
    if photo_path:
        p = Path(photo_path)
        if p.exists():
            return p
        log_warn(f"Фото не найдено: {p}")
    return None

def save_log(stats: Dict, processed_chats: List[Dict]):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'stats': stats,
        'chats': [{'id': c['id'], 'name': c['name']} for c in processed_chats]
    }
    with open(LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

# =============================================================================
# ОТПРАВКА СООБЩЕНИЙ
# =============================================================================

async def send_message(client: TelegramClient, chat_id: str, text: str, forward_from_msg_id: Optional[int] = None) -> bool:
    """
    Отправить сообщение: текст + пересылка фото из избранного
    Возвращает True если текст отправлен
    """
    
    # 1. Отправляем текст (без таймаута)
    try:
        await client.send_message(chat_id, text)
    except FloodWaitError as e:
        log_error(f"FloodWait: ждём {e.seconds} сек")
        await asyncio.sleep(e.seconds)
        await client.send_message(chat_id, text)
    except Exception as e:
        log_error(f"Текст не отправлен: {type(e).__name__}: {e}")
        return False
    
    # 2. Пересылаем фото из избранного (если есть msg_id)
    if forward_from_msg_id:
        try:
            await client.forward_messages(chat_id, forward_from_msg_id, from_peer='me')
        except FloodWaitError as e:
            log_error(f"FloodWait (фото): {e.seconds} сек")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            # Фото не отправилось — пишем причину, но текст ушёл
            log_error(f"Фото не отправлено: {type(e).__name__}: {e}")
    
    return True

async def broadcast(client: TelegramClient, chats: List[Dict], text: str, forward_from_msg_id: Optional[int] = None) -> Dict:
    """Рассылка по чатам (бесконечный цикл)"""
    stats = {'total': len(chats), 'sent': 0, 'failed': 0, 'errors': []}
    random.shuffle(chats)
    sent_count = 0

    for i, chat in enumerate(chats, 1):
        chat_id = chat['id']
        chat_name = chat.get('name', chat_id)

        # Отправка
        success = await send_message(client, chat_id, text, forward_from_msg_id)

        if success:
            stats['sent'] += 1
            sent_count += 1
            log_info(f"[{i}/{len(chats)}] ✓ {chat_name}")
        else:
            stats['failed'] += 1
            stats['errors'].append({'chat': chat_name, 'id': chat_id})
            log_error(f"[{i}/{len(chats)}] ✗ {chat_name}")

        save_log(stats, chats[:i])

        # Рандомизированная задержка после каждого сообщения
        if i < len(chats):
            delay = random.randint(MIN_DELAY, MAX_DELAY)
            for sec in range(delay, 0, -1):
                mins, secs = divmod(sec, 60)
                print(f"\r   Пауза: {mins:02d}:{secs:02d}  ", end='', flush=True)
                await asyncio.sleep(1)
            print()

    return stats

# =============================================================================
# АВТОРИЗАЦИЯ
# =============================================================================

async def auth_interactive(client: TelegramClient) -> bool:
    """Интерактивная авторизация"""
    header("АВТОРИЗАЦИЯ")
    log_info(f"Телефон: {PHONE}")

    try:
        await client.connect()
        await client.send_code_request(PHONE)
        log_ok("Код отправлен")

        print("\nПроверьте Telegram или SMS", flush=True)
        code = input("Код: ").strip()

        if not code:
            return False

        try:
            await client.sign_in(phone=PHONE, code=code)
        except SessionPasswordNeededError:
            print("\n2FA включён", flush=True)
            pwd = input("Пароль: ").strip()
            await client.sign_in(password=pwd)

        me = await client.get_me()
        log_ok(f"В системе: {me.first_name} (@{me.username or 'no username'})")
        return True

    except FloodWaitError as e:
        log_error(f"FloodWait: {e.seconds} сек")
        return False
    except Exception as e:
        log_error(f"Ошибка: {e}")
        return False


async def auth_with_proxy() -> bool:
    """Авторизация с прокси (для корректного применения прокси)"""
    header("АВТОРИЗАЦИЯ ЧЕРЕЗ ПРОКСИ")
    
    if API_ID == 0 or not API_HASH:
        log_error("Заполните API_ID и API_HASH в .env")
        return False
    
    phone = input(f"Телефон [{PHONE}]: ").strip()
    if not phone:
        phone = PHONE
    
    if not phone:
        log_error("Телефон не указан!")
        return False
    
    # Создаём клиента С ПРОКСИ
    if PROXY_ENABLED and PROXY_HOST:
        try:
            proxy_ip = socket.gethostbyname(PROXY_HOST)
            log_info(f"Прокси: {PROXY_HOST} → {proxy_ip}:{PROXY_PORT}")
        except Exception as e:
            log_warn(f"Не удалось получить IP прокси: {e}")
            proxy_ip = PROXY_HOST
        
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
        
        log_info("SOCKS5 прокси настроен через set_proxy(dict)")
    else:
        client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
        log_info("Прокси отключён")
    
    try:
        await client.connect()
        
        # Проверка существующей сессии
        if await client.is_user_authorized():
            me = await client.get_me()
            log_ok(f"Уже авторизовано: {me.first_name} (@{me.username})")
            
            choice = input("Выйти и войти заново? (y/n): ").strip().lower()
            if choice == 'y':
                await client.log_out()
                log_info("Выполнен выход")
            else:
                await client.disconnect()
                return True
        
        # Отправка кода ЧЕРЕЗ ПРОКСИ
        log_info(f"Отправка кода на {phone}...")
        await client.send_code_request(phone)
        log_ok("Код отправлен (через прокси)")
        
        print("\nПроверьте Telegram или SMS", flush=True)
        code = input("Код: ").strip()
        
        if not code:
            await client.disconnect()
            return False
        
        try:
            await client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            print("\n2FA включён", flush=True)
            pwd = input("Пароль: ").strip()
            await client.sign_in(password=pwd)
        
        me = await client.get_me()
        log_ok(f"✓ Вход выполнен: {me.first_name} (@{me.username})")
        log_info("Проверьте уведомление от Telegram — должен быть IP прокси!")
        
        await client.disconnect()
        return True
        
    except FloodWaitError as e:
        log_error(f"FloodWait: {e.seconds} сек")
        await client.disconnect()
        return False
    except Exception as e:
        log_error(f"Ошибка: {type(e).__name__}: {e}")
        await client.disconnect()
        return False

async def collect_chats(client: TelegramClient):
    """Сбор чатов"""
    header("СБОР ЧАТОВ")
    chats_data = []

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, User):
            continue
        if isinstance(entity, (Chat, Channel)):
            chat_id = entity.username if hasattr(entity, 'username') and entity.username else str(entity.id)
            title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            chat_type = "channel" if isinstance(entity, Channel) else "chat"
            chats_data.append({'id': chat_id, 'name': title, 'type': chat_type, 'enabled': True})

    chats_data.sort(key=lambda x: x['name'].lower())
    CHATS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CHATS_PATH, 'w', encoding='utf-8') as f:
        json.dump({
            '_comment': 'Чаты для рассылки',
            '_total': len(chats_data),
            'chats': chats_data
        }, f, ensure_ascii=False, indent=2)

    log_ok(f"Сохранено {len(chats_data)} чатов")
    print(f"\nПервые 10:", flush=True)
    for i, c in enumerate(chats_data[:10], 1):
        print(f"  {i}. {c['name']}", flush=True)

# =============================================================================
# РАССЫЛКА
# =============================================================================

async def run_broadcast():
    """Запуск рассылки"""
    header("РАССЫЛКА")

    if API_ID == 0 or not API_HASH or not PHONE:
        log_error("Заполните .env")
        input("\nНажмите Enter...")
        return

    templates_data = load_templates()
    if not templates_data:
        input("\nНажмите Enter...")
        return

    chats = load_chats()
    if not chats:
        log_error("Чаты пусты!")
        input("\nНажмите Enter...")
        return

    # Выбор шаблона
    templates = templates_data.get('templates', [])
    header("ШАБЛОНЫ")
    for i, t in enumerate(templates, 1):
        photo_mark = " 📷" if t.get('has_photo', False) else ""
        print(f"  {i}. {t['name']}{photo_mark}")
    print()
    
    choice = input(f"Выберите шаблон (1-{len(templates)}, Enter=1): ").strip()
    try:
        idx = int(choice) - 1 if choice else 0
        idx = max(0, min(idx, len(templates) - 1))
    except ValueError:
        idx = 0
    
    template = templates[idx]
    log_info(f"Выбран шаблон: {template['name']}")
    log_info(f"Текст: {len(template['text'])} симв.")

    # Клиент - используем start() для правильной инициализации
    log_info(f"Сессия: {SESSION_PATH}.session")
    
    # Настройка клиента с прокси (если включён)
    if PROXY_ENABLED and PROXY_HOST:
        # Получаем актуальный IP (для мобильных прокси с ротацией)
        try:
            import socket
            proxy_ip = socket.gethostbyname(PROXY_HOST)
            log_info(f"Прокси: {PROXY_HOST} → {proxy_ip}:{PROXY_PORT}")
        except Exception as e:
            log_warn(f"Не удалось получить IP: {e}")
            proxy_ip = PROXY_HOST

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
        
        log_info("SOCKS5 прокси настроен через set_proxy(dict)")
    else:
        client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)

    try:
        log_info("Подключение...")
        await client.connect()
        
        # Проверка авторизации
        if not await client.is_user_authorized():
            log_error("Не авторизовано! Выполните вход сначала.")
            log_info("Выберите пункт 1 или 2 в главном меню")
            await client.disconnect()
            input("\nНажмите Enter...")
            return
        
        log_info("Подключено")
        me = await client.get_me()
        log_ok(f"В системе: {me.first_name} (@{me.username or 'no username'})")

        # Получаем последнее сообщение из избранного (для пересылки фото)
        forward_from_msg_id = None
        try:
            log_info("Получение последнего сообщения из избранного...")
            async for msg in client.iter_messages('me', limit=1):
                forward_from_msg_id = msg.id
                log_info(f"Фото будет пересылаться (msg_id={forward_from_msg_id})")
                break
        except Exception as e:
            log_error(f"Не удалось получить сообщение из избранного: {e}")

        # БЕСКОНЕЧНАЯ РАССЫЛКА
        log_info("=" * 40)
        log_info("НАЧАЛО РАССЫЛКИ (бесконечный цикл)")
        log_info("=" * 40)
        
        cycle = 0
        while True:
            cycle += 1
            log_info(f"\n{'=' * 40}")
            log_info(f"ЦИКЛ {cycle}")
            log_info(f"{'=' * 40}")
            
            stats = await broadcast(client, chats, template['text'], forward_from_msg_id)
            
            # Отчёт после каждого цикла
            header("ОТЧЁТ О РАССЫЛКЕ")
            print(f"  Цикл:        {cycle}")
            print(f"  Чатов:       {stats['total']}")
            print(f"  Успешно:     {stats['sent']}")
            print(f"  Ошибки:      {stats['failed']}")
            if stats['errors']:
                print(f"\n  Ошибки ({len(stats['errors'])}):")
                for e in stats['errors'][:5]:
                    print(f"    - {e['chat']}")
            
            log_info("\nПерезапуск через 5 сек...")
            await asyncio.sleep(5)

    except KeyboardInterrupt:
        log_info("\n\nПрервано пользователем")
    except Exception as e:
        log_error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        log_info("Отключение...")
        await client.disconnect()
        log_info("Отключено")

# =============================================================================
# ПРОВЕРКА СЕССИИ
# =============================================================================

async def check_session():
    """Проверка сессии"""
    header("ПРОВЕРКА СЕССИИ")
    
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            log_ok("Сессия активна")
            log_info(f"Пользователь: {me.first_name} (@{me.username})")
        else:
            log_error("Сессия не активна")
    except Exception as e:
        log_error(f"Ошибка: {e}")
    finally:
        await client.disconnect()

# =============================================================================
# АВТОРИЗАЦИЯ И СБОР ЧАТОВ
# =============================================================================

async def auth_and_collect():
    """Авторизация и сбор чатов"""
    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)
    try:
        await client.connect()
        if await client.is_user_authorized():
            me = await client.get_me()
            log_ok(f"Уже авторизовано: {me.first_name}")
            ans = input("Собрать чаты? (y/n): ").strip().lower()
            if ans == 'y':
                await collect_chats(client)
        else:
            log_error("Не авторизовано, вход...")
            success = await auth_interactive(client)
            if success:
                await collect_chats(client)
    except Exception as e:
        log_error(f"Ошибка: {e}")
    finally:
        await client.disconnect()

# =============================================================================
# ГЛАВНОЕ МЕНЮ
# =============================================================================

def show_menu():
    while True:
        header("TELEGRAM AUTOMATION")
        print("  1. Войти (создать сессию)")
        print("  2. Войти через прокси (для корректного IP)")
        print("  3. Рассылка")
        print("  4. Проверка сессии")
        print("  5. Статистика чатов")
        print("  0. Выход")
        print(flush=True)

        choice = input("Выбор (0-5): ").strip()

        if choice == '1':
            asyncio.run(auth_and_collect())

        elif choice == '2':
            # Авторизация через прокси
            if PROXY_ENABLED and PROXY_HOST:
                asyncio.run(auth_with_proxy())
            else:
                log_warn("Прокси отключён!")
                log_info("Настройте PROXY_ENABLED, PROXY_HOST в .env")
                input("\nНажмите Enter...")

        elif choice == '3':
            asyncio.run(run_broadcast())

        elif choice == '4':
            asyncio.run(check_session())

        elif choice == '5':
            if not CHATS_PATH.exists():
                log_error("Чаты не найдены")
            else:
                with open(CHATS_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                chats = data.get('chats', [])
                enabled = [c for c in chats if c.get('enabled', True)]
                log_info(f"Всего: {len(chats)}")
                log_ok(f"Активных: {len(enabled)}")
                if enabled:
                    print("\nПервые 10:", flush=True)
                    for i, c in enumerate(enabled[:10], 1):
                        print(f"  {i}. {c['name']}", flush=True)

        elif choice == '0':
            print("Выход...", flush=True)
            break

        input("\nНажмите Enter...")

# =============================================================================
# ЗАПУСК
# =============================================================================

if __name__ == "__main__":
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    try:
        show_menu()
    except KeyboardInterrupt:
        print("\nПрервано")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
