"""
Вывод списка чатов, в которые аккаунт вступил
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from multi_account import Config, AccountConfig, ProxyManager

class Colors:
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[36m'

def cprint(msg, color=Colors.RESET):
    print(f"{color}{msg}{Colors.RESET}", flush=True)

def header(msg):
    print(f"\n{Colors.BOLD}{'=' * 70}{Colors.RESET}", flush=True)
    cprint(msg, Colors.BOLD)
    print(f"{'=' * 70}\n", flush=True)

async def get_joined_chats():
    header("📋 СПИСОК ЧАТОВ, ГДЕ СОСТОИТ АККАУНТ")
    
    # Подключение
    accounts = Config.load_accounts()['accounts']
    acc = next((a for a in accounts if a.get('enabled')), None)
    if not acc:
        cprint("❌ Нет включённых аккаунтов!", Colors.ERROR)
        return
    
    account_config = AccountConfig(acc)
    proxy_manager = ProxyManager()
    client = proxy_manager.create_client_with_proxy(account_config)
    
    cprint("\n🔄 Подключение...", Colors.CYAN)
    await client.connect()
    
    if not await client.is_user_authorized():
        cprint("❌ Не авторизован!", Colors.ERROR)
        return
    
    me = await client.get_me()
    cprint(f"✅ @{me.username or me.first_name}", Colors.SUCCESS)
    
    # Загрузка всех диалогов
    cprint("\n📚 Загрузка диалогов...", Colors.CYAN)
    dialogs_list = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        dialog_type = "channel" if hasattr(entity, 'broadcast') else "group"
        dialogs_list.append({
            'id': entity.username if hasattr(entity, 'username') and entity.username else str(entity.id),
            'name': getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown'),
            'type': dialog_type
        })
    
    cprint(f"✅ Диалогов: {len(dialogs_list)}", Colors.SUCCESS)
    
    # Загрузка базы чатов
    base_chats = Config.get_chats()
    base_ids = {c['id'] for c in base_chats}
    base_names = {c['id']: c.get('name', c['id']) for c in base_chats}
    
    cprint(f"📋 Чатов в базе: {len(base_chats)}", Colors.CYAN)
    
    # Фильтрация: чаты из базы, где состоим
    in_base_and_joined = []
    not_in_base = []
    
    for d in dialogs_list:
        if d['id'] in base_ids:
            in_base_and_joined.append(d)
        else:
            not_in_base.append(d)
    
    # Вывод
    header(f"📊 ЧАТЫ ИЗ БАЗЫ ({len(in_base_and_joined)} из {len(base_chats)})")
    
    for i, d in enumerate(in_base_and_joined[:100], 1):
        name = base_names.get(d['id'], d['name'])[:60]
        cprint(f"  {i}. {name} (@{d['id']})", Colors.SUCCESS)
    
    if len(in_base_and_joined) > 100:
        cprint(f"\n  ... ещё {len(in_base_and_joined) - 100}", Colors.WARNING)
    
    # Сохранение в файл
    save_file = Path('logs/joined_chats.txt')
    save_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(save_file, 'w', encoding='utf-8') as f:
        f.write(f"Дата: {datetime.now().isoformat()}\n")
        f.write(f"Аккаунт: @{me.username or me.first_name}\n")
        f.write(f"Всего диалогов: {len(dialogs_list)}\n")
        f.write(f"Чатов из базы: {len(in_base_and_joined)} из {len(base_chats)}\n\n")
        f.write("=" * 70 + "\n\n")
        
        for i, d in enumerate(in_base_and_joined, 1):
            name = base_names.get(d['id'], d['name'])
            f.write(f"{i}. {name} (@{d['id']})\n")
    
    cprint(f"\n💾 Сохранено: {save_file}", Colors.SUCCESS)
    
    # Чаты, где НЕ состоим
    header(f"❌ НЕ СОСТОИМ ({len(base_chats) - len(in_base_and_joined)})")
    
    not_joined = [c for c in base_chats if c['id'] not in {d['id'] for d in in_base_and_joined}]
    
    for i, c in enumerate(not_joined[:50], 1):
        cprint(f"  {i}. {c.get('name', c.get('id'))[:60]}", Colors.ERROR)
    
    if len(not_joined) > 50:
        cprint(f"\n  ... ещё {len(not_joined) - 50}", Colors.WARNING)
    
    await client.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(get_joined_chats())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}⚠ Прервано{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.ERROR}❌ Ошибка: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
