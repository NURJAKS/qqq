# 🚀 Деплой в Streamlit Community Cloud

## Подготовка к деплою

### 1. Файлы для деплоя
- `app.py` - основное приложение (объединенный backend + frontend)
- `requirements_streamlit.txt` - зависимости для Streamlit Cloud
- `.streamlit/config.toml` - конфигурация Streamlit
- `.streamlit/secrets.toml` - шаблон секретов

### 2. Загрузка в GitHub
1. Создайте репозиторий на GitHub
2. Загрузите следующие файлы:
   ```
   app.py
   requirements_streamlit.txt
   .streamlit/config.toml
   README.md
   ```

### 3. Деплой в Streamlit Cloud

1. Зайдите на https://share.streamlit.io/
2. Подключите GitHub аккаунт
3. Выберите ваш репозиторий
4. Укажите `app.py` как main file
5. Добавьте секреты в настройках:

```toml
[general]
SECRET_KEY = "ваш_секретный_ключ_минимум_32_символа"

[email]
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password"
```

### 4. Особенности деплоя

- База данных SQLite создается автоматически
- QR-коды генерируются в памяти
- PDF сертификаты генерируются динамически
- Все данные сохраняются в файловой системе Streamlit Cloud

### 5. Тестирование

После деплоя проверьте:
- ✅ Регистрацию пользователей
- ✅ Создание мероприятий
- ✅ Сканирование QR-кодов
- ✅ Генерацию сертификатов

## Структура проекта для деплоя

```
your-repo/
├── app.py                      # Основное приложение
├── requirements_streamlit.txt  # Зависимости
├── .streamlit/
│   ├── config.toml            # Конфигурация
│   └── secrets.toml           # Шаблон секретов
└── README.md                  # Документация
```

## Команды для локального тестирования

```bash
# Установка зависимостей
pip install -r requirements_streamlit.txt

# Запуск приложения
streamlit run app.py
```

## Важные замечания

1. **Секреты**: Обязательно настройте секреты в Streamlit Cloud
2. **Email**: Для отправки сертификатов нужен настроенный SMTP
3. **База данных**: SQLite файл создается автоматически
4. **Безопасность**: Используйте сильный SECRET_KEY
