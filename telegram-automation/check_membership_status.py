"""
Проверка реального членства в чатах
Показывает: в каких чатах аккаунт состоит и может писать
"""
import asyncio
import sys
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.types import Channel

sys.path.insert(0, str(Path(__file__).parent))
from multi_account import Config, AccountConfig, ProxyManager

class Colors:
    INFO = '\033[94m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def cprint(msg, color=Colors.RESET):
    print(f"{color}{msg}{Colors.RESET}", flush=True)

def header(msg):
    print(f"\n{Colors.BOLD}{'=' * 70}{Colors.RESET}", flush=True)
    cprint(msg, Colors.BOLD)
    print(f"{'=' * 70}\n", flush=True)

async def check_all_chats():
    header("🔍 ПРОВЕРКА ЧЛЕНСТВА В ЧАТАХ")
    
    # Загрузка
    chats = Config.get_chats()
    cprint(f"📋 Чатов в базе: {len(chats)}", Colors.INFO)
    
    # Подключение
    accounts = Config.load_accounts()['accounts']
    acc = next((a for a in accounts if a.get('enabled')), None)
    if not acc:
        cprint("❌ Нет включённых аккаунтов!", Colors.ERROR)
        return
    
    account_config = AccountConfig(acc)
    proxy_manager = ProxyManager()
    client = proxy_manager.create_client_with_proxy(account_config)
    
    cprint("\n🔄 Подключение...", Colors.INFO)
    await client.connect()
    
    if not await client.is_user_authorized():
        cprint("❌ Не авторизован!", Colors.ERROR)
        return
    
    me = await client.get_me()
    cprint(f"✅ @{me.username or me.first_name}", Colors.SUCCESS)
    
    # Загрузка диалогов
    cprint("\n📚 Загрузка диалогов...", Colors.INFO)
    dialog_ids = set()
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if hasattr(entity, 'username') and entity.username:
            dialog_ids.add(entity.username)
        dialog_ids.add(str(entity.id))
    
    cprint(f"✅ Диалогов: {len(dialog_ids)}", Colors.SUCCESS)
    
    # Проверка каждого чата
    header("📊 РЕЗУЛЬТАТЫ")
    
    in_chat = []      # Состоим, можно писать
    readonly = []     # Состоим, но только чтение (каналы)
    not_member = []   # Не состоим
    errors = []       # Ошибки
    
    cprint("\nПроверка...\n", Colors.INFO)
    
    for i, chat in enumerate(chats, 1):
        chat_id = chat['id']
        chat_name = chat.get('name', chat_id)[:50]
        
        if chat_id not in dialog_ids:
            not_member.append(chat)
            cprint(f"  [{i}/{len(chats)}] ❌ НЕ СОСТОИМ: {chat_name}", Colors.ERROR)
        else:
            # Проверяем тип чата
            try:
                entity = await client.get_entity(chat_id)
                
                if isinstance(entity, Channel):
                    if entity.broadcast:
                        # Канал - только чтение (если не админ)
                        readonly.append(chat)
                        cprint(f"  [{i}/{len(chats)}] 🔒 КАНАЛ (чтение): {chat_name}", Colors.WARNING)
                    else:
                        # Группа
                        in_chat.append(chat)
                        cprint(f"  [{i}/{len(chats)}] ✅ ГРУППА: {chat_name}", Colors.SUCCESS)
                else:
                    in_chat.append(chat)
                    cprint(f"  [{i}/{len(chats)}] ✅ ЧАТ: {chat_name}", Colors.SUCCESS)
                    
            except Exception as e:
                errors.append({'chat': chat, 'error': str(e)})
                cprint(f"  [{i}/{len(chats)}] ⚠ ОШИБКА: {chat_name} - {type(e).__name__}", Colors.WARNING)
        
        if i % 10 == 0:
            cprint(f"      ... проверено {i}/{len(chats)}", Colors.INFO)
    
    await client.disconnect()
    
    # Итог
    header("📊 ИТОГИ")
    cprint(f"\n  ✅ Можно писать: {len(in_chat)}", Colors.SUCCESS)
    cprint(f"  🔒 Только чтение: {len(readonly)}", Colors.WARNING)
    cprint(f"  ❌ Не состоим: {len(not_member)}", Colors.ERROR)
    cprint(f"  ⚠ Ошибки: {len(errors)}", Colors.WARNING)
    
    # Сохранение
    if not_member:
        cprint(f"\n💾 Сохранение списка для вступления...", Colors.INFO)
        join_file = Path('logs/chats_to_join.json')
        join_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(join_file, 'w', encoding='utf-8') as f:
            json.dump({
                '_comment': 'Чаты для вступления',
                '_total': len(not_member),
                'chats': not_member
            }, f, ensure_ascii=False, indent=2)
        
        cprint(f"✅ Сохранено: {join_file} ({len(not_member)} чатов)", Colors.SUCCESS)
    
    # Показываем первые 20 чатов для вступления
    if not_member:
        header("❌ НЕ СОСТОИМ (первые 20)")
        for i, c in enumerate(not_member[:20], 1):
            cprint(f"  {i}. {c.get('name', c.get('id'))[:60]}", Colors.ERROR)
        if len(not_member) > 20:
            cprint(f"  ... ещё {len(not_member) - 20}", Colors.WARNING)

if __name__ == '__main__':
    import json
    try:
        asyncio.run(check_all_chats())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠ Прервано{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.ERROR}❌ Ошибка: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
