"""
Telegram авторизация
"""

import asyncio
import os
from pathlib import Path
from typing import Optional, Tuple
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError
from telethon.tl.types import User

load_dotenv()


class TelegramAuth:
    """Менеджер авторизации Telegram"""

    def __init__(
        self,
        session_name: str = 'userbot',
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        phone: Optional[str] = None
    ):
        self.session_name = session_name
        self.session_path = Path('sessions') / session_name
        self.api_id = api_id or int(os.getenv('API_ID', '0'))
        self.api_hash = api_hash or os.getenv('API_HASH', '')
        self.phone = phone or os.getenv('PHONE', '')
        self._client: Optional[TelegramClient] = None

    def _input_text(self, prompt: str) -> Optional[str]:
        try:
            return input(prompt).strip()
        except EOFError:
            return None

    async def connect(self) -> TelegramClient:
        if self.api_id == 0 or not self.api_hash or not self.phone:
            raise ValueError("Заполните API_ID, API_HASH, PHONE в .env")

        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self._client = TelegramClient(str(self.session_path), self.api_id, self.api_hash)
        await self._client.connect()
        return self._client

    async def disconnect(self):
        if self._client:
            await self._client.disconnect()

    async def check_status(self) -> Tuple[bool, Optional[User]]:
        if not self._client:
            await self.connect()
        is_auth = await self._client.is_user_authorized()
        user = await self._client.get_me() if is_auth else None
        return is_auth, user

    async def authorize(self, force_sms: bool = False) -> Tuple[bool, str]:
        """Простая авторизация с кодом"""
        if not self._client:
            await self.connect()

        # Проверка существующей авторизации
        is_auth, user = await self.check_status()
        if is_auth:
            return True, f"Уже авторизовано: {user.first_name}"

        print("\n" + "=" * 60)
        print("АВТОРИЗАЦИЯ")
        print("=" * 60)
        print(f"\nТелефон: {self.phone}\n")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Отправка кода
                print(f"Попытка {attempt + 1}/{max_retries}")
                result = await self._client.send_code_request(self.phone)
                
                # Определяем тип отправки
                try:
                    # Проверяем тип кода (app, sms, call, flash_call)
                    code_type = type(result.type).__name__ if hasattr(result.type, '__class__') else str(result.type)
                    print(f"Код отправлен: {code_type}")
                except:
                    print("Код отправлен")
                
                print("\nПроверьте Telegram или SMS")
                print()

                code = self._input_text("Введите код: ")
                if not code:
                    print("❌ Код не введён\n")
                    continue

                # Вход
                try:
                    await self._client.sign_in(
                        self.phone,
                        code,
                        phone_code_hash=result.phone_code_hash
                    )
                except SessionPasswordNeededError:
                    print("\n🔐 Введён 2FA пароль")
                    password = self._input_text("Пароль: ")
                    if not password:
                        print("❌ Пароль не введён\n")
                        continue
                    await self._client.sign_in(password=password)

                # Успех
                user = await self._client.get_me()
                return True, f"Авторизовано: {user.first_name} (@{user.username or 'no username'})"

            except FloodWaitError as e:
                print(f"\n❌ FloodWait: ждите {e.seconds} сек")
                return False, f"FloodWait: {e.seconds}s"

            except PhoneCodeInvalidError:
                print("\n❌ Неверный код\n")

            except Exception as e:
                err_str = str(e)
                if "ResendCodeRequest" in err_str or "all available options" in err_str:
                    print(f"\n⚠️ Лимит запросов кода. Подождите 1 час.\n")
                    return False, "Лимит запросов кода"
                print(f"\n❌ Ошибка: {e}\n")

        return False, "Не удалось авторизоваться"

    @property
    def client(self) -> Optional[TelegramClient]:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected()
