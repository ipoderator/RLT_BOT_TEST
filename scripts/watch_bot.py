#!/usr/bin/env python3
"""
Скрипт для автоматической перезагрузки бота при изменении файлов.
Использует watchdog для отслеживания изменений в исходном коде.
"""
import os
import sys
import subprocess
import signal
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class BotReloadHandler(FileSystemEventHandler):
    """Обработчик событий файловой системы для перезагрузки бота."""

    def __init__(self, script_path):
        super().__init__()
        self.script_path = script_path
        self.process = None
        self.last_reload = 0
        self.reload_delay = 2  # Задержка перед перезагрузкой (секунды)

    def on_modified(self, event):
        """Вызывается при изменении файла."""
        if event.is_directory:
            return

        # Игнорируем изменения в служебных файлах
        ignored_extensions = {'.pyc', '.pyo', '.pyd', '.log', '.json'}
        if Path(event.src_path).suffix in ignored_extensions:
            return

        # Игнорируем изменения в кэше и логах
        if 'cache' in event.src_path or 'logs' in event.src_path:
            return

        # Игнорируем изменения в __pycache__
        if '__pycache__' in event.src_path:
            return

        # Проверяем, что это Python файл
        if not event.src_path.endswith('.py'):
            return

        # Защита от множественных событий за короткое время
        current_time = time.time()
        if current_time - self.last_reload < self.reload_delay:
            return

        self.last_reload = current_time
        print(f"\n🔄 Обнаружено изменение в {event.src_path}")
        print("🔄 Перезапускаю бота...")
        self.reload_bot()

    def reload_bot(self):
        """Перезапускает процесс бота."""
        # Останавливаем текущий процесс
        if self.process and self.process.poll() is None:
            print("⏹️  Останавливаю текущий процесс бота...")
            try:
                self.process.terminate()
                # Ждем завершения процесса
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("⚠️  Процесс не завершился, принудительно завершаю...")
                    self.process.kill()
                    self.process.wait()
            except Exception as e:
                print(f"⚠️  Ошибка при остановке процесса: {e}")

        # Запускаем новый процесс
        print("▶️  Запускаю бота...")
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-m", "src.bot"],
                stdout=sys.stdout,
                stderr=sys.stderr,
                env=os.environ.copy()
            )
            print("✅ Бот перезапущен!")
        except Exception as e:
            print(f"❌ Ошибка при запуске бота: {e}")
            sys.exit(1)

    def start_bot(self):
        """Запускает бота в первый раз."""
        self.reload_bot()


def main():
    """Главная функция."""
    # Определяем директории для отслеживания
    base_dir = Path(__file__).parent.parent
    watch_dirs = [
        base_dir / "src",
        base_dir / "scripts",
    ]

    # Проверяем существование директорий
    existing_dirs = [d for d in watch_dirs if d.exists()]
    if not existing_dirs:
        print("❌ Не найдены директории для отслеживания")
        sys.exit(1)

    print("🚀 Запуск бота с автоперезагрузкой...")
    print(f"📁 Отслеживаю изменения в: {', '.join(str(d) for d in existing_dirs)}")

    # Создаем обработчик и наблюдатель
    handler = BotReloadHandler("src.bot")
    observer = Observer()

    # Регистрируем обработчики для каждой директории
    for watch_dir in existing_dirs:
        observer.schedule(handler, str(watch_dir), recursive=True)
        print(f"  ✓ {watch_dir}")

    # Запускаем наблюдатель
    observer.start()

    # Запускаем бота в первый раз
    handler.start_bot()

    # Обработчик сигналов для корректного завершения
    def signal_handler(sig, frame):
        print("\n🛑 Получен сигнал завершения, останавливаю...")
        observer.stop()
        if handler.process and handler.process.poll() is None:
            handler.process.terminate()
            try:
                handler.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                handler.process.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Ждем завершения
        while True:
            # Проверяем, что процесс бота еще работает
            if handler.process and handler.process.poll() is not None:
                print(f"\n⚠️  Бот завершился с кодом {handler.process.returncode}")
                print("🔄 Перезапускаю...")
                handler.reload_bot()
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()



