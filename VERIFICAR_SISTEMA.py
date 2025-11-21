#!/usr/bin/env python
"""
Script de verificación completa del sistema Twitter Scraper
Verifica que todos los componentes estén funcionando correctamente
"""
import os
import sys
import time
import sqlite3
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{BLUE}{BOLD}{'='*60}{RESET}")
    print(f"{BLUE}{BOLD}{text}{RESET}")
    print(f"{BLUE}{BOLD}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ {text}{RESET}")

def check_python_version():
    """Verificar versión de Python"""
    print_info("Verificando versión de Python...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} (se requiere 3.8+)")
        return False

def check_redis():
    """Verificar que Redis esté corriendo"""
    print_info("Verificando Redis...")
    try:
        result = subprocess.run(
            ['redis-cli', 'ping'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and 'PONG' in result.stdout:
            print_success("Redis está corriendo")
            return True
        else:
            print_error("Redis no responde correctamente")
            return False
    except FileNotFoundError:
        print_error("redis-cli no encontrado. ¿Redis está instalado?")
        return False
    except subprocess.TimeoutExpired:
        print_error("Redis timeout. ¿Está corriendo en localhost:6379?")
        return False
    except Exception as e:
        print_error(f"Error verificando Redis: {e}")
        return False

def check_dependencies():
    """Verificar dependencias de Python"""
    print_info("Verificando dependencias de Python...")
    required = [
        'flask',
        'celery',
        'redis',
        'selenium',
        'beautifulsoup4',
        'lxml',
        'python-dotenv',
        'flask_cors'
    ]

    all_ok = True
    for package in required:
        try:
            __import__(package.replace('-', '_'))
            print_success(f"{package}")
        except ImportError:
            print_error(f"{package} NO INSTALADO")
            all_ok = False

    return all_ok

def check_env_file():
    """Verificar archivo .env"""
    print_info("Verificando archivo .env...")

    if not os.path.exists('.env'):
        print_error(".env no encontrado")
        return False

    load_dotenv()

    required_vars = [
        'FLASK_SECRET_KEY',
        'CELERY_BROKER_URL',
        'CELERY_RESULT_BACKEND',
        'DATABASE_PATH'
    ]

    all_ok = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Check if Redis URLs use localhost
            if 'BROKER_URL' in var or 'BACKEND' in var:
                if 'localhost' in value or '127.0.0.1' in value:
                    print_success(f"{var} = {value}")
                else:
                    print_warning(f"{var} = {value} (debería usar localhost)")
            else:
                print_success(f"{var} = {value}")
        else:
            print_error(f"{var} NO DEFINIDO")
            all_ok = False

    return all_ok

def check_directories():
    """Verificar directorios necesarios"""
    print_info("Verificando directorios...")

    required_dirs = [
        'app',
        'app/routes',
        'app/services',
        'app/models',
        'app/templates',
        'celery_app',
        'config',
        'logs',
        'chrome_profiles'
    ]

    all_ok = True
    for directory in required_dirs:
        path = Path(directory)
        if path.exists():
            print_success(f"{directory}/")
        else:
            print_error(f"{directory}/ NO EXISTE")
            all_ok = False

    return all_ok

def check_database():
    """Verificar base de datos"""
    print_info("Verificando base de datos...")

    db_path = os.getenv('DATABASE_PATH', 'twitter_scraper.db')

    if not os.path.exists(db_path):
        print_warning("Base de datos no existe, se creará al iniciar Flask")
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ['profiles', 'tweets', 'scrape_logs']
        for table in required_tables:
            if table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print_success(f"Tabla '{table}' existe ({count} registros)")
            else:
                print_error(f"Tabla '{table}' NO EXISTE")

        conn.close()
        return True

    except Exception as e:
        print_error(f"Error verificando base de datos: {e}")
        return False

def check_chromedriver():
    """Verificar ChromeDriver"""
    print_info("Verificando ChromeDriver...")

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        print_info("Creando instancia de Chrome (puede tardar unos segundos)...")
        driver = webdriver.Chrome(options=options)
        driver.get('about:blank')
        driver.quit()

        print_success("ChromeDriver funciona correctamente")
        return True

    except Exception as e:
        print_error(f"ChromeDriver error: {e}")
        print_warning("Instala ChromeDriver: https://chromedriver.chromium.org/")
        return False

def check_celery_config():
    """Verificar configuración de Celery"""
    print_info("Verificando configuración de Celery...")

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from celery_app.celery_config import celery_app

        print_success(f"Celery app: {celery_app.main}")
        print_success(f"Broker: {celery_app.conf.broker_url}")
        print_success(f"Backend: {celery_app.conf.result_backend}")

        return True
    except Exception as e:
        print_error(f"Error cargando configuración de Celery: {e}")
        return False

def check_flask_app():
    """Verificar que Flask app se puede crear"""
    print_info("Verificando Flask app...")

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from app import create_app

        app = create_app()
        print_success("Flask app creada correctamente")

        # Check routes
        rules = list(app.url_map.iter_rules())
        print_info(f"Total de rutas: {len(rules)}")

        important_routes = ['/', '/search', '/monitoring', '/add_profile', '/api.scrape_profile']
        for route in important_routes:
            found = any(route in str(rule) for rule in rules)
            if found:
                print_success(f"Ruta {route}")
            else:
                print_warning(f"Ruta {route} no encontrada")

        return True

    except Exception as e:
        print_error(f"Error creando Flask app: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_redis_connection():
    """Probar conexión a Redis"""
    print_info("Probando conexión a Redis desde Python...")

    try:
        import redis

        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)

        # Test set/get
        test_key = 'twitter_scraper_test'
        test_value = 'verification_test'

        r.set(test_key, test_value)
        result = r.get(test_key)
        r.delete(test_key)

        if result.decode() == test_value:
            print_success("Redis read/write funciona correctamente")
            return True
        else:
            print_error("Redis read/write falló")
            return False

    except Exception as e:
        print_error(f"Error conectando a Redis: {e}")
        return False

def print_summary(results):
    """Imprimir resumen de verificación"""
    print_header("RESUMEN DE VERIFICACIÓN")

    total = len(results)
    passed = sum(results.values())
    failed = total - passed

    print(f"\nTotal de verificaciones: {total}")
    print(f"{GREEN}Pasadas: {passed}{RESET}")
    print(f"{RED}Fallidas: {failed}{RESET}")

    percentage = (passed / total) * 100

    print(f"\n{BOLD}Estado del sistema: ", end="")
    if percentage == 100:
        print(f"{GREEN}PERFECTO ✓{RESET}")
    elif percentage >= 80:
        print(f"{YELLOW}BUENO (con advertencias){RESET}")
    else:
        print(f"{RED}NECESITA ATENCIÓN{RESET}")

    print(f"\nPorcentaje de éxito: {percentage:.1f}%")

    if failed > 0:
        print(f"\n{YELLOW}Verifica los errores arriba antes de iniciar el sistema.{RESET}")
    else:
        print(f"\n{GREEN}¡Todo listo! Puedes iniciar el sistema con start_windows.bat{RESET}")

def main():
    """Función principal"""
    print_header("VERIFICACIÓN COMPLETA DEL SISTEMA TWITTER SCRAPER")

    # Change to script directory
    os.chdir(Path(__file__).parent)

    results = {}

    # Run all checks
    print_header("[1/11] Python")
    results['python'] = check_python_version()

    print_header("[2/11] Redis")
    results['redis'] = check_redis()

    print_header("[3/11] Dependencias Python")
    results['dependencies'] = check_dependencies()

    print_header("[4/11] Archivo .env")
    results['env'] = check_env_file()

    print_header("[5/11] Directorios")
    results['directories'] = check_directories()

    print_header("[6/11] Base de datos")
    results['database'] = check_database()

    print_header("[7/11] ChromeDriver")
    results['chromedriver'] = check_chromedriver()

    print_header("[8/11] Configuración Celery")
    results['celery_config'] = check_celery_config()

    print_header("[9/11] Flask App")
    results['flask'] = check_flask_app()

    print_header("[10/11] Conexión Redis Python")
    results['redis_python'] = test_redis_connection()

    print_header("[11/11] Scripts de inicio")
    start_scripts = ['start_windows.bat', 'INICIO_RAPIDO.bat']
    all_exist = all(os.path.exists(script) for script in start_scripts)
    if all_exist:
        print_success("Scripts de inicio encontrados")
        results['scripts'] = True
    else:
        print_error("Scripts de inicio no encontrados")
        results['scripts'] = False

    # Print summary
    print_summary(results)

    return all(results.values())

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Verificación interrumpida{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Error inesperado: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
