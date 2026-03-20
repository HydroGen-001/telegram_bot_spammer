"""
Сбор чатов Telegram
Единый модуль для сбора и экспорта чатов
"""

import asyncio
import json
import sys
import io
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict

from telethon import TelegramClient
from telethon.tl.types import Chat, Channel, User


@dataclass
class ChatInfo:
    """Информация о чате"""
    id: str
    name: str
    type: str  # 'channel' или 'chat'
    enabled: bool = True
    
    @classmethod
    def from_entity(cls, entity: Union[Chat, Channel]) -> 'ChatInfo':
        """Создать из Telegram entity"""
        # Определение ID
        if hasattr(entity, 'username') and entity.username:
            chat_id = entity.username
        else:
            chat_id = str(entity.id)
        
        # Определение названия
        title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
        
        # Определение типа
        chat_type = "channel" if isinstance(entity, Channel) else "chat"
        
        return cls(id=chat_id, name=title, type=chat_type)
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в dict"""
        return asdict(self)


class ChatCollector:
    """
    Сборщик чатов Telegram
    
    Функции:
    - Сбор всех чатов из аккаунта
    - Фильтрация по типу
    - Сохранение в JSON
    - Загрузка из JSON
    """

    def __init__(self, client: TelegramClient):
        self.client = client
        self._chats: List[ChatInfo] = []

    def _setup_console(self):
        """Настройка консоли для Windows"""
        if sys.platform == 'win32':
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )

    async def collect(
        self,
        exclude_users: bool = True,
        exclude_disabled: bool = False
    ) -> List[ChatInfo]:
        """
        Собрать все чаты
        
        Args:
            exclude_users: Исключить личные сообщения
            exclude_disabled: Исключить отключённые чаты
            
        Returns:
            Список чатов
        """
        self._chats = []
        excluded_count = 0

        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity

            # Пропуск личных сообщений
            if exclude_users and isinstance(entity, User):
                excluded_count += 1
                continue

            # Сбор только чатов и каналов
            if isinstance(entity, (Chat, Channel)):
                chat_info = ChatInfo.from_entity(entity)
                self._chats.append(chat_info)

        # Сортировка по названию
        self._chats.sort(key=lambda x: x.name.lower())

        return self._chats

    def save_to_file(
        self,
        output_path: Union[str, Path],
        include_metadata: bool = True
    ) -> Path:
        """
        Сохранить чаты в JSON файл
        
        Args:
            output_path: Путь к файлу
            include_metadata: Включить метаданные (версия, комментарий)
            
        Returns:
            Путь к сохранённому файлу
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "chats": [chat.to_dict() for chat in self._chats]
        }

        if include_metadata:
            metadata = {
                "_comment": "Список чатов для рассылки (автоматически собрано)",
                "_version": "1.0.0",
                "_total_found": len(self._chats),
                "_generated_by": "Telegram Automation System"
            }
            # Добавляем метаданные перед chats
            data_with_meta = {**metadata, **data}
            data = data_with_meta

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return output_path

    def load_from_file(self, file_path: Union[str, Path]) -> List[ChatInfo]:
        """
        Загрузить чаты из JSON файла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Список чатов
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        chats_data = data.get('chats', [])
        self._chats = [
            ChatInfo(
                id=c['id'],
                name=c['name'],
                type=c['type'],
                enabled=c.get('enabled', True)
            )
            for c in chats_data
        ]

        return self._chats

    def get_enabled_chats(self) -> List[ChatInfo]:
        """Получить только активные чаты"""
        return [c for c in self._chats if c.enabled]

    def get_disabled_chats(self) -> List[ChatInfo]:
        """Получить отключенные чаты"""
        return [c for c in self._chats if not c.enabled]

    def print_stats(self, limit: int = 20):
        """Вывести статистику в консоль"""
        self._setup_console()

        enabled = self.get_enabled_chats()
        disabled = self.get_disabled_chats()

        print("\n" + "=" * 60)
        print("СТАТИСТИКА ЧАТОВ")
        print("=" * 60)
        print()
        print(f"Всего чатов:    {len(self._chats)}")
        print(f"✅ Активных:    {len(enabled)}")
        print(f"❌ Отключено:   {len(disabled)}")
        print()

        if self._chats:
            print(f"Первые {min(limit, len(self._chats))} чатов:")
            for i, chat in enumerate(self._chats[:limit], 1):
                status = "[+]" if chat.enabled else "[-]"
                print(f"  {i}. {status} {chat.name} ({chat.id})")
            
            if len(self._chats) > limit:
                print(f"  ... и ещё {len(self._chats) - limit} чатов")
        print()

    @property
    def chats(self) -> List[ChatInfo]:
        """Получить все чаты"""
        return self._chats

    @property
    def count(self) -> int:
        """Получить количество чатов"""
        return len(self._chats)
