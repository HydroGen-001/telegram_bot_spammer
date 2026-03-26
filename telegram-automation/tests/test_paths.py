"""Проверка путей"""
from multi_account.config import TEMPLATES_PATH, CHATS_PATH, ACCOUNTS_PATH

print(f"TEMPLATES_PATH: {TEMPLATES_PATH}")
print(f"TEMPLATES_PATH.exists(): {TEMPLATES_PATH.exists()}")

print(f"\nCHATS_PATH: {CHATS_PATH}")
print(f"CHATS_PATH.exists(): {CHATS_PATH.exists()}")

print(f"\nACCOUNTS_PATH: {ACCOUNTS_PATH}")
print(f"ACCOUNTS_PATH.exists(): {ACCOUNTS_PATH.exists()}")
