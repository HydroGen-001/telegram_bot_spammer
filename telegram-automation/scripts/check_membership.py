"""
Check Membership Script
Проверка реального членства аккаунта в чатах из базы

Методы проверки:
1. get_dialogs() — сверяем с списком диалогов аккаунта (быстро)
2. get_messages() — пытаемся получить сообщения (точно для каналов)
3. get_participants() — пытаемся получить список участников (точно для групп)

Запуск: python scripts/check_membership.py
"""

import asyncio
import json
import socket
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Set
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChannelPrivateError, UserNotParticipantError
from telethon.tl.types import ChannelParticipantsAdmin


# =============================================================================
# КОНФИГУРАЦИЯ
# =============================================================================

BASE_DIR = Path(__file__).parent.parent.resolve()
ACCOUNTS_FILE = BASE_DIR / 'accounts.json'
CHATS_FILE = BASE_DIR / 'config' / 'chats.json'
SESSIONS_DIR = BASE_DIR / 'sessions'
LOGS_DIR = BASE_DIR / 'logs'

# Лимиты проверки
CHECK_LIMIT = 200  # Сколько чатов проверять
TIMEOUT = 10  # Таймаут на запрос (сек)

# Метод проверки: 'dialogs' | 'messages' | 'participants'
CHECK_METHOD = 'dialogs'  # 'dialogs' — самый быстрый и надёжный


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
    percentage = current / total if total > 0 else 0
    filled = int(width * percentage)
    bar = '█' * filled + '░' * (width - filled)
    return f"[{bar}] {current}/{total} ({percentage*100:.1f}%)"


# =============================================================================
# ЗАГРУЗКА ДАННЫХ
# =============================================================================

def load_accounts() -> List[Dict]:
    if not ACCOUNTS_FILE.exists():
        log_error(f"Файл {ACCOUNTS_FILE} не найден!")
        return []

    with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        accounts = data.get('accounts', [])
        enabled = [a for a in accounts if a.get('enabled', False)]
        log_info(f"Всего: {len(accounts)}, Включено: {len(enabled)}")
        return enabled


def load_chats() -> List[Dict]:
    if not CHATS_FILE.exists():
        log_error(f"Файл {CHATS_FILE} не найден!")
        return []

    with open(CHATS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        chats = data.get('chats', [])
        enabled = [c for c in chats if c.get('enabled', True)]
        log_info(f"Загружено {len(enabled)} чатов")
        return enabled


def create_client(account: Dict) -> TelegramClient:
    session_path = SESSIONS_DIR / f"{account['session_name']}.session"

    if not session_path.exists():
        log_error(f"Сессия не найдена: {session_path}")
        return None

    client = TelegramClient(str(session_path), account.get('api_id', 0), account.get('api_hash', ''))

    proxy_config = account.get('proxy', {})
    if proxy_config.get('enabled', False) and proxy_config.get('host'):
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
            log_info(f"Прокси: {proxy_ip}:{proxy_config['port']}")
        except Exception as e:
            log_warning(f"Не удалось установить прокси: {e}")

    return client


# =============================================================================
# ПРОВЕРКА ЧЛЕНСТВА
# =============================================================================

class MembershipChecker:
    def __init__(self, client: TelegramClient, account_id: int):
        self.client = client
        self.account_id = account_id
        self.total = 0
        self.member = 0
        self.not_member = 0
        self.errors = 0
        self.private = 0
        self.results = {'member': [], 'not_member': [], 'private': [], 'errors': []}
        self.dialog_ids: Set[str] = set()

    async def load_dialogs(self) -> Set[str]:
        """Загружает список диалогов аккаунта для быстрой проверки"""
        dialog_ids = set()
        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            # Сохраняем username если есть, иначе id
            if hasattr(entity, 'username') and entity.username:
                dialog_ids.add(entity.username)
            dialog_ids.add(str(entity.id))
        log_info(f"Загружено {len(dialog_ids)} диалогов")
        return dialog_ids

    async def check_chat_dialogs(self, chat: Dict) -> Tuple[str, str]:
        """Проверка через список диалогов (БЫСТРО)"""
        chat_id = chat.get('id')
        
        if chat_id in self.dialog_ids:
            return 'member', ''
        
        # Пробуем также по числовому id
        try:
            entity = await self.client.get_entity(chat_id)
            if str(entity.id) in self.dialog_ids:
                return 'member', ''
        except Exception:
            pass
        
        return 'not_member', 'Нет в диалогах'

    async def check_chat_messages(self, chat: Dict) -> Tuple[str, str]:
        """Проверка через попытку получить сообщения (ТОЧНО для каналов)"""
        chat_id = chat.get('id')
        
        try:
            # Пытаемся получить 1 сообщение
            async for msg in self.client.iter_messages(chat_id, limit=1):
                return 'member', ''
            return 'member', ''  # Если сообщений нет, но доступ есть
        except ChannelPrivateError:
            return 'private', 'Частный канал'
        except UserNotParticipantError:
            return 'not_member', 'Не состоит в канале'
        except ValueError as e:
            return 'not_member', f'Чат не найден: {str(e)[:30]}'
        except FloodWaitError as e:
            return 'error', f'FloodWait: {e.seconds} сек'
        except Exception as e:
            error_name = type(e).__name__
            return 'error', f'{error_name}: {str(e)[:50]}'

    async def check_chat_participants(self, chat: Dict) -> Tuple[str, str]:
        """Проверка через список участников (ТОЧНО для групп)"""
        chat_id = chat.get('id')
        
        try:
            # Пытаемся получить участников
            async for _ in self.client.iter_participants(chat_id, limit=1):
                return 'member', ''
            return 'member', ''
        except ChannelPrivateError:
            return 'private', 'Частный канал'
        except UserNotParticipantError:
            return 'not_member', 'Не состоит в группе'
        except ValueError as e:
            return 'not_member', f'Чат не найден: {str(e)[:30]}'
        except FloodWaitError as e:
            return 'error', f'FloodWait: {e.seconds} сек'
        except Exception as e:
            error_name = type(e).__name__
            return 'error', f'{error_name}: {str(e)[:50]}'

    async def check_chat(self, chat: Dict) -> Tuple[str, str]:
        """Основной метод проверки (выбирает стратегию)"""
        if CHECK_METHOD == 'dialogs':
            return await self.check_chat_dialogs(chat)
        elif CHECK_METHOD == 'messages':
            return await self.check_chat_messages(chat)
        elif CHECK_METHOD == 'participants':
            return await self.check_chat_participants(chat)
        else:
            return await self.check_chat_dialogs(chat)

    async def check_chats(self, chats: List[Dict], limit: int = 100):
        chats_to_check = chats[:limit]
        self.total = len(chats_to_check)

        header(f"ПРОВЕРКА ЧЛЕНСТВА (Аккаунт {self.account_id})")
        print(f"\n📊 Всего чатов для проверки: {self.total}")
        print(f"📋 Метод: {CHECK_METHOD}")
        print(f"⏱ Таймаут: {TIMEOUT} сек\n")

        # Загружаем диалоги для метода 'dialogs'
        if CHECK_METHOD == 'dialogs':
            log_info("Загрузка списка диалогов...")
            self.dialog_ids = await self.load_dialogs()

        start_time = datetime.now()

        for i, chat in enumerate(chats_to_check, 1):
            chat_id = chat.get('id')
            chat_name = chat.get('name', chat_id)

            status, error = await self.check_chat(chat)
            now = datetime.now().isoformat()

            if status == 'member':
                self.member += 1
                self.results['member'].append({'id': chat_id, 'name': chat_name, 'checked_at': now})
                print(f"[{i}/{self.total}] {Colors.GREEN}✓ В чате{Colors.RESET}: {chat_name}")

            elif status == 'not_member':
                self.not_member += 1
                self.results['not_member'].append({'id': chat_id, 'name': chat_name, 'error': error, 'checked_at': now})
                print(f"[{i}/{self.total}] {Colors.RED}✗ НЕ В ЧАТЕ{Colors.RESET}: {chat_name}")

            elif status == 'private':
                self.private += 1
                self.results['private'].append({'id': chat_id, 'name': chat_name, 'error': error, 'checked_at': now})
                print(f"[{i}/{self.total}] {Colors.YELLOW}🔒 Частный{Colors.RESET}: {chat_name}")

            elif status == 'error':
                self.errors += 1
                self.results['errors'].append({'id': chat_id, 'name': chat_name, 'error': error, 'checked_at': now})
                print(f"[{i}/{self.total}] {Colors.RED}⚠ Ошибка{Colors.RESET}: {chat_name} ({error})")

            if i % 10 == 0:
                print(f"\n{progress_bar(i, self.total)}\n")
                await asyncio.sleep(1)

        duration = datetime.now() - start_time

        header("ИТОГИ")
        print(f"\n⏱ Время: {duration}")
        print(f"\n✅ В чате: {self.member} ({self.member/self.total*100:.1f}%)")
        print(f"❌ НЕ в чате: {self.not_member} ({self.not_member/self.total*100:.1f}%)")
        print(f"🔒 Частные: {self.private}")
        print(f"⚠ Ошибки: {self.errors}")

        self.save_results()

    def save_results(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        results_file = LOGS_DIR / f'membership_check_{self.account_id}.json'

        report = {
            'account_id': self.account_id,
            'checked_at': datetime.now().isoformat(),
            'total': self.total,
            'member': self.member,
            'not_member': self.not_member,
            'private': self.private,
            'errors': self.errors,
            'results': self.results
        }

        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        log_success(f"Результаты: {results_file}")
        
        # Экспорт чатов для вступления
        self.export_not_member_chats()
    
    def export_not_member_chats(self):
        """Экспорт чатов, в которых не состоит аккаунт (для вступления)"""
        if not self.results['not_member']:
            return
        
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        export_file = LOGS_DIR / f'join_chats_{self.account_id}.json'
        
        # Формируем список для вступления
        join_list = []
        for chat in self.results['not_member']:
            join_list.append({
                'id': chat['id'],
                'name': chat['name'],
                'type': 'channel',
                'enabled': True
            })
        
        export_data = {
            '_comment': f'Чаты для вступления (аккаунт {self.account_id})',
            '_generated_at': datetime.now().isoformat(),
            '_total': len(join_list),
            'chats': join_list
        }
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        log_success(f"Экспорт для вступления: {export_file} ({len(join_list)} чатов)")


# =============================================================================
# МЕНЮ
# =============================================================================

def show_menu():
    global CHECK_METHOD, CHECK_LIMIT
    
    while True:
        header("ПРОВЕРКА ЧЛЕНСТВА В ЧАТАХ")
        print(f"\n📁 Аккаунты: {ACCOUNTS_FILE}")
        print(f"📁 Чаты: {CHATS_FILE}")
        print(f"📊 Лимит: {CHECK_LIMIT} чатов")
        print(f"🔍 Метод: {CHECK_METHOD}\n")

        print("  1. Проверить членство (выбрать аккаунт)")
        print("  2. Показать результаты")
        print("  3. Выбрать метод проверки")
        print("  4. Изменить лимит")
        print("  0. Выход\n")

        choice = input("Выбор (0-4): ").strip()

        if choice == '1':
            header("ВЫБОР АККАУНТА")
            accounts = load_accounts()

            if not accounts:
                log_error("Нет аккаунтов!")
                input("\nНажмите Enter...")
                continue

            print("\nАккаунты:")
            for i, acc in enumerate(accounts, 1):
                print(f"  {i}. {acc.get('name')} (ID: {acc['id']})")

            try:
                idx = input("\nНомер (Enter=отмена): ").strip()
                if not idx:
                    continue

                account = accounts[int(idx) - 1]
                client = create_client(account)
                if not client:
                    input("\nНажмите Enter...")
                    continue

                chats = load_chats()
                if not chats:
                    log_error("Чаты пусты!")
                    input("\nНажмите Enter...")
                    continue

                async def run():
                    await client.connect()
                    if not await client.is_user_authorized():
                        log_error("Не авторизован!")
                        await client.disconnect()
                        return

                    me = await client.get_me()
                    log_success(f"@{me.username or me.first_name}")
                    print()

                    checker = MembershipChecker(client, account['id'])
                    await checker.check_chats(chats, CHECK_LIMIT)
                    await client.disconnect()

                asyncio.run(run())

            except (IndexError, ValueError) as e:
                log_error("Неверный номер!")
            except Exception as e:
                log_error(f"Ошибка: {e}")

            input("\nНажмите Enter...")

        elif choice == '2':
            header("РЕЗУЛЬТАТЫ")
            if not LOGS_DIR.exists():
                log_warning("Нет результатов")
                input("\nНажмите Enter...")
                continue

            files = list(LOGS_DIR.glob('membership_check_*.json'))
            if not files:
                log_warning("Нет результатов")
                input("\nНажмите Enter...")
                continue

            print("\nОтчёты:")
            for i, f in enumerate(files, 1):
                print(f"  {i}. {f.name}")

            try:
                idx = input("\nНомер (Enter=отмена): ").strip()
                if not idx:
                    continue

                with open(files[int(idx) - 1], 'r', encoding='utf-8') as f:
                    report = json.load(f)

                print(f"\n📊 Аккаунт {report['account_id']}")
                print(f"📅 {report['checked_at']}")
                print(f"\n✅ В чате: {report['member']}")
                print(f"❌ НЕ в чате: {report['not_member']}")
                print(f"🔒 Частные: {report['private']}")
                print(f"⚠ Ошибки: {report['errors']}")

                not_member = report.get('results', {}).get('not_member', [])
                if not_member:
                    print(f"\n❌ НЕ состоим в ({len(not_member)}):")
                    for i, c in enumerate(not_member[:20], 1):
                        print(f"  {i}. {c['name']} (@{c['id']})")
                    if len(not_member) > 20:
                        print(f"  ... ещё {len(not_member) - 20}")
                
                # Показываем файл для вступления
                join_file = LOGS_DIR / f'join_chats_{report["account_id"]}.json'
                if join_file.exists():
                    print(f"\n💾 Файл для вступления: {join_file.name}")

            except Exception as e:
                log_error(f"Ошибка: {e}")

            input("\nНажмите Enter...")
        
        elif choice == '3':
            header("МЕТОД ПРОВЕРКИ")
            print("\n1. dialogs — Быстро (сверка со списком диалогов)")
            print("2. messages — Точно (попытка читать сообщения)")
            print("3. participants — Точно (попытка читать участников)")
            print(f"\nТекущий: {CHECK_METHOD}")
            
            method_choice = input("\nВыберите метод (1-3, Enter=отмена): ").strip()
            if method_choice == '1':
                CHECK_METHOD = 'dialogs'
                log_success("Метод: dialogs")
            elif method_choice == '2':
                CHECK_METHOD = 'messages'
                log_success("Метод: messages")
            elif method_choice == '3':
                CHECK_METHOD = 'participants'
                log_success("Метод: participants")
            
            input("\nНажмите Enter...")

        elif choice == '4':
            header("ЛИМИТ ПРОВЕРКИ")
            print(f"\nТекущий лимит: {CHECK_LIMIT}")
            try:
                new_limit = input("Новый лимит (Enter=отмена): ").strip()
                if new_limit:
                    CHECK_LIMIT = int(new_limit)
                    log_success(f"Лимит установлен: {CHECK_LIMIT}")
            except ValueError:
                log_error("Неверное число!")
            
            input("\nНажмите Enter...")

        elif choice == '0':
            break

        else:
            log_warning("Неверный выбор")
            input("\nНажмите Enter...")


# =============================================================================
# ЗАПУСК
# =============================================================================

if __name__ == "__main__":
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
