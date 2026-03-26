"""
Chat Join Manager
Управление вступлением аккаунтов в чаты
"""

import asyncio
import random
from typing import Dict, List, Optional, Tuple
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest, InviteToChannelRequest
from telethon.tl.types import InputPeerChannel


class ChatJoinManager:
    """Менеджер вступления в чаты"""

    def __init__(self):
        self.clients: Dict[int, TelegramClient] = {}
        self.join_stats: Dict[int, Dict] = {}

    async def add_client(self, account_id: int, client: TelegramClient):
        """Добавить клиента аккаунта"""
        self.clients[account_id] = client
        self.join_stats[account_id] = {
            'joined': 0,
            'already': 0,
            'failed': 0,
            'errors': []
        }

    async def check_membership(self, client: TelegramClient, chat_id: str) -> Tuple[bool, str]:
        """
        Проверить, состоит ли аккаунт в чате

        Returns:
            (is_member: bool, error: str)
        """
        try:
            # Пытаемся получить информацию о чате
            entity = await client.get_entity(chat_id)
            return True, ""
        except ValueError:
            # Чат не найден
            return False, "Чат не найден"
        except Exception as e:
            error_name = type(e).__name__
            if 'ChannelPrivate' in error_name:
                return False, "Частный канал"
            elif 'UserNotParticipant' in error_name:
                return False, "Не состоит"
            else:
                return False, str(e)

    async def join_chat(self, client: TelegramClient, chat_id: str, chat_name: str) -> Tuple[bool, str]:
        """
        Вступить в чат

        Returns:
            (success: bool, message: str)
        """
        try:
            # Проверяем, не состоим ли уже
            is_member, error = await self.check_membership(client, chat_id)
            if is_member:
                return True, "Уже в чате"

            # Пытаемся вступить
            entity = await client.get_entity(chat_id)
            await client(JoinChannelRequest(entity))

            return True, "Вступил"

        except UserAlreadyParticipantError:
            return True, "Уже в чате"
        except FloodWaitError as e:
            return False, f"FloodWait: {e.seconds} сек"
        except ValueError:
            return False, "Чат не найден"
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)[:50]}"

    async def join_chats_for_account(
        self,
        account_id: int,
        chats: List[Dict],
        max_join_per_session: int = 50,
        delay_between_joins: Tuple[int, int] = (30, 60),
        delay_already_member: Tuple[int, int] = (5, 15)
    ) -> Dict:
        """
        Вступить в чаты для одного аккаунта

        Args:
            account_id: ID аккаунта
            chats: Список чатов для вступления
            max_join_per_session: Максимум вступлений за сессию
            delay_between_joins: Задержка после вступления (мин, макс)
            delay_already_member: Задержка если уже в чате (мин, макс)

        Returns:
            Статистика вступлений
        """
        if account_id not in self.clients:
            return {'error': 'Аккаунт не подключён'}

        client = self.clients[account_id]
        stats = self.join_stats[account_id]

        print(f"\n  Вступление в чаты (макс. {max_join_per_session})...")

        joined_count = 0

        for i, chat in enumerate(chats):
            if joined_count >= max_join_per_session:
                print(f"  ⚠ Достигнут лимит вступлений ({max_join_per_session})")
                break

            chat_id = chat.get('id')
            chat_name = chat.get('name', chat_id)

            # Проверка членства
            is_member, error = await self.check_membership(client, chat_id)

            if is_member:
                stats['already'] += 1
                print(f"  [{i+1}/{len(chats)}] ✓ Уже в чате: {chat_name}")
                continue

            # Вступление
            success, message = await self.join_chat(client, chat_id, chat_name)

            if success:
                stats['joined'] += 1
                joined_count += 1
                print(f"  [{i+1}/{len(chats)}] ✓ {message}: {chat_name}")
            else:
                stats['failed'] += 1
                stats['errors'].append({'chat': chat_name, 'error': message})
                print(f"  [{i+1}/{len(chats)}] ✗ {message}: {chat_name}")

            # Задержка после каждого чата
            if i < len(chats) - 1 and joined_count < max_join_per_session:
                # Если уже был в чате — короткая задержка, иначе — длинная
                if is_member:
                    delay = random.randint(delay_already_member[0], delay_already_member[1])
                else:
                    delay = random.randint(delay_between_joins[0], delay_between_joins[1])
                
                mins, secs = divmod(delay, 60)
                print(f"\r      Пауза: {mins:02d}:{secs:02d}  ", end='', flush=True)
                await asyncio.sleep(delay)
                print()

        return stats

    async def distribute_and_join(
        self,
        accounts: List[Dict],
        chats: List[Dict],
        chats_per_account: int = 50
    ) -> Dict[int, List[Dict]]:
        """
        Распределить чаты между аккаунтами и вступить

        Args:
            accounts: Список аккаунтов
            chats: Список чатов
            chats_per_account: Сколько чатов на аккаунт

        Returns:
            Распределение чатов
        """
        distribution = {}
        chat_index = 0

        print(f"\nРаспределение {len(chats)} чатов между {len(accounts)} аккаунтами...")
        print(f"По {chats_per_account} чатов на аккаунт\n")

        for acc in accounts:
            acc_id = acc.get('id')
            acc_name = acc.get('name', f'Аккаунт {acc_id}')

            start = chat_index
            end = min(chat_index + chats_per_account, len(chats))
            acc_chats = chats[start:end]

            distribution[acc_id] = acc_chats
            chat_index = end

            print(f"  {acc_name}: {len(acc_chats)} чатов")

            if chat_index >= len(chats):
                break

        # Остаток
        if chat_index < len(chats):
            remaining = len(chats) - chat_index
            print(f"\n  ⚠ Осталось {remaining} чатов без аккаунтов")

        return distribution

    def get_stats(self, account_id: int) -> Dict:
        """Получить статистику аккаунта"""
        return self.join_stats.get(account_id, {})

    def get_all_stats(self) -> Dict:
        """Получить статистику всех аккаунтов"""
        return self.join_stats

    async def disconnect_all(self):
        """Отключить все клиенты"""
        for client in self.clients.values():
            try:
                await client.disconnect()
            except:
                pass
        self.clients.clear()
