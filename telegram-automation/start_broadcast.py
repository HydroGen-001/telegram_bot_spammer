"""
Автоматический запуск рассылки из пункта 1 меню multi_account_start.py
Сначала вступает в чаты, потом делает рассылку
Выводит все этапы работы в реальном времени
"""
import asyncio
import random
import sys
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, ChannelPrivateError

# Добавляем путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

from multi_account import Config, AccountConfig, ProxyManager, ChatJoinManager
from multi_account_start import send_message_with_photo, broadcast_with_account, check_accounts_ready, log, SESSIONS_DIR

# =============================================================================
# ЦВЕТА ДЛЯ ВЫВОДА
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
    CYAN = '\033[36m'

def cprint(msg, color=Colors.RESET):
    print(f"{color}{msg}{Colors.RESET}", flush=True)

def header(msg):
    print(f"\n{Colors.BOLD}{'=' * 70}{Colors.RESET}", flush=True)
    cprint(msg, Colors.BOLD)
    print(f"{'=' * 70}\n", flush=True)

# =============================================================================
# РАССЫЛКА
# =============================================================================

async def join_not_member_chats(client, chats, max_join=50):
    """Вступить в чаты, где не состоим"""
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.errors import ChatAdminRequiredError, UserAlreadyParticipantError
    
    cprint("\n📋 ПРОВЕРКА ЧЛЕНСТВА...", Colors.INFO)
    
    # Загрузка диалогов
    dialog_ids = set()
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if hasattr(entity, 'username') and entity.username:
            dialog_ids.add(entity.username)
        dialog_ids.add(str(entity.id))
    
    cprint(f"   Диалогов: {len(dialog_ids)}", Colors.INFO)
    
    # Поиск чатов для вступления
    to_join = []
    for chat in chats:
        chat_id = chat['id']
        if chat_id not in dialog_ids:
            to_join.append(chat)
    
    cprint(f"   Не состоим в: {len(to_join)} чатах", Colors.WARNING)
    
    if not to_join:
        cprint("   ✅ Уже во всех чатах!", Colors.SUCCESS)
        return {'joined': 0, 'failed': 0, 'skipped': 0, 'details': []}
    
    # Вступление
    cprint(f"\n📥 ВСТУПЛЕНИЕ (до {max_join} чатов)...", Colors.INFO)
    cprint(f"{'=' * 70}", Colors.INFO)
    
    joined = 0
    failed = 0
    skipped = 0
    details = []  # Детали для отчёта
    
    for i, chat in enumerate(to_join[:max_join], 1):
        chat_id = chat['id']
        chat_name = chat.get('name', chat_id)[:55]
        
        try:
            # Пытаемся получить канал/группу
            entity = await client.get_entity(chat_id)
            
            # Вступаем через JoinChannelRequest
            await client(JoinChannelRequest(entity))
            cprint(f"  [{i:3d}/{max_join}] ✅ ВСТУПИЛ    | {chat_name}", Colors.SUCCESS)
            joined += 1
            details.append({'status': 'joined', 'chat': chat_name, 'id': chat_id})
            await asyncio.sleep(2)  # Пауза между вступлениями
            
        except UserAlreadyParticipantError:
            cprint(f"  [{i:3d}/{max_join}] ➖ УЖЕ В ЧАТЕ | {chat_name}", Colors.INFO)
            skipped += 1
            details.append({'status': 'already', 'chat': chat_name, 'id': chat_id})
        except ChatAdminRequiredError:
            cprint(f"  [{i:3d}/{max_join}] ⚠️ НУЖНЫ ПРАВА| {chat_name}", Colors.WARNING)
            failed += 1
            details.append({'status': 'admin_required', 'chat': chat_name, 'id': chat_id})
        except ValueError as e:
            cprint(f"  [{i:3d}/{max_join}] ❌ НЕ НАЙДЕН  | {chat_name}", Colors.WARNING)
            skipped += 1
            details.append({'status': 'not_found', 'chat': chat_name, 'id': chat_id})
        except FloodWaitError as e:
            wait_mins = e.seconds // 60
            cprint(f"  [{i:3d}/{max_join}] ⏳ FLOOD WAIT | {wait_mins} мин | {chat_name}", Colors.WARNING)
            # Ждём и продолжаем
            await asyncio.sleep(e.seconds)
            joined += 1
            details.append({'status': 'joined_floodwait', 'chat': chat_name, 'id': chat_id})
        except Exception as e:
            error_msg = str(e)[:30]
            cprint(f"  [{i:3d}/{max_join}] ❌ {type(e).__name__:15} | {error_msg:30} | {chat_name}", Colors.ERROR)
            failed += 1
            details.append({'status': 'error', 'chat': chat_name, 'id': chat_id, 'error': str(e)})
    
    # Итоговый отчёт
    cprint(f"{'=' * 70}", Colors.INFO)
    cprint("\n📊 ОТЧЁТ О ВСТУПЛЕНИИ", Colors.BOLD)
    cprint(f"{'=' * 70}", Colors.INFO)
    
    # Статистика
    cprint(f"\n  ✅ Успешно вступил:     {joined}", Colors.SUCCESS)
    cprint(f"  ➖ Уже был в чате:      {skipped}", Colors.INFO)
    cprint(f"  ❌ Ошибки:              {failed}", Colors.ERROR)
    cprint(f"  📋 Всего проверено:     {joined + skipped + failed}", Colors.INFO)
    
    # Детализация по ошибкам
    errors = [d for d in details if d['status'] in ('error', 'admin_required', 'not_found')]
    if errors:
        cprint(f"\n⚠️  ОШИБКИ ({len(errors)}):", Colors.WARNING)
        for err in errors[:10]:
            status = err['status']
            if status == 'error':
                cprint(f"     • {err['chat'][:50]}: {err.get('error', 'Unknown')[:30]}", Colors.ERROR)
            elif status == 'admin_required':
                cprint(f"     • {err['chat'][:50]}: нужны права админа", Colors.WARNING)
            elif status == 'not_found':
                cprint(f"     • {err['chat'][:50]}: чат не найден", Colors.WARNING)
        if len(errors) > 10:
            cprint(f"     ... и ещё {len(errors) - 10}", Colors.WARNING)
    
    # Список успешных вступлений
    success_list = [d for d in details if d['status'] in ('joined', 'joined_floodwait')]
    if success_list:
        cprint(f"\n✅ УСПЕШНЫЕ ВСТУПЛЕНИЯ ({len(success_list)}):", Colors.SUCCESS)
        for s in success_list[:15]:
            cprint(f"     • {s['chat'][:55]}", Colors.SUCCESS)
        if len(success_list) > 15:
            cprint(f"     ... и ещё {len(success_list) - 15}", Colors.SUCCESS)
    
    cprint(f"\n{'=' * 70}\n", Colors.INFO)
    
    return {'joined': joined, 'failed': failed, 'skipped': skipped, 'details': details}


async def run_broadcast():
    """Запуск рассылки с предварительным вступлением"""
    header("🚀 ЗАПУСК РАССЫЛКИ")
    
    # 1. Проверка готовности аккаунтов
    header("1️⃣ ПРОВЕРКА ГОТОВНОСТИ АККАУНТОВ")
    ready_accounts = await check_accounts_ready()
    
    if not ready_accounts:
        cprint("❌ Нет готовых аккаунтов!", Colors.ERROR)
        return
    
    cprint(f"\n✅ Готово аккаунтов: {len(ready_accounts)}", Colors.SUCCESS)
    
    # 2. Загрузка чатов
    header("2️⃣ ЗАГРУЗКА ЧАТОВ")
    chats = Config.get_chats()
    if not chats:
        cprint("❌ Чаты пусты!", Colors.ERROR)
        return
    
    cprint(f"✅ Загружено чатов: {len(chats)}", Colors.SUCCESS)
    
    # 3. Вступление в чаты
    header("3️⃣ ВСТУПЛЕНИЕ В ЧАТЫ")
    
    # Вопрос пользователю
    cprint("\n⚠ Аккаунт может не состоять в чатах из базы.", Colors.WARNING)
    cprint("   Сначала вступить в чаты, потом сделать рассылку?", Colors.WARNING)
    cprint("   1. Да, вступить (20 чатов)", Colors.INFO)
    cprint("   2. Нет, сразу рассылка", Colors.INFO)
    cprint("   3. Вступить больше (50 чатов)", Colors.INFO)
    
    # Автоматически выбираем 1 (вступить в 20 чатов за раз, чтобы избежать FloodWait)
    join_choice = '1'  # Можно заменить на input()
    
    if join_choice == '1':
        max_join = 20  # Уменьшил с 50 до 20
    elif join_choice == '3':
        max_join = 50  # Уменьшил с 200 до 50
    else:
        max_join = 0
    
    if max_join > 0:
        # Подключение для вступления
        acc = ready_accounts[0]
        account_config = AccountConfig(acc)
        proxy_manager = ProxyManager()
        client = proxy_manager.create_client_with_proxy(account_config)
        
        await client.connect()
        if await client.is_user_authorized():
            await join_not_member_chats(client, chats, max_join)
        await client.disconnect()
        
        cprint("\n⏱ Пауза 10 сек перед рассылкой...", Colors.YELLOW)
        await asyncio.sleep(10)
    
    # 4. Распределение
    header("4️⃣ РАСПРЕДЕЛЕНИЕ ЧАТОВ")
    distribution = {}
    chat_index = 0
    chats_per_account = 200
    
    for acc in ready_accounts:
        start = chat_index
        end = min(chat_index + chats_per_account, len(chats))
        distribution[acc['id']] = chats[start:end]
        chat_index = end
        cprint(f"  📋 {acc.get('name')}: {len(distribution[acc['id']])} чатов", Colors.INFO)
        if chat_index >= len(chats):
            break
    
    # 5. Старт
    header("5️⃣ НАЧАЛО РАССЫЛКИ")
    cprint(f"📊 Чатов всего: {len(chats)}", Colors.CYAN)
    cprint(f"👥 Аккаунтов: {len(ready_accounts)}", Colors.CYAN)
    cprint(f"⏱ Старт через 3 сек...", Colors.YELLOW)
    await asyncio.sleep(3)
    
    # 5. Запуск
    total_stats = {'total': 0, 'sent': 0, 'failed': 0, 'errors': []}
    start_time = datetime.now()
    
    for acc_id, acc_chats in distribution.items():
        if not acc_chats:
            continue
        
        acc = next((a for a in ready_accounts if a.get('id') == acc_id), None)
        if not acc:
            continue
        
        # Конфиг
        account_config = AccountConfig(acc)
        text = account_config.get_text()
        if not text:
            cprint(f"⚠ Аккаунт {acc_id}: текст не настроен", Colors.WARNING)
            continue
        
        photo_path = account_config.get_photo_path()
        limits = account_config.limits
        min_delay = limits.get('min_delay', 50)
        max_delay = limits.get('max_delay', 100)
        
        # Клиент с прокси
        proxy_manager = ProxyManager()
        client = proxy_manager.create_client_with_proxy(account_config)
        
        try:
            header(f"📤 АККАУНТ: {acc.get('name')}")
            
            # Подключение
            cprint("🔄 Подключение...", Colors.INFO)
            await client.connect()
            
            if not await client.is_user_authorized():
                cprint("❌ Не авторизован!", Colors.ERROR)
                await client.disconnect()
                continue
            
            me = await client.get_me()
            cprint(f"✅ @{me.username or me.first_name}", Colors.SUCCESS)
            cprint(f"📋 Чатов для рассылки: {len(acc_chats)}", Colors.INFO)
            
            # Запуск рассылки
            stats = await broadcast_with_account(
                client, acc, acc_chats, text, photo_path, min_delay, max_delay, start_from=0
            )
            
            cprint(f"\n✅ Завершил: {stats['sent']}/{len(acc_chats)}", Colors.SUCCESS)
            
            # Итог
            total_stats['total'] += stats['total']
            total_stats['sent'] += stats['sent']
            total_stats['failed'] += stats['failed']
            total_stats['errors'].extend(stats['errors'][:5])
            
        except Exception as e:
            cprint(f"❌ Ошибка: {type(e).__name__}: {e}", Colors.ERROR)
            import traceback
            traceback.print_exc()
        finally:
            try:
                await client.disconnect()
                cprint("📴 Отключено", Colors.INFO)
            except:
                pass
    
    # 6. Отчёт
    end_time = datetime.now()
    duration = end_time - start_time
    
    header("📊 ОТЧЁТ О РАССЫЛКЕ")
    cprint(f"  ⏱ Время:         {duration}", Colors.CYAN)
    cprint(f"  📋 Чатов всего:   {total_stats['total']}", Colors.CYAN)
    cprint(f"  ✅ Успешно:       {total_stats['sent']}", Colors.GREEN)
    cprint(f"  ❌ Ошибки:        {total_stats['failed']}", Colors.RED)
    
    if total_stats['total'] > 0:
        rate = total_stats['sent'] / total_stats['total'] * 100
        cprint(f"  📈 Процент:       {rate:.1f}%", Colors.CYAN)
    
    if total_stats['errors']:
        cprint(f"\n  ⚠ Ошибки ({len(total_stats['errors'])}):", Colors.WARNING)
        for err in total_stats['errors'][:10]:
            cprint(f"    - {err.get('chat', 'Unknown')}: {err.get('error', 'Unknown')}", Colors.YELLOW)
    
    header("✅ РАССЫЛКА ЗАВЕРШЕНА")


if __name__ == '__main__':
    try:
        asyncio.run(run_broadcast())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠ Прервано пользователем{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.ERROR}❌ Критическая ошибка: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
