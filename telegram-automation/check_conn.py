from telethon.network import connection
print("Connection classes:")
for name in dir(connection):
    if not name.startswith('_'):
        print(f"  - {name}")

# Попробуем импортировать
try:
    from telethon.network.connection.http import ConnectionHttp
    print("\n✓ http.ConnectionHttp доступен")
except ImportError as e:
    print(f"\n✗ http.ConnectionHttp: {e}")

try:
    from telethon.network.connection.connection import ConnectionHttp
    print("✓ connection.ConnectionHttp доступен")
except ImportError as e:
    print(f"✗ connection.ConnectionHttp: {e}")
