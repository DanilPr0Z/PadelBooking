#!/usr/bin/env python
"""
Скрипт для автоматической настройки .env файла
Использование: python setup_env.py
"""
import os
from pathlib import Path
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / '.env'
ENV_EXAMPLE = BASE_DIR / '.env.example'

def create_env_file():
    """Создает .env файл из .env.example с автоматической генерацией SECRET_KEY"""
    
    if ENV_FILE.exists():
        print(f"⚠️  Файл {ENV_FILE} уже существует!")
        response = input("Перезаписать? (y/n): ")
        if response.lower() != 'y':
            print("Отменено.")
            return
    
    if not ENV_EXAMPLE.exists():
        print(f"❌ Файл {ENV_EXAMPLE} не найден!")
        return
    
    # Читаем .env.example
    with open(ENV_EXAMPLE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Генерируем новый SECRET_KEY
    secret_key = get_random_secret_key()
    print(f"🔑 Сгенерирован новый SECRET_KEY: {secret_key[:20]}...")
    
    # Заменяем SECRET_KEY в содержимом
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('SECRET_KEY=') and 'django-insecure' in line:
            lines[i] = f'SECRET_KEY={secret_key}'
            break
    
    # Записываем в .env
    new_content = '\n'.join(lines)
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ Файл {ENV_FILE} успешно создан!")
    print(f"📝 SECRET_KEY автоматически сгенерирован и установлен")
    print(f"\n💡 Для продакшена не забудьте:")
    print(f"   - Установить DEBUG=False")
    print(f"   - Указать правильные ALLOWED_HOSTS")

if __name__ == '__main__':
    try:
        create_env_file()
    except ImportError:
        print("❌ Ошибка: Django не установлен или не в PYTHONPATH")
        print("💡 Попробуйте: pip install django")
        print("\nИли создайте .env вручную, скопировав .env.example")






