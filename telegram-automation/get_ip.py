import socket
try:
    ip = socket.gethostbyname('mobpool.proxy.market')
    print(f"IP: {ip}")
except Exception as e:
    print(f"Ошибка: {e}")
