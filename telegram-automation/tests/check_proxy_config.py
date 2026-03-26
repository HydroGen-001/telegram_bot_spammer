from telethon.network.connection import connection
import inspect

# Ищем ProxyConfig
print("ProxyConfig:")
if hasattr(connection, 'ProxyConfig'):
    print(f"  Есть: {connection.ProxyConfig}")
    sig = inspect.signature(connection.ProxyConfig.__init__)
    for name, param in sig.parameters.items():
        print(f"    {name}: {param.default}")
else:
    print("  Не найден")

# Проверяем как парсится proxy
print("\n_parse_proxy:")
from telethon.network.connection.connection import Connection
if hasattr(Connection, '_parse_proxy'):
    print(f"  Есть: {Connection._parse_proxy}")
else:
    print("  Не найден")
