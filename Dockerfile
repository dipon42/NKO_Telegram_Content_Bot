# Используем официальный образ Python 3.12
FROM python:3.12.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы проекта
COPY . .

# Создаем переменные окружения (опционально, можно передавать при запуске)
ENV BOT_TOKEN=8152053719:AAFhrGQsLamc4n8ZKWe7Kj3wvJcuXxfS5U4
ENV DATABASE_URL=sqlite+aiosqlite:///./nko_bot.db
ENV ENCRYPTION_KEY=7Vbny4HHP3odGMLkP2e2JpwYlC2APaxChXEj8Bb37SA=
ENV GIGACHAT_CREDENTIALS=MDE5YTgzNGUtZWJmZi03OTRjLWFjODEtNzVjNzBlZTJmMDM3OmI2ODg0NDk2LWViNDgtNDU0ZS05NTg5LWUwYTFjZGMxZWNmNw==

# Запускаем бота
CMD ["python", "main.py"]