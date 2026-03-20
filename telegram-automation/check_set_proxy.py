"""
Проверка set_proxy
"""

from telethon import TelegramClient
import inspect

client = TelegramClient('test', 123, 'abc')

# Проверяем set_proxy
print("set_proxy signature:")
print(inspect.signature(client.set_proxy))

print("\nset_proxy docstring:")
print(client.set_proxy.__doc__)

# Проверяем _proxy
print(f"\nclient._proxy: {client._proxy}")

# Пробуем установить через _proxy напрямую
client._proxy = ('socks5', '127.0.0.1', 1080, 'user', 'pass')
print(f"client._proxy после установки: {client._proxy}")
