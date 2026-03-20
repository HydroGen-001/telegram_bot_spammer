# Настройка прокси для Telegram Automation

## 📋 Содержание

1. [Зачем нужен прокси](#зачем-нужен-прокси)
2. [Где купить прокси](#где-купить-прокси)
3. [Настройка в скрипте](#настройка-в-скрипте)
4. [Проверка работы](#проверка-работы)
5. [Troubleshooting](#troubleshooting)

---

## 🔍 Зачем нужен прокси

**Проблема:** В России Telegram блокируется на уровне провайдеров (DPI-фильтрация, блокировка IP).

**Решение:** Мобильный прокси обходит блокировки:
- ✅ Стабильное соединение
- ✅ Меньше FloodWait
- ✅ Выше процент доставки

**Важно:** Для аккаунта из России → Россия/Индия/Индонезия прокси

---

## 🛒 Где купить прокси

### Рекомендуемые сервисы

| Сервис | Цена | Страна | Ссылка |
|--------|------|--------|--------|
| **Proxy6** | ~$5/мес | Индия | [proxy6.net](https://proxy6.net) |
| **Proxy-Seller** | ~$6/мес | Индия | [proxy-seller.com](https://proxy-seller.com) |
| **IPRoyal** | ~$4/мес | Индия | [iproyal.com](https://iproyal.com) |
| **SOAX** | ~$99/мес | Индия | [soax.com](https://soax.com) |

### Что искать при покупке

- **Тип:** Mobile (3G/4G/LTE) — НЕ datacenter!
- **Страна:** India (IN) или Indonesia (ID) или Russia (RU)
- **Протокол:** HTTP/HTTPS или SOCKS5 (оба работают)
- **Порт:** обычно 8080, 3128, 10000+
- **Трафик:** 2 GB хватит на 6+ месяцев

---

## ⚙️ Настройка в скрипте

### Шаг 1: Открой `.env`

```bash
notepad .env
```

### Шаг 2: Добавь данные прокси

После покупки ты получишь:
- Host/IP: `185.xxx.xxx.xxx` или `proxy.example.com`
- Port: `8080`
- Username: `myuser`
- Password: `mypass`

Пример `.env`:
```env
# Telegram API
API_ID=26680307
API_HASH=11fe6a7625e5c368e494c40f29066de0
PHONE=+79124922318

# Прокси
PROXY_ENABLED=true
PROXY_HOST=185.123.45.67
PROXY_PORT=8080
PROXY_USERNAME=myuser
PROXY_PASSWORD=mypass
```

### Шаг 3: Сохрани и запусти

```bash
python start.py
```

В логе увидишь:
```
[INFO] Прокси: 185.123.45.67:8080
[INFO] Подключение...
[OK] В системе: ...
```

---

## ✅ Проверка работы

### Тест подключения

Запусти:
```bash
python test_connect.py
```

**Успех:**
```
[OK] Сессия активна
[INFO] Пользователь: ...
```

**Если ошибка:**
- Проверь данные в `.env`
- Убедись, что `PROXY_ENABLED=true`
- Проверь баланс прокси

---

## 🐛 Troubleshooting

### ❌ "Connection timed out"

**Причина:** Прокси не отвечает

**Решение:**
1. Проверь `PROXY_HOST` и `PROXY_PORT`
2. Протестируй прокси в браузере
3. Обратись в поддержку прокси-сервиса

### ❌ "Unauthorized" / "Session expired"

**Причина:** Сессия устарела

**Решение:**
1. Удали `sessions/userbot.session`
2. Запусти `python start.py`
3. Выбери пункт 1 (войти)
4. Введи код из Telegram

### ❌ FloodWait ошибки

**Причина:** Слишком частая отправка

**Решение:**
- Увеличь `MIN_DELAY` и `MAX_DELAY` в `start.py`
- Уменьши `DAILY_LIMIT`

### ❌ "Phone number banned"

**Причина:** Номер заблокирован Telegram

**Решение:**
- Используй другой номер
- Не спамь в первые дни
- Включи 2FA

---

## 📊 Рекомендуемые настройки

### Для 1 аккаунта (начало)

```env
DAILY_LIMIT=20
MIN_DELAY=90
MAX_DELAY=180
```

### Для 1 аккаунта (после 2 недель)

```env
DAILY_LIMIT=40
MIN_DELAY=50
MAX_DELAY=100
```

### С прокси (Индия/Индонезия)

Увеличь таймауты в `start.py`:
```python
# send_message():
timeout=15.0  # текст (было 10)
timeout=90.0  # фото (было 60)
```

---

## 📞 Поддержка прокси-сервисов

- **Proxy6:** support@proxy6.net
- **Proxy-Seller:** support@proxy-seller.com
- **IPRoyal:** support@iproyal.com

---

**Последнее обновление:** Март 2026
