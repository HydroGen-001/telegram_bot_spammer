"""Тест импортов multi_account"""

from multi_account import Config, AccountManager, MultiAccountBroadcaster

print("✓ Все импорты работают!")

# Тест загрузки конфигурации
data = Config.load_accounts()
print(f"✓ accounts.json загружен: {len(data.get('accounts', []))} аккаунтов")

# Тест загрузки чатов
chats = Config.get_chats()
print(f"✓ chats.json загружен: {len(chats)} чатов")

# Тест загрузки шаблонов
templates = Config.get_templates()
print(f"✓ templates.json загружен: {len(templates.get('templates', []))} шаблонов")

print("\n✓ Все тесты пройдены!")
