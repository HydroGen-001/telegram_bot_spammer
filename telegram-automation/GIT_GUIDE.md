# Telegram Automation — Работа с Git

## Быстрый старт

### На текущем компьютере

```cmd
cd "c:\Users\ACER\OneDrive\Desktop\Новая папка (4)\telegram-automation"

# Инициализация Git
git init

# Добавление всех файлов
git add .

# Первый коммит
git commit -m "Initial commit: Telegram automation MVP"

# Создание репозитория на GitHub (в браузере)
# Затем добавьте remote и push:
git remote add origin https://github.com/ВАШ_НИК/telegram-automation.git
git push -u origin main
```

---

### На домашнем компьютере

```cmd
# Клонирование репозитория
git clone https://github.com/ВАШ_НИК/telegram-automation.git
cd telegram-automation

# Установка зависимостей
pip install -r requirements.txt

# Настройка .env (создайте файл вручную)
copy .env.example .env
# Откройте .env и вставьте ваши API ключи

# Копирование сессии (если есть)
# Скопируйте файл userbot.session в папку sessions\

# Проверка сессии
python check_session.py

# Запуск
python src\main.py
```

---

## Что синхронизируется через Git

| Файлы | Синхронизация |
|-------|---------------|
| ✅ Исходный код (`src/`) | Да |
| ✅ Конфигурация (`config/`) | Да |
| ✅ Зависимости (`requirements.txt`) | Да |
| ✅ Документация (`*.md`) | Да |
| ❌ `.env` | Нет (создавать вручную) |
| ❌ `sessions/*.session` | Нет (копировать вручную) |
| ❌ `database/*.db` | Нет (локальная история) |
| ❌ `logs/*.log` | Нет |

---

## Безопасность

### Никогда не коммитьте:
- `.env` — содержит API ключи
- `sessions/*.session` — доступ к Telegram
- `database/*.db` — личные данные

### Если случайно закоммитили чувствительные данные:

```cmd
# Удалить из истории Git
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env sessions/*.session" \
  --prune-empty --tag-name-filter cat -- --all

# Обновить remote
git push origin --force --all
```

---

## Рабочий процесс

### На работе:
```cmd
git add .
git commit -m "Описание изменений"
git push
```

### Дома:
```cmd
git pull
pip install -r requirements.txt  # если обновились зависимости
python src\main.py
```

---

## Альтернативы Git

Если не хотите использовать Git:

### Вариант 1: Облачное хранилище
- Положите проект в OneDrive/Google Drive
- Синхронизация автоматическая

### Вариант 2: ZIP-архив
- Создавайте архив после изменений
- Передавайте через USB/облако

---

## Чек-лист для переноса

- [ ] Закоммитить изменения
- [ ] Сделать push в репозиторий
- [ ] На другом компьютере: git pull
- [ ] Создать `.env` с API ключами
- [ ] Скопировать `sessions/userbot.session`
- [ ] Установить зависимости: `pip install -r requirements.txt`
- [ ] Проверить сессию: `python check_session.py`
- [ ] Запустить: `python src\main.py`
