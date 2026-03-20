"""
Multi-Account Broadcaster
Параллельная рассылка с распределением чатов
"""

import asyncio
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from telethon import TelegramClient
from telethon.errors import FloodWaitError

from .config import AccountConfig, Config
from .manager import AccountManager


class BroadcasterStats:
    """Статистика рассылки"""
    
    def __init__(self):
        self.total_chats = 0
        self.sent = 0
        self.failed = 0
        self.errors = []
        self.start_time = None
        self.end_time = None
        self.account_stats = {}
    
    def to_dict(self) -> Dict:
        duration = (self.end_time - self.start_time) if self.end_time and self.start_time else None
        return {
            'total_chats': self.total_chats,
            'sent': self.sent,
            'failed': self.failed,
            'success_rate': f"{(self.sent / self.total_chats * 100):.1f}%" if self.total_chats else 0,
            'duration': str(duration).split('.')[0] if duration else None,
            'accounts': self.account_stats,
            'errors': self.errors[:20]  # Первые 20 ошибок
        }


class AccountBroadcaster:
    """Рассылка для одного аккаунта"""
    
    def __init__(self, account: AccountConfig, client: TelegramClient):
        self.account = account
        self.client = client
        self.stats = {
            'sent': 0,
            'failed': 0,
            'errors': []
        }
    
    async def send_message(
        self, 
        chat_id: str, 
        text: str, 
        photo_path: Optional[Path] = None,
        forward_from_msg_id: Optional[int] = None
    ) -> bool:
        """
        Отправить сообщение
        
        Args:
            chat_id: ID чата
            text: Текст сообщения
            photo_path: Путь к фото (если есть)
            forward_from_msg_id: ID сообщения для пересылки (из избранного)
        
        Returns:
            True если успешно
        """
        limits = self.account.limits
        
        try:
            # Отправляем текст
            await self.client.send_message(chat_id, text)
            
            # Отправляем фото (если есть путь)
            if photo_path and photo_path.exists():
                await self.client.send_file(chat_id, photo_path)
            
            # ИЛИ пересылаем из избранного (если указан msg_id)
            elif forward_from_msg_id:
                await self.client.forward_messages(chat_id, forward_from_msg_id, from_peer='me')
            
            self.stats['sent'] += 1
            return True
        
        except FloodWaitError as e:
            wait_time = e.seconds
            self.stats['errors'].append({
                'chat': chat_id,
                'error': f'FloodWait {wait_time} сек',
                'type': 'flood'
            })
            
            # Ждём и пробуем снова
            await asyncio.sleep(wait_time)
            try:
                await self.client.send_message(chat_id, text)
                self.stats['sent'] += 1
                return True
            except Exception:
                self.stats['failed'] += 1
                return False
        
        except Exception as e:
            self.stats['failed'] += 1
            self.stats['errors'].append({
                'chat': chat_id,
                'error': f'{type(e).__name__}: {str(e)[:100]}',
                'type': 'error'
            })
            return False
    
    async def broadcast(
        self,
        chats: List[Dict],
        text: str,
        photo_path: Optional[Path] = None,
        forward_from_msg_id: Optional[int] = None
    ) -> Dict:
        """
        Рассылка по списку чатов
        
        Args:
            chats: Список чатов
            text: Текст сообщения
            photo_path: Путь к фото
            forward_from_msg_id: ID сообщения для пересылки
        
        Returns:
            Статистика рассылки
        """
        min_delay = self.account.limits['min_delay']
        max_delay = self.account.limits['max_delay']
        
        for i, chat in enumerate(chats, 1):
            chat_id = chat['id']
            chat_name = chat.get('name', chat_id)
            
            success = await self.send_message(
                chat_id, 
                text, 
                photo_path, 
                forward_from_msg_id
            )
            
            status = "✓" if success else "✗"
            print(f"  [{i}/{len(chats)}] {status} {chat_name}")
            
            # Задержка между сообщениями
            if i < len(chats):
                delay = random.randint(min_delay, max_delay)
                mins, secs = divmod(delay, 60)
                print(f"\r      Пауза: {mins:02d}:{secs:02d}  ", end='', flush=True)
                await asyncio.sleep(delay)
                print()
        
        return self.stats


class MultiAccountBroadcaster:
    """Мультиаккаунтная рассылка"""
    
    def __init__(self):
        self.manager = AccountManager()
        self.global_stats = BroadcasterStats()
    
    async def run_broadcast(
        self,
        distribute_strategy: str = 'balanced',
        use_photo: bool = True
    ) -> Dict:
        """
        Запустить параллельную рассылку
        
        Args:
            distribute_strategy: 'balanced' или 'weighted'
            use_photo: Использовать фото или нет
        
        Returns:
            Общая статистика
        """
        self.global_stats.start_time = datetime.now()
        
        # Загружаем аккаунты
        self.manager.load_accounts()
        ready_accounts = self.manager.get_ready_accounts()
        
        if not ready_accounts:
            print("Нет готовых аккаунтов!")
            return self.global_stats.to_dict()
        
        # Подключаем все аккаунты
        print("\nПодключение аккаунтов...")
        results = await self.manager.connect_all()
        
        for acc_id, (success, message) in results.items():
            status = "✓" if success else "✗"
            print(f"  {status} Аккаунт {acc_id}: {message}")
        
        # Загружаем чаты
        chats = Config.get_chats()
        if not chats:
            print("Чаты пусты!")
            return self.global_stats.to_dict()
        
        self.global_stats.total_chats = len(chats)
        
        # Распределяем чаты
        distribution = self.manager.distribute_chats(chats, distribute_strategy)
        
        print(f"\nРаспределение чатов ({len(chats)} всего):")
        for acc_id, acc_chats in distribution.items():
            acc = next((a for a in ready_accounts if a.id == acc_id), None)
            if acc:
                print(f"  {acc.name}: {len(acc_chats)} чатов")
        
        # Запускаем рассылку параллельно
        tasks = []
        for acc_id, acc_chats in distribution.items():
            client = self.manager.get_client(acc_id)
            account = next((a for a in ready_accounts if a.id == acc_id), None)
            
            if client and account and acc_chats:
                tasks.append(
                    self._broadcast_for_account(
                        account, 
                        client, 
                        acc_chats,
                        use_photo
                    )
                )
        
        # Ждём завершения всех задач
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Собираем статистику
        for result in results:
            if isinstance(result, dict):
                self.global_stats.sent += result.get('sent', 0)
                self.global_stats.failed += result.get('failed', 0)
                self.global_stats.errors.extend(result.get('errors', []))
        
        self.global_stats.end_time = datetime.now()
        
        # Вывод отчёта
        self._print_report()
        
        # Отключаем аккаунты
        await self.manager.disconnect_all()
        
        return self.global_stats.to_dict()
    
    async def _broadcast_for_account(
        self,
        account: AccountConfig,
        client: TelegramClient,
        chats: List[Dict],
        use_photo: bool
    ) -> Dict:
        """Рассылка для одного аккаунта"""
        
        me = await client.get_me()
        account_name = f"@{me.username or me.first_name}"
        
        print(f"\n{'=' * 40}")
        print(f"Аккаунт {account.name} ({account_name})")
        print(f"Чатов: {len(chats)}")
        print(f"{'=' * 40}")
        
        # Получаем текст
        text = account.get_text()
        if not text:
            print("  Текст не настроен! Пропускаем...")
            return {'sent': 0, 'failed': len(chats), 'errors': []}
        
        # Получаем фото
        photo_path = None
        if use_photo:
            photo_path = account.get_photo_path()
        
        # Получаем msg_id для пересылки из избранного
        forward_from_msg_id = None
        if not photo_path:
            # Пробуем получить последнее сообщение из избранного
            try:
                async for msg in client.iter_messages('me', limit=1):
                    forward_from_msg_id = msg.id
                    break
            except Exception:
                pass
        
        # Запускаем рассылку
        broadcaster = AccountBroadcaster(account, client)
        stats = await broadcaster.broadcast(
            chats,
            text,
            photo_path,
            forward_from_msg_id
        )
        
        # Сохраняем в глобальную статистику
        self.global_stats.account_stats[account.id] = {
            'name': account.name,
            'username': account_name,
            'chats': len(chats),
            **stats
        }
        
        print(f"\n✓ Аккаунт {account_name} завершил: {stats['sent']}/{len(chats)}")
        
        return stats
    
    def _print_report(self):
        """Вывод итогового отчёта"""
        stats = self.global_stats.to_dict()
        
        print("\n" + "=" * 60)
        print("ИТОГОВЫЙ ОТЧЁТ")
        print("=" * 60)
        print(f"  Всего чатов:    {stats['total_chats']}")
        print(f"  Успешно:        {stats['sent']}")
        print(f"  Ошибки:         {stats['failed']}")
        print(f"  Процент:        {stats['success_rate']}")
        if stats['duration']:
            print(f"  Время:          {stats['duration']}")
        
        if stats['accounts']:
            print("\nПо аккаунтам:")
            for acc_id, acc_stats in stats['accounts'].items():
                print(f"  {acc_stats['name']} ({acc_stats['username']}):")
                print(f"    Чатов: {acc_stats['chats']}, Успешно: {acc_stats['sent']}, Ошибки: {acc_stats['failed']}")
        
        if stats['errors']:
            print(f"\nОшибки ({len(stats['errors'])}):")
            for err in stats['errors'][:10]:
                print(f"  - {err['chat']}: {err['error']}")
