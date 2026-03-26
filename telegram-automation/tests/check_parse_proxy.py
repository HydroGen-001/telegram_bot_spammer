from telethon.network.connection.connection import Connection
import inspect

# Смотрим исходный код _parse_proxy
src = inspect.getsource(Connection._parse_proxy)
print("Исходный код _parse_proxy:")
print(src[:2000])
