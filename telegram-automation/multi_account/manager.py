"""
Multi-Account Manager
Управление сессиями и аккаунтами
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError

from .config import AccountConfig, Config


class AccountManager:
    """Менеджер аккаунтов Telegram"""
    
    def __init__(self):
        self.accounts: List[AccountConfig] = []
        self.clients: Dict[int, TelegramClient] = {}
        self.account_states: Dict[int, Dict] = {}
    
    def load_accounts(self) -> List[AccountConfig]:
        """Загрузить и инициализировать аккаунты"""
        self.accounts = [
            AccountConfig(acc) 
            for acc in Config.get_enabled_accounts()
        ]
        return self.accounts
    
    def get_ready_accounts(self) -> List[AccountConfig]:
        """Получить готовые к работе аккаунты"""
        return [acc for acc in self.accounts if acc.is_ready()]
    
    async def connect_account(self, account: AccountConfig) -> Tuple[bool, str]:
        """
        Подключить аккаунт
        
        Returns:
            (success: bool, message: str)
        """
        try:
            client = TelegramClient(
                str(account.session_path),
                account.api_id,
                account.api_hash
            )
            
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "Не авторизован"
            
            me = await client.get_me()
            self.clients[account.id] = client
            
            # Сохраняем состояние
            self.account_states[account.id] = {
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'phone': account.phone,
                'connected': True,
                'sent_count': 0,
                'error_count': 0
            }
            
            return True, f"@{me.username or me.first_name}"
        
        except Exception as e:
            return False, str(e)
    
    async def connect_all(self) -> Dict[int, Tuple[bool, str]]:
        """
        Подключить все аккаунты
        
        Returns:
            Dict[account_id, (success, message)]
        """
        results = {}
        
        connect_tasks = {
            acc.id: self.connect_account(acc) 
            for acc in self.get_ready_accounts()
        }
        
        completed = await asyncio.gather(*connect_tasks.values(), return_exceptions=True)
        
        for (acc_id, _), result in zip(connect_tasks.items(), completed):
            if isinstance(result, Exception):
                results[acc_id] = (False, str(result))
            else:
                results[acc_id] = result
        
        return results
    
    async def disconnect_account(self, account_id: int):
        """Отключить аккаунт"""
        if account_id in self.clients:
            await self.clients[account_id].disconnect()
            del self.clients[account_id]
            
            if account_id in self.account_states:
                self.account_states[account_id]['connected'] = False
    
    async def disconnect_all(self):
        """Отключить все аккаунты"""
        for account_id in list(self.clients.keys()):
            await self.disconnect_account(account_id)
    
    def get_client(self, account_id: int) -> Optional[TelegramClient]:
        """Получить клиента аккаунта"""
        return self.clients.get(account_id)
    
    def get_state(self, account_id: int) -> Optional[Dict]:
        """Получить состояние аккаунта"""
        return self.account_states.get(account_id)
    
    def get_all_states(self) -> List[Dict]:
        """Получить состояния всех аккаунтов"""
        return [
            {
                'id': acc.id,
                'name': acc.name,
                **self.account_states.get(acc.id, {})
            }
            for acc in self.accounts
        ]
    
    def increment_sent(self, account_id: int):
        """Увеличить счётчик отправленных"""
        if account_id in self.account_states:
            self.account_states[account_id]['sent_count'] += 1
    
    def increment_errors(self, account_id: int):
        """Увеличить счётчик ошибок"""
        if account_id in self.account_states:
            self.account_states[account_id]['error_count'] += 1
    
    async def auth_account(self, account: AccountConfig, code: str, password: str = None) -> Tuple[bool, str]:
        """
        Авторизовать аккаунт
        
        Args:
            account: Конфигурация аккаунта
            code: Код из Telegram
            password: 2FA пароль (если нужен)
        
        Returns:
            (success: bool, message: str)
        """
        try:
            client = TelegramClient(
                str(account.session_path),
                account.api_id,
                account.api_hash
            )
            
            await client.connect()
            
            # Отправляем код
            await client.send_code_request(account.phone)
            
            # Вводим код
            try:
                await client.sign_in(phone=account.phone, code=code)
            except SessionPasswordNeededError:
                if not password:
                    return False, "Нужен 2FA пароль"
                await client.sign_in(password=password)
            
            me = await client.get_me()
            self.clients[account.id] = client
            
            self.account_states[account.id] = {
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'phone': account.phone,
                'connected': True,
                'sent_count': 0,
                'error_count': 0
            }
            
            return True, f"@{me.username or me.first_name}"
        
        except FloodWaitError as e:
            return False, f"FloodWait: {e.seconds} сек"
        except Exception as e:
            return False, str(e)
    
    def distribute_chats(self, chats: List[Dict], strategy: str = 'balanced') -> Dict[int, List[Dict]]:
        """
        Распределить чаты между аккаунтами
        
        Args:
            chats: Список чатов
            strategy: 'balanced' (поровну) или 'weighted' (по лимитам)
        
        Returns:
            Dict[account_id, List[chats]]
        """
        ready_accounts = self.get_ready_accounts()
        
        if not ready_accounts:
            return {}
        
        if strategy == 'balanced':
            # Равномерное распределение
            chats_per_account = len(chats) // len(ready_accounts)
            distribution = {}
            
            for i, acc in enumerate(ready_accounts):
                start = i * chats_per_account
                end = start + chats_per_account if i < len(ready_accounts) - 1 else len(chats)
                distribution[acc.id] = chats[start:end]
            
            return distribution
        
        elif strategy == 'weighted':
            # Распределение по лимитам
            total_limit = sum(
                acc.limits.get('daily_limit', 500) 
                for acc in ready_accounts
            )
            
            distribution = {}
            chat_index = 0
            
            for acc in ready_accounts:
                acc_limit = acc.limits.get('daily_limit', 500)
                acc_share = int(len(chats) * acc_limit / total_limit)
                
                distribution[acc.id] = chats[chat_index:chat_index + acc_share]
                chat_index += acc_share
            
            # Остаток последнему аккаунту
            if chat_index < len(chats):
                last_acc = ready_accounts[-1]
                distribution[last_acc].extend(chats[chat_index:])
            
            return distribution
        
        return {}
