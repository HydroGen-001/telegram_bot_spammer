# 🔌 ProxyManager — Проксирование в мультиаккаунтах

**Путь:** `multi_account/proxy_manager.py`

---

## 📌 Назначение

Модуль для управления прокси в мультиаккаунтной рассылке **без изменения существующих файлов** (`manager.py`, `broadcaster.py`).

---

## 🚀 Быстрый старт

### Вариант 1: Через ProxyManager (класс)

```python
from multi_account import ProxyManager, AccountConfig

# Создаём менеджер
proxy_manager = ProxyManager()

# Создаём конфигурацию аккаунта
account = AccountConfig({
    'id': 1,
    'name': 'Аккаунт 1',
    'session_name': 'userbot',
    'api_id': 26680307,
    'api_hash': '11fe6a7625e5c368e494c40f29066de0',
    'phone': '+79124922318',
    'proxy': {
        'enabled': True,
        'host': 'mobpool.proxy.market',
        'port': 10000,
        'username': 'user',
        'password': 'pass'
    }
})

# Создаём клиента с прокси
client = proxy_manager.create_client_with_proxy(account)

# Подключаем
async with client:
    await client.connect()
    me = await client.get_me()
    print(f"Подключено: {me.first_name}")
```

---

### Вариант 2: Через функции (проще)

```python
from multi_account import create_client_with_proxy, connect_account_with_proxy

# Создаём клиента с прокси
client = create_client_with_proxy(account_config)

# Подключаем
success, message = await connect_account_with_proxy(account_config)

if success:
    print(f"✓ {message}")
else:
    print(f"✗ {message}")
```

---

## 📋 API

### Класс `ProxyManager`

#### Методы:

| Метод | Описание |
|-------|----------|
| `create_client_with_proxy(account)` | Создать клиента с прокси |
| `connect_account(account)` | Подключить аккаунт с прокси |
| `connect_all_accounts(accounts)` | Подключить все аккаунты |
| `get_client(account_id)` | Получить клиента |
| `get_proxy_state(account_id)` | Получить состояние прокси |
| `disconnect_account(account_id)` | Отключить аккаунт |
| `disconnect_all()` | Отключить все аккаунты |
| `get_proxy_info_string(account_id)` | Строка с инфо о прокси |

---

### Функции (для совместимости)

| Функция | Описание |
|---------|----------|
| `create_client_with_proxy(account)` | Создать клиента с прокси |
| `connect_account_with_proxy(account)` | Подключить аккаунт с прокси |

---

## 🔧 Конфигурация прокси

### Формат в `accounts.json`:

```json
{
  "accounts": [
    {
      "id": 1,
      "name": "Аккаунт 1",
      "session_name": "userbot",
      "api_id": 26680307,
      "api_hash": "11fe6a7625e5c368e494c40f29066de0",
      "phone": "+79124922318",

      "proxy": {
        "enabled": true,
        "host": "mobpool.proxy.market",
        "port": 10000,
        "username": "rTtqcDc4t0Kg",
        "password": "wkLYa1bq"
      }
    }
  ]
}
```

### Поля:

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| `enabled` | bool | Да | Включить прокси |
| `host` | str | Да | Хост прокси (домен или IP) |
| `port` | int | Да | Порт прокси |
| `username` | str | Нет | Логин для авторизации |
| `password` | str | Нет | Пароль для авторизации |

---

## 📊 Примеры использования

### Пример 1: Подключение одного аккаунта

```python
import asyncio
from multi_account import Config, ProxyManager

async def main():
    # Загружаем аккаунты
    accounts = Config.get_enabled_accounts()
    account = accounts[0]  # Берём первый

    # Создаём менеджер
    proxy_manager = ProxyManager()

    # Создаём клиента с прокси
    client = proxy_manager.create_client_with_proxy(account)

    # Подключаем
    await client.connect()

    # Проверяем прокси
    state = proxy_manager.get_proxy_state(account['id'])
    if state.get('enabled'):
        print(f"✓ Прокси: {state['host']} → {state['ip']}:{state['port']}")

    # Работаем с клиентом
    me = await client.get_me()
    print(f"Аккаунт: {me.first_name}")

    # Отключаем
    await client.disconnect()

asyncio.run(main())
```

---

### Пример 2: Подключение всех аккаунтов

```python
import asyncio
from multi_account import Config, ProxyManager

async def main():
    accounts = Config.get_enabled_accounts()
    proxy_manager = ProxyManager()

    # Подключаем все аккаунты параллельно
    results = await proxy_manager.connect_all_accounts(accounts)

    # Выводим результаты
    for acc_id, (success, message, proxy_info) in results.items():
        if success:
            print(f"✓ Аккаунт {acc_id}: {message}")
            print(f"  Прокси: {proxy_info.get('host')} → {proxy_info.get('ip')}")
        else:
            print(f"✗ Аккаунт {acc_id}: {message}")

    # Отключаем все
    await proxy_manager.disconnect_all()

asyncio.run(main())
```

---

### Пример 3: Интеграция с `AccountManager`

```python
from multi_account import AccountManager, ProxyManager

class AccountManagerWithProxy(AccountManager):
    """AccountManager с поддержкой прокси"""

    def __init__(self):
        super().__init__()
        self.proxy_manager = ProxyManager()

    async def connect_account(self, account):
        """Подключить аккаунт с прокси"""
        # Создаём клиента с прокси вместо обычного
        client = self.proxy_manager.create_client_with_proxy(account)

        # Подключаем
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return False, "Не авторизован"

        me = await client.get_me()
        self.clients[account.id] = client

        # Сохраняем состояние с инфо о прокси
        proxy_state = self.proxy_manager.get_proxy_state(account.id)
        self.account_states[account.id] = {
            'username': me.username,
            'first_name': me.first_name,
            'proxy': proxy_state,
            'connected': True
        }

        return True, f"@{me.username or me.first_name}"
```

---

## 🧪 Тестирование

### Запуск теста:

```bash
python tests/test_multi_account_proxy.py
```

### Меню теста:

```
1. Тестировать все аккаунты
2. Тестировать один аккаунт
3. Показать конфигурацию аккаунтов
0. Выход
```

---

## 🔍 Проверка работоспособности

### Чек-лист:

- [ ] Прокси настроен в `accounts.json`
- [ ] `proxy.enabled = true`
- [ ] `proxy.host` и `proxy.port` заполнены
- [ ] Сессия существует в `sessions/`
- [ ] API credentials заполнены

### Ошибки:

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `proxy_host not found` | DNS не резолвится | Проверьте домен прокси |
| `Not authorized` | Нет сессии | Запустите авторизацию |
| `Connection refused` | Прокси недоступен | Проверьте порт/файрвол |
| `FloodWait` | Блокировка Telegram | Подождите указанное время |

---

## 📁 Структура модуля

```
multi_account/
├── proxy_manager.py          # Новый модуль проксирования
├── __init__.py               # Экспорт (обновлён)
├── config.py                 # Конфигурация (без изменений)
├── manager.py                # Менеджер (без изменений)
└── broadcaster.py            # Рассылка (без изменений)
```

---

## 🎯 Преимущества

| Преимущество | Описание |
|--------------|----------|
| ✅ Без изменений | Существующие файлы не тронуты |
| ✅ Совместимость | Работает со старым кодом |
| ✅ Гибкость | Можно использовать частично |
| ✅ Тестирование | Отдельный скрипт для проверки |
| ✅ Прозрачность | Видно состояние каждого прокси |

---

## 📝 Интеграция в `multi_account_start.py`

Для использования в главном меню мультиаккаунтов:

```python
from multi_account import ProxyManager

# В функции подключения аккаунта:
proxy_manager = ProxyManager()
client = proxy_manager.create_client_with_proxy(account_config)

await client.connect()
# ... остальной код
```

---

## 🔗 Ссылки

- `multi_account/proxy_manager.py` — исходный код
- `tests/test_multi_account_proxy.py` — тесты
- `accounts.json` — конфигурация аккаунтов

---

**Готово!** Теперь мультиаккаунты поддерживают проксирование без изменения основных файлов! 🎉
