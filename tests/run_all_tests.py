"""
Скрипт для запуска всех проверок последовательно.
Выполняет все тесты и выводит итоговый отчет.
"""
import subprocess
import sys
import os
from pathlib import Path

# Цвета для вывода


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Выводит заголовок."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")


def check_and_fix_dependencies():
    """Проверяет и исправляет проблемы с зависимостями."""
    try:
        import httpx

        # Проверка совместимости
        httpx_version = tuple(map(int, httpx.__version__.split('.')[:2]))
        if httpx_version < (0, 27):
            print(f"{Colors.YELLOW}⚠️  Обнаружена проблема совместимости httpx {httpx.__version__}{Colors.RESET}")
            print(f"{Colors.YELLOW}   Попытка автоматического исправления...{Colors.RESET}")

            import subprocess
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "httpx>=0.27.0", "-q"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                # Перезагружаем модуль
                import importlib
                importlib.reload(httpx)
                httpx_version = tuple(map(int, httpx.__version__.split('.')[:2]))
                if httpx_version >= (0, 27):
                    print(f"{Colors.GREEN}✅ Зависимости исправлены автоматически{Colors.RESET}")
                    return True

            print(f"{Colors.RED}❌ Не удалось исправить автоматически{Colors.RESET}")
            print(f"{Colors.YELLOW}   Запустите: python fix_dependencies.py{Colors.RESET}")
            return False
        return True
    except ImportError:
        return True
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  Не удалось проверить зависимости: {e}{Colors.RESET}")
        return True


def run_test(script_name, description):
    """Запускает тестовый скрипт и возвращает результат."""
    print(f"{Colors.BOLD}Запуск: {description}{Colors.RESET}")
    print(f"Скрипт: {script_name}\n")

    try:
        if script_name.endswith('.py'):
            # Для Python скриптов
            if 'asyncio' in open(script_name).read():
                # Асинхронный скрипт - нужно запустить через asyncio
                result = subprocess.run(
                    [sys.executable, script_name],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            else:
                result = subprocess.run(
                    [sys.executable, script_name],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
        else:
            result = subprocess.run(
                script_name,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )

        print(result.stdout)
        if result.stderr:
            print(f"{Colors.YELLOW}Предупреждения:{Colors.RESET}")
            print(result.stderr)

        if result.returncode == 0:
            print(f"{Colors.GREEN}✅ {description} - УСПЕШНО{Colors.RESET}\n")
            return True
        else:
            print(f"{Colors.RED}❌ {description} - ОШИБКА (код: {result.returncode}){Colors.RESET}\n")
            return False

    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}❌ {description} - ТАЙМАУТ (превышено 5 минут){Colors.RESET}\n")
        return False
    except Exception as e:
        print(f"{Colors.RED}❌ {description} - ИСКЛЮЧЕНИЕ: {e}{Colors.RESET}\n")
        return False


def check_prerequisites():
    """Проверяет предварительные условия."""
    print_header("ПРОВЕРКА ПРЕДВАРИТЕЛЬНЫХ УСЛОВИЙ")

    checks = {}

    # Проверка и исправление зависимостей
    if not check_and_fix_dependencies():
        checks['dependencies_ok'] = False
    else:
        checks['dependencies_ok'] = True

    # Проверка .env файла
    if Path('.env').exists():
        print(f"{Colors.GREEN}✅ Файл .env существует{Colors.RESET}")
        checks['env_file'] = True

        # Проверка переменных окружения
        from dotenv import load_dotenv
        load_dotenv()

        required_vars = ['TELEGRAM_BOT_TOKEN', 'OPENAI_API_KEY', 'DATABASE_URL']
        for var in required_vars:
            if os.getenv(var):
                print(f"{Colors.GREEN}✅ {var} настроен{Colors.RESET}")
                checks[var] = True
            else:
                print(f"{Colors.YELLOW}⚠️  {var} не настроен{Colors.RESET}")
                checks[var] = False
    else:
        print(f"{Colors.YELLOW}⚠️  Файл .env не найден{Colors.RESET}")
        print(f"{Colors.YELLOW}   Создайте файл .env: python setup_env.py{Colors.RESET}")
        checks['env_file'] = False

    # Проверка Python версии
    python_version = sys.version_info
    if python_version >= (3, 11):
        print(f"{Colors.GREEN}✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}{Colors.RESET}")
        checks['python_version'] = True
    else:
        print(f"{Colors.YELLOW}⚠️  Python {python_version.major}.{python_version.minor} (рекомендуется 3.11+){Colors.RESET}")
        checks['python_version'] = False

    # Проверка зависимостей
    required_packages = ['aiogram', 'sqlalchemy', 'asyncpg', 'psycopg2', 'openai']
    for package in required_packages:
        try:
            mod = __import__(package)
            version = getattr(mod, '__version__', 'unknown')
            if version != 'unknown':
                print(f"{Colors.GREEN}✅ {package} {version} установлен{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}✅ {package} установлен{Colors.RESET}")
            checks[package] = True
        except ImportError:
            print(f"{Colors.RED}❌ {package} не установлен{Colors.RESET}")
            checks[package] = False
        except Exception as e:
            # Обработка ошибок совместимости для openai
            if package == 'openai' and 'proxies' in str(e).lower():
                print(f"{Colors.YELLOW}⚠️  {package} установлен, но есть проблема совместимости{Colors.RESET}")
                print(f"{Colors.YELLOW}   Запустите: python fix_dependencies.py{Colors.RESET}")
                checks[package] = False
            else:
                print(f"{Colors.RED}❌ Ошибка при проверке {package}: {e}{Colors.RESET}")
                checks[package] = False

    all_passed = all(checks.values())

    if all_passed:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Все предварительные условия выполнены{Colors.RESET}\n")
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Некоторые предварительные условия не выполнены{Colors.RESET}\n")
        print("Рекомендуется исправить проблемы перед запуском тестов.\n")

    return checks


def main():
    """Основная функция."""
    print_header("ЗАПУСК ВСЕХ ПРОВЕРОК ТРЕБОВАНИЙ К БОТУ")

    # Проверка предварительных условий
    prerequisites = check_prerequisites()

    # Предупреждение о проблемах с зависимостями
    if not prerequisites.get('dependencies_ok', True):
        print(f"\n{Colors.YELLOW}⚠️  Обнаружены проблемы с зависимостями{Colors.RESET}")
        print(f"{Colors.YELLOW}   Рекомендуется запустить: python fix_dependencies.py{Colors.RESET}\n")

    if not prerequisites.get('env_file'):
        print(f"\n{Colors.RED}❌ Файл .env не найден{Colors.RESET}")
        print(f"{Colors.YELLOW}Для запуска проверок необходимо создать файл .env{Colors.RESET}")
        print(f"\n{Colors.BOLD}Варианты:{Colors.RESET}")
        setup_cmd = f"{Colors.GREEN}python setup_env.py{Colors.RESET}"
        print(f"1. Интерактивная настройка: {setup_cmd}")
        cp_cmd = f"{Colors.GREEN}cp .env.example .env{Colors.RESET}"
        print(f"2. Вручную: {cp_cmd}")
        print("   Затем отредактируйте .env и заполните значения")
        print(f"\n{Colors.BLUE}{'='*70}{Colors.RESET}\n")
        return

    # Список тестов для запуска
    tests_dir = Path(__file__).parent
    tests = [
        {
            'script': str(tests_dir / 'test_database_structure.py'),
            'description': 'Проверка структуры базы данных',
            'required': ['DATABASE_URL']
        },
        {
            'script': str(tests_dir / 'test_sql_generation.py'),
            'description': 'Проверка генерации SQL запросов',
            'required': ['OPENAI_API_KEY', 'DATABASE_URL']
        },
        {
            'script': str(tests_dir / 'test_bot.py'),
            'description': 'Тестирование примеров вопросов',
            'required': ['OPENAI_API_KEY', 'DATABASE_URL']
        },
        {
            'script': str(tests_dir / 'test_requirements.py'),
            'description': 'Комплексная проверка всех требований',
            'required': ['OPENAI_API_KEY', 'DATABASE_URL']
        }
    ]

    results = {}

    # Запуск тестов
    for test in tests:
        # Проверяем, есть ли все необходимые переменные
        required_vars_ok = all(prerequisites.get(var, False) for var in test['required'])

        if required_vars_ok:
            success = run_test(test['script'], test['description'])
            results[test['description']] = success
        else:
            missing = [var for var in test['required'] if not prerequisites.get(var, False)]
            print(f"{Colors.YELLOW}⚠️  Пропущено: {test['description']}{Colors.RESET}")
            print(f"   Отсутствуют переменные: {', '.join(missing)}\n")
            results[test['description']] = None

    # Итоговая сводка
    print_header("ИТОГОВАЯ СВОДКА")

    total = len([r for r in results.values() if r is not None])
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)

    print(f"Всего тестов: {len(results)}")
    print(f"{Colors.GREEN}✅ Успешно: {passed}{Colors.RESET}")
    print(f"{Colors.RED}❌ Не пройдено: {failed}{Colors.RESET}")
    print(f"{Colors.YELLOW}⚠️  Пропущено: {skipped}{Colors.RESET}")

    if total > 0:
        success_rate = (passed / total) * 100
        print(f"\nПроцент успешных проверок: {success_rate:.1f}%")

        if success_rate >= 90:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Все основные требования выполнены!{Colors.RESET}")
        elif success_rate >= 70:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Большинство требований выполнено, но есть замечания{Colors.RESET}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ Требуется доработка{Colors.RESET}")

    print(f"\n{Colors.BLUE}{'='*70}{Colors.RESET}\n")


if __name__ == "__main__":
    main()
