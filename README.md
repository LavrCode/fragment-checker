# Fragment Username Checker

Инструмент для проверки доступности юзернеймов на [Fragment.com](https://fragment.com) с уведомлениями в Telegram.

## Возможности

- Проверка наличия свободных юзернеймов на Fragment
- Отправка уведомлений в Telegram
- Защита от блокировки с различными механизмами безопасности:
  - Ротация User-Agent
  - Адаптивная задержка между запросами
  - Обработка ошибок с повторными попытками
- Сохранение и возобновление прогресса
- Поддержка проверки как одиночных юзернеймов, так и списков из файла

## Установка

```bash
git clone https://github.com/LavrCode/fragment-checker.git
cd fragment-checker

pip install -r requirements.txt
```

### Зависимости

- requests
- beautifulsoup4
- aiogram (v3+)
- fake-useragent

## Использование

### Простая проверка одного юзернейма

```bash
python fragment_checker.py -u username
```

### Проверка списка юзернеймов из файла

```bash
python fragment_checker.py -f usernames.txt
```

### Отправка уведомлений в Telegram

```bash
python fragment_checker.py -f usernames.txt -t "YOUR_TELEGRAM_BOT_TOKEN" -c "YOUR_CHAT_ID"
```

### Безопасный режим для больших списков

```bash
python fragment_checker.py -f large_list.txt -d 2.5 -D 5.0 -s progress.json -b 5
```

## Аргументы командной строки

| Аргумент | Описание |
|----------|----------|
| `-u`, `--username` | Проверить один юзернейм |
| `-f`, `--file` | Путь к файлу со списком юзернеймов (по одному на строку) |
| `-t`, `--token` | Токен Telegram бота |
| `-c`, `--chat` | ID чата Telegram для отправки сообщений |
| `-d`, `--delay` | Минимальная задержка между запросами в секундах (по умолчанию 1.0) |
| `-D`, `--max-delay` | Максимальная задержка между запросами в секундах |
| `-s`, `--state` | Путь к файлу для сохранения/загрузки прогресса |
| `-b`, `--batch` | Размер пакета для сохранения прогресса (по умолчанию 10) |

## Защита от блокировки

Скрипт использует несколько механизмов для предотвращения блокировки со стороны Fragment:

1. **Ротация User-Agent**:
   - Поддерживает пул из 10 различных User-Agent
   - Периодически обновляет User-Agent для имитации разных браузеров

2. **Адаптивные задержки**:
   - Случайные задержки между запросами в указанном диапазоне
   - Автоматическое увеличение задержки после ошибок
   - Специальная обработка ответов с кодом 429 (Too Many Requests)

3. **Повторные попытки**:
   - Экспоненциальная задержка между повторными попытками
   - Обработка сетевых ошибок и временных сбоев

## Формат результатов

Для каждого юзернейма скрипт определяет один из следующих статусов:

- **unavailable** - юзернейм свободен (доступен для регистрации)
- **available** - юзернейм недоступен
- **taken** - юзернейм уже занят
- **unknown** - статус не удалось определить
- **error** - произошла ошибка при проверке

## Пример файла с юзернеймами

```
username1
username2
username3
```

## Лицензия

MIT License

## Автор

Разработано с ❤️ [LavrCode](https://lavrcode.t.me/)

---

<p align="center">
  Если у вас возникли вопросы или предложения, создайте issue в репозитории проекта.
</p> 
