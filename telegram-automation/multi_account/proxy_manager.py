"""
Multi-Account Proxy Manager
Управление прокси для мультиаккаунтной рассылки

Использование:
    from multi_account import ProxyManager
    
    proxy_manager = ProxyManager()
    client = proxy_manager.create_client_with_proxy(account_config)
"""

import socket
from pathlib import Path
from typing import Dict, Optional, Tuple
from telethon import TelegramClient

from .config import AccountConfig, Config, SESSIONS_DIR


class ProxyManager:
    """Менеджер прокси для мультиаккаунтов"""

    def __init__(self):
        self.clients: Dict[int, TelegramClient] = {}
        self.proxy_states: Dict[int, Dict] = {}

    def create_client_with_proxy(
        self,
        account: AccountConfig
    ) -> TelegramClient:
        """
        Создать Telegram клиент с прокси

        Args:
            account: Конфигурация аккаунта

        Returns:
            TelegramClient с настроенным прокси (если включён)
        """
        # Создаём клиента
        client = TelegramClient(
            str(account.session_path),
            account.api_id,
            account.api_hash
        )

        # Настраиваем прокси если включено
        proxy_config = account.data.get('proxy', {})
        if proxy_config.get('enabled', False):
            self._setup_proxy(client, proxy_config, account.id)

        return client

    def _setup_proxy(
        self,
        client: TelegramClient,
        proxy_config: Dict,
        account_id: int
    ) -> bool:
        """
        Настроить прокси для клиента

        Args:
            client: Telegram клиент
            proxy_config: Конфигурация прокси
            account_id: ID аккаунта

        Returns:
            True если прокси настроено успешно
        """
        try:
            proxy_host = proxy_config.get('host', '')
            proxy_port = int(proxy_config.get('port', 0))
            proxy_username = proxy_config.get('username', '')
            proxy_password = proxy_config.get('password', '')

            if not proxy_host or not proxy_port:
                return False

            # Получаем актуальный IP (для мобильных прокси с ротацией)
            proxy_ip = socket.gethostbyname(proxy_host)

            # Создаём proxy_dict (правильный формат для Telethon 1.42+)
            proxy_dict = {
                'proxy_type': 'socks5',
                'addr': proxy_ip,
                'port': proxy_port,
            }

            # Добавляем авторизацию если есть
            if proxy_username and proxy_password:
                proxy_dict['username'] = proxy_username
                proxy_dict['password'] = proxy_password

            # Устанавливаем прокси
            client.set_proxy(proxy_dict)

            # Сохраняем состояние
            self.proxy_states[account_id] = {
                'host': proxy_host,
                'ip': proxy_ip,
                'port': proxy_port,
                'enabled': True
            }

            return True

        except Exception as e:
            # Сохраняем ошибку
            self.proxy_states[account_id] = {
                'enabled': False,
                'error': str(e)
            }
            return False

    async def connect_account(
        self,
        account: AccountConfig
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Подключить аккаунт с прокси

        Args:
            account: Конфигурация аккаунта

        Returns:
            (success: bool, message: str, proxy_info: dict)
        """
        try:
            # Создаём клиента с прокси
            client = self.create_client_with_proxy(account)

            # Подключаем
            await client.connect()

            # Проверяем авторизацию
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "Не авторизован", None

            # Получаем информацию о пользователе
            me = await client.get_me()

            # Сохраняем клиент
            self.clients[account.id] = client

            # Получаем информацию о прокси
            proxy_info = self.proxy_states.get(account.id, {})
            proxy_info['username'] = me.username
            proxy_info['first_name'] = me.first_name

            return True, f"@{me.username or me.first_name}", proxy_info

        except Exception as e:
            return False, str(e), None

    async def connect_all_accounts(
        self,
        accounts: list
    ) -> Dict[int, Tuple[bool, str, Optional[Dict]]]:
        """
        Подключить все аккаунты с прокси

        Args:
            accounts: Список AccountConfig

        Returns:
            Dict[account_id, (success, message, proxy_info)]
        """
        import asyncio

        results = {}

        # Создаём задачи для всех аккаунтов
        tasks = {
            acc.id: self.connect_account(acc)
            for acc in accounts
        }

        # Выполняем параллельно
        completed = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # Собираем результаты
        for (acc_id, _), result in zip(tasks.items(), completed):
            if isinstance(result, Exception):
                results[acc_id] = (False, str(result), None)
            else:
                results[acc_id] = result

        return results

    def get_client(self, account_id: int) -> Optional[TelegramClient]:
        """Получить клиента аккаунта"""
        return self.clients.get(account_id)

    def get_proxy_state(self, account_id: int) -> Optional[Dict]:
        """Получить состояние прокси аккаунта"""
        return self.proxy_states.get(account_id)

    async def disconnect_account(self, account_id: int):
        """Отключить аккаунт"""
        if account_id in self.clients:
            await self.clients[account_id].disconnect()
            del self.clients[account_id]

    async def disconnect_all(self):
        """Отключить все аккаунты"""
        for account_id in list(self.clients.keys()):
            await self.disconnect_account(account_id)

    def get_proxy_info_string(self, account_id: int) -> str:
        """
        Получить строку с информацией о прокси

        Returns:
            Строка вида "proxy_host → proxy_ip:port" или "Без прокси"
        """
        state = self.proxy_states.get(account_id)
        if not state:
            return "Без прокси"

        if not state.get('enabled'):
            return f"❌ Ошибка: {state.get('error', 'Неизвестная')}"

        return f"✓ {state.get('host')} → {state.get('ip')}:{state.get('port')}"


# =============================================================================
# ФУНКЦИИ ДЛЯ СОВМЕСТИМОСТИ СО СТАРЫМ КОДОМ
# =============================================================================

def create_client_with_proxy(account: AccountConfig) -> TelegramClient:
    """
    Создать клиент с прокси (функциональный интерфейс)

    Args:
        account: Конфигурация аккаунта

    Returns:
        TelegramClient
    """
    proxy_manager = ProxyManager()
    return proxy_manager.create_client_with_proxy(account)


async def connect_account_with_proxy(
    account: AccountConfig
) -> Tuple[bool, str]:
    """
    Подключить аккаунт с прокси (функциональный интерфейс)

    Args:
        account: Конфигурация аккаунта

    Returns:
        (success: bool, message: str)
    """
    proxy_manager = ProxyManager()
    success, message, _ = await proxy_manager.connect_account(account)
    return success, message
