"""
Join Chats Script
Постепенное вступление в чаты с защитой от бана

Запуск: python scripts/join_chats.py
"""

import asyncio
import json
import random
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError, UserNotParticipantError

# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

BASE_DIR = Path(__file__).parent.parent.resolve()
CONFIG_DIR = BASE_DIR / 'config'
ACCOUNTS_FILE = BASE_DIR / 'accounts.json'
SESSIONS_DIR = BASE_DIR / 'sessions'

# Настройки вступления
JOINS_PER_DAY = 30  # Максимум вступлений в день
MIN_DELAY = 45  # Минимальная задержка между вступлениями (сек)
MAX_DELAY = 90  # Максимальная задержка между вступлениями (сек)
PAUSE_AFTER_SERIES = 5  # Пауза после N вступлений
PAUSE_DURATION_MIN = 10  # Минимальная пауза (мин)
PAUSE_DURATION_MAX = 20  # Максимальная пауза (мин)


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
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    RED = '\033[31m'


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


def progress_bar(current: int, total: int, width: int = 30) -> str:
    """Создать прогресс-бар"""
    percentage = current / total if total > 0 else 0
    filled = int(width * percentage)
    bar = '█' * filled + '░' * (width - filled)
    return f"[{bar}] {current}/{total} ({percentage*100:.1f}%)"


# =============================================================================
# ЗАГРУЗКА ДАННЫХ
# =============================================================================

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


def load_account_chats(account_id: int) -> List[Dict]:
    """Загрузить чаты для конкретного аккаунта"""
    chats_file = CONFIG_DIR / 'accounts' / str(account_id) / 'chats.json'
    
    if not chats_file.exists():
        log_warning(f"Файл чатов не найден: {chats_file}")
        return []
    
    with open(chats_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        chats = data.get('chats', [])
        enabled_chats = [c for c in chats if c.get('enabled', True)]
        
        log_info(f"Загружено {len(enabled_chats)} чатов для аккаунта {account_id}")
        
        return enabled_chats


def load_progress(account_id: int) -> Dict:
    """Загрузить прогресс вступления для аккаунта"""
    progress_file = CONFIG_DIR / 'accounts' / str(account_id) / 'progress.json'
    
    if not progress_file.exists():
        return {
            'joined': [],
            'failed': [],
            'last_join_date': None,
            'joins_today': 0
        }
    
    with open(progress_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_progress(account_id: int, progress: Dict):
    """Сохранить прогресс вступления"""
    progress_file = CONFIG_DIR / 'accounts' / str(account_id) / 'progress.json'
    
    # Создаём папку если нет
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


# =============================================================================
# КЛИЕНТ TELEGRAM
# =============================================================================

def create_client(account: Dict) -> TelegramClient:
    """Создать Telegram клиент для аккаунта"""
    session_path = SESSIONS_DIR / account['session_name']
    
    client = TelegramClient(
        str(session_path),
        account['api_id'],
        account['api_hash']
    )
    
    # Настройка прокси если включён
    proxy_config = account.get('proxy', {})
    if proxy_config.get('enabled', False):
        import socket
        try:
            proxy_ip = socket.gethostbyname(proxy_config['host'])
            
            proxy_dict = {
                'proxy_type': 'socks5',
                'addr': proxy_ip,
                'port': proxy_config['port'],
            }
            
            if proxy_config.get('username') and proxy_config.get('password'):
                proxy_dict['username'] = proxy_config['username']
                proxy_dict['password'] = proxy_config['password']
            
            client.set_proxy(proxy_dict)
            log_info(f"Прокси установлен: {proxy_ip}:{proxy_config['port']}")
        except Exception as e:
            log_warning(f"Не удалось установить прокси: {e}")
    
    return client


# =============================================================================
# ВСТУПЛЕНИЕ В ЧАТЫ
# =============================================================================

class JoinManager:
    """Менеджер вступления в чаты"""
    
    def __init__(self, client: TelegramClient, account_id: int):
        self.client = client
        self.account_id = account_id
        self.progress = load_progress(account_id)
        
        # Статистика
        self.joined_count = 0
        self.failed_count = 0
        self.skipped_count = 0
    
    async def join_chat(self, chat: Dict) -> bool:
        """
        Вступить в чат
        
        Returns:
            True если успешно
        """
        chat_id = chat.get('id')
        chat_name = chat.get('name', chat_id)
        
        try:
            # Пытаемся вступить
            await self.client(JoinChannelRequest(chat_id))
            
            # Успех
            self.progress['joined'].append({
                'id': chat_id,
                'name': chat_name,
                'joined_at': datetime.now().isoformat()
            })
            
            self.joined_count += 1
            return True
            
        except FloodWaitError as e:
            # FloodWait — серьёзная проблема
            log_warning(f"⚠️ FloodWait {e.seconds} сек для {chat_name}")
            
            self.progress['failed'].append({
                'id': chat_id,
                'name': chat_name,
                'error': f'FloodWait: {e.seconds} сек',
                'failed_at': datetime.now().isoformat()
            })
            
            self.failed_count += 1
            return False
            
        except ChannelPrivateError:
            # Частный канал без доступа
            log_warning(f"🔒 Частный канал: {chat_name}")
            
            self.progress['failed'].append({
                'id': chat_id,
                'name': chat_name,
                'error': 'ChannelPrivate',
                'failed_at': datetime.now().isoformat()
            })
            
            self.failed_count += 1
            return False
            
        except UserNotParticipantError:
            # Нужно приглашение
            log_warning(f"🔒 Нужно приглашение: {chat_name}")
            
            self.progress['failed'].append({
                'id': chat_id,
                'name': chat_name,
                'error': 'InviteRequired',
                'failed_at': datetime.now().isoformat()
            })
            
            self.failed_count += 1
            return False
            
        except Exception as e:
            # Другая ошибка
            log_error(f"✗ Ошибка: {type(e).__name__}: {str(e)[:100]}")
            
            self.progress['failed'].append({
                'id': chat_id,
                'name': chat_name,
                'error': f'{type(e).__name__}: {str(e)[:50]}',
                'failed_at': datetime.now().isoformat()
            })
            
            self.failed_count += 1
            return False
    
    def can_join_today(self) -> bool:
        """Проверка: можно ли вступать сегодня"""
        today = datetime.now().date().isoformat()
        last_date = self.progress.get('last_join_date')
        
        # Новый день — сбрасываем счётчик
        if last_date != today:
            self.progress['last_join_date'] = today
            self.progress['joins_today'] = 0
            save_progress(self.account_id, self.progress)
            log_info("Новый день — счётчик сброшен")
        
        return self.progress['joins_today'] < JOINS_PER_DAY
    
    def increment_joins(self):
        """Увеличить счётчик вступлений"""
        self.progress['joins_today'] += 1
        save_progress(self.account_id, self.progress)
    
    async def run_join(self, chats: List[Dict]):
        """
        Запустить вступление в чаты
        
        Args:
            chats: Список чатов для вступления
        """
        if not chats:
            log_warning("Нет чатов для вступления!")
            return
        
        header(f"ВСТУПЛЕНИЕ В ЧАТЫ (Аккаунт {self.account_id})")
        
        print(f"\n📊 Лимит вступлений в день: {JOINS_PER_DAY}")
        print(f"⏱ Задержка между вступлениями: {MIN_DELAY}-{MAX_DELAY} сек")
        print(f"☕ Пауза после {PAUSE_AFTER_SERIES} вступлений: {PAUSE_DURATION_MIN}-{PAUSE_DURATION_MAX} мин")
        print()
        
        # Фильтруем уже вступившие
        joined_ids = {j['id'] for j in self.progress.get('joined', [])}
        failed_ids = {f['id'] for f in self.progress.get('failed', [])}
        
        chats_to_join = [
            c for c in chats 
            if c['id'] not in joined_ids and c['id'] not in failed_ids
        ]
        
        log_info(f"Чатов для вступления: {len(chats_to_join)} (из {len(chats)})")
        log_info(f"Уже вступили: {len(joined_ids)}")
        log_info(f"Ошибки: {len(failed_ids)}")
        print()
        
        if not chats_to_join:
            log_success("Все чаты уже обработаны!")
            return
        
        series_count = 0
        start_time = datetime.now()
        
        for i, chat in enumerate(chats_to_join, 1):
            # Проверка дневного лимита
            if not self.can_join_today():
                log_warning("\n📊 Дневной лимит исчерпан!")
                log_info("Продолжите завтра")
                break
            
            # Пауза после серии
            if series_count >= PAUSE_AFTER_SERIES:
                pause_mins = random.randint(PAUSE_DURATION_MIN, PAUSE_DURATION_MAX)
                print(f"\n{Colors.YELLOW}☕ Пауза {pause_mins} мин после {series_count} вступлений...{Colors.RESET}")
                await asyncio.sleep(pause_mins * 60)
                series_count = 0
            
            # Задержка между вступлениями
            if i > 1:
                delay = random.randint(MIN_DELAY, MAX_DELAY)
                mins, secs = divmod(delay, 60)
                print(f"\r⏳ Задержка: {mins:02d}:{secs:02d}  ", end='', flush=True)
                await asyncio.sleep(delay)
                print()
            
            # Вступление
            chat_name = chat.get('name', chat['id'])
            print(f"[{i}/{len(chats_to_join)}] Вступаю в {chat_name}...")
            
            success = await self.join_chat(chat)
            
            if success:
                self.increment_joins()
                series_count += 1
                remaining = JOINS_PER_DAY - self.progress['joins_today']
                print(f"  {Colors.GREEN}✓ Вступил! Осталось сегодня: {remaining}{Colors.RESET}")
            else:
                print(f"  {Colors.RED}✗ Не вступил{Colors.RESET}")
            
            # Сохраняем прогресс после каждого действия
            save_progress(self.account_id, self.progress)
            
            # Прогресс-бар
            if i % 5 == 0:
                print(f"\n{progress_bar(self.joined_count + self.failed_count, len(chats_to_join))}")
        
        # Итоги
        end_time = datetime.now()
        duration = end_time - start_time
        
        header("ИТОГИ")
        print(f"\n⏱ Время: {duration}")
        print(f"✅ Вступил: {self.joined_count}")
        print(f"❌ Ошибки: {self.failed_count}")
        print(f"⏭ Пропущено: {self.skipped_count}")
        print(f"\n📊 Прогресс сохранён в {CONFIG_DIR / 'accounts' / str(self.account_id) / 'progress.json'}")


# =============================================================================
# ИМПОРТ JoinChannelRequest
# =============================================================================

from telethon.tl.functions.channels import JoinChannelRequest


# =============================================================================
# МЕНЮ
# =============================================================================

def show_menu():
    """Главное меню"""
    
    while True:
        header("ВСТУПЛЕНИЕ В ЧАТЫ")
        
        print(f"\n  Лимит вступлений в день: {JOINS_PER_DAY}")
        print(f"  Задержка: {MIN_DELAY}-{MAX_DELAY} сек")
        print(f"  Папка аккаунтов: {CONFIG_DIR / 'accounts'}")
        print()
        
        print("  1. Вступить в чаты (выбрать аккаунт)")
        print("  2. Настройки лимитов")
        print("  3. Показать прогресс по аккаунтам")
        print("  4. Сбросить прогресс аккаунта")
        print("  5. Открыть папку с аккаунтами")
        print("  0. Выход")
        print()
        
        choice = input("Выбор (0-5): ").strip()
        
        if choice == '1':
            # Вступить в чаты
            header("ВЫБОР АККАУНТА")
            
            accounts = load_accounts()
            if not accounts:
                log_error("Нет включённых аккаунтов!")
                input("\nНажмите Enter...")
                continue
            
            print("\nДоступные аккаунты:")
            for i, acc in enumerate(accounts, 1):
                print(f"  {i}. {acc.get('name', f'Аккаунт {acc[\"id\"]}')} (ID: {acc['id']})")
            
            try:
                acc_index = input("\nНомер аккаунта (Enter для отмены): ").strip()
                if not acc_index:
                    continue
                
                account = accounts[int(acc_index) - 1]
                account_id = account['id']
                
                # Загружаем чаты
                chats = load_account_chats(account_id)
                if not chats:
                    log_error(f"Нет чатов для аккаунта {account_id}!")
                    log_info("Запустите сначала scripts/distribute_chats.py")
                    input("\nНажмите Enter...")
                    continue
                
                # Создаём клиент
                client = create_client(account)
                
                # Запускаем вступление
                async def run():
                    await client.connect()
                    
                    if not await client.is_user_authorized():
                        log_error("Аккаунт не авторизован!")
                        await client.disconnect()
                        return
                    
                    me = await client.get_me()
                    log_success(f"Авторизован: @{me.username or me.first_name}")
                    print()
                    
                    manager = JoinManager(client, account_id)
                    await manager.run_join(chats)
                    
                    await client.disconnect()
                
                asyncio.run(run())
                
            except (IndexError, ValueError) as e:
                log_error(f"Неверный номер аккаунта!")
            except Exception as e:
                log_error(f"Ошибка: {e}")
                import traceback
                traceback.print_exc()
            
            input("\nНажмите Enter...")
        
        elif choice == '2':
            # Настройки
            header("НАСТРОЙКИ ЛИМИТОВ")
            
            print(f"\n  1. Вступлений в день: {JOINS_PER_DAY}")
            print(f"  2. Мин. задержка: {MIN_DELAY} сек")
            print(f"  3. Макс. задержка: {MAX_DELAY} сек")
            print(f"  4. Пауза после: {PAUSE_AFTER_SERIES} вступлений")
            print(f"  5. Длительность паузы: {PAUSE_DURATION_MIN}-{PAUSE_DURATION_MAX} мин")
            print()
            
            sub_choice = input("Выбор (0-5): ").strip()
            
            if sub_choice == '1':
                global JOINS_PER_DAY
                new_val = input(f"Новое значение ({JOINS_PER_DAY}): ").strip()
                if new_val:
                    JOINS_PER_DAY = int(new_val)
                    log_success(f"Установлено: {JOINS_PER_DAY}")
            
            elif sub_choice == '2':
                global MIN_DELAY
                new_val = input(f"Новое значение ({MIN_DELAY}): ").strip()
                if new_val:
                    MIN_DELAY = int(new_val)
                    log_success(f"Установлено: {MIN_DELAY}")
            
            elif sub_choice == '3':
                global MAX_DELAY
                new_val = input(f"Новое значение ({MAX_DELAY}): ").strip()
                if new_val:
                    MAX_DELAY = int(new_val)
                    log_success(f"Установлено: {MAX_DELAY}")
            
            elif sub_choice == '4':
                global PAUSE_AFTER_SERIES
                new_val = input(f"Новое значение ({PAUSE_AFTER_SERIES}): ").strip()
                if new_val:
                    PAUSE_AFTER_SERIES = int(new_val)
                    log_success(f"Установлено: {PAUSE_AFTER_SERIES}")
            
            elif sub_choice == '5':
                global PAUSE_DURATION_MIN, PAUSE_DURATION_MAX
                new_min = input(f"Мин. пауза ({PAUSE_DURATION_MIN}): ").strip()
                new_max = input(f"Макс. пауза ({PAUSE_DURATION_MAX}): ").strip()
                if new_min:
                    PAUSE_DURATION_MIN = int(new_min)
                if new_max:
                    PAUSE_DURATION_MAX = int(new_max)
                log_success(f"Установлено: {PAUSE_DURATION_MIN}-{PAUSE_DURATION_MAX} мин")
            
            input("\nНажмите Enter...")
        
        elif choice == '3':
            # Прогресс
            header("ПРОГРЕСС ПО АККАУНТАМ")
            
            accounts = load_accounts()
            
            for acc in accounts:
                acc_id = acc['id']
                progress = load_progress(acc_id)
                chats = load_account_chats(acc_id)
                
                joined = len(progress.get('joined', []))
                failed = len(progress.get('failed', []))
                total = len(chats)
                
                print(f"\n  Аккаунт {acc_id} ({acc.get('name', 'Unknown')}):")
                print(f"    Чатов всего: {total}")
                print(f"    Вступил: {joined}")
                print(f"    Ошибки: {failed}")
                print(f"    Осталось: {total - joined - failed}")
                
                if total > 0:
                    pct = (joined / total) * 100
                    print(f"    Прогресс: {pct:.1f}%")
            
            input("\nНажмите Enter...")
        
        elif choice == '4':
            # Сброс прогресса
            header("СБРОС ПРОГРЕССА")
            
            accounts = load_accounts()
            
            print("\nДоступные аккаунты:")
            for i, acc in enumerate(accounts, 1):
                acc_id = acc['id']
                progress = load_progress(acc_id)
                joined = len(progress.get('joined', []))
                print(f"  {i}. {acc.get('name', f'Аккаунт {acc_id}')} (вступил: {joined})")
            
            try:
                acc_index = input("\nНомер аккаунта для сброса (0 для отмены): ").strip()
                if acc_index == '0':
                    continue
                
                account = accounts[int(acc_index) - 1]
                acc_id = account['id']
                
                confirm = input(f"Сбросить прогресс аккаунта {acc_id}? (y/n): ").strip().lower()
                if confirm == 'y':
                    save_progress(acc_id, {
                        'joined': [],
                        'failed': [],
                        'last_join_date': None,
                        'joins_today': 0
                    })
                    log_success(f"Прогресс аккаунта {acc_id} сброшен!")
                else:
                    log_info("Отменено")
            
            except (IndexError, ValueError) as e:
                log_error(f"Неверный номер аккаунта!")
            
            input("\nНажмите Enter...")
        
        elif choice == '5':
            # Открыть папку
            header("ОТКРЫТИЕ ПАПКИ")
            
            accounts_dir = CONFIG_DIR / 'accounts'
            if accounts_dir.exists():
                import os
                os.startfile(str(accounts_dir))
                log_success(f"Папка открыта: {accounts_dir}")
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
