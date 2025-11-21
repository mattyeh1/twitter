# 🐦 Twitter Scraper - Sistema Avanzado

Sistema profesional de scraping de Twitter/X con **pool de drivers**, **scraping concurrente**, **jobs asíncronos** y **monitoreo en tiempo real**.

## 🚀 Características

### **Mejoras Principales vs Versión Anterior**

#### ✅ **Scraping Concurrente**
- **Antes**: Un solo usuario a la vez, los demás esperaban
- **Ahora**: Hasta **3+ usuarios simultáneos** scrapeando en paralelo
- Pool de drivers Selenium con manejo automático de recursos

#### ✅ **Jobs Asíncronos con Celery**
- **Antes**: Request HTTP bloqueaba hasta terminar (2-5 minutos)
- **Ahora**: Response inmediata + progreso en tiempo real
- Sistema de colas con Redis
- Reintentos automáticos en caso de error

#### ✅ **Monitoreo y Métricas**
- Dashboard de estadísticas del pool de drivers
- Monitor de tareas activas/en cola (Flower)
- Logs estructurados y detallados

#### ✅ **Arquitectura Profesional**
- **Antes**: Todo en 1 archivo de 2000+ líneas
- **Ahora**: Estructura modular y mantenible
- Separación de responsabilidades (services, routes, models)
- Configuración centralizada

#### ✅ **Fácil Deployment**
- Docker Compose con todos los servicios
- Scripts de inicio automatizados
- Configuración con variables de entorno

---

## 📁 Estructura del Proyecto

```
twitter-scraper/
├── app/                          # Aplicación Flask
│   ├── __init__.py              # Factory de la app
│   ├── routes/                  # Endpoints web
│   │   ├── dashboard.py         # Dashboard principal
│   │   └── api.py               # API REST
│   ├── services/                # Lógica de negocio
│   │   ├── scraper_service.py   # Scraper refactorizado
│   │   └── driver_pool.py       # Pool de Selenium drivers
│   ├── templates/               # HTML templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── monitoring.html
│   │   ├── tweets.html
│   │   └── search.html
│   └── static/                  # CSS, JS, imágenes
│
├── celery_app/                  # Celery para async tasks
│   ├── celery_config.py         # Configuración de Celery
│   └── tasks.py                 # Tareas asíncronas
│
├── config/                      # Configuración
│   └── settings.py              # Settings centralizados
│
├── logs/                        # Logs de la aplicación
├── chrome_profiles/             # Perfiles de Chrome (pool)
│
├── docker-compose.yml           # Orquestación de servicios
├── Dockerfile                   # Imagen Docker
├── requirements.txt             # Dependencias Python
├── .env.example                 # Variables de entorno
├── run.py                       # Punto de entrada
├── start_local.sh               # Script de inicio (Linux/Mac)
└── start_local.bat              # Script de inicio (Windows)
```

---

## 🔧 Instalación

### **Opción 1: Docker (Recomendado)**

```bash
# 1. Clonar repositorio
git clone <repo-url>
cd twitter-scraper

# 2. Copiar .env de ejemplo
cp .env.example .env

# 3. (Opcional) Editar .env con tus configuraciones
nano .env

# 4. Iniciar todos los servicios
docker-compose up -d

# 5. Ver logs
docker-compose logs -f

# Acceder a:
# - Dashboard: http://localhost:5000
# - Flower (Celery): http://localhost:5555
```

### **Opción 2: Instalación Local (Windows)**

#### **Requisitos previos:**
- Python 3.8+ (recomendado 3.10 o 3.11, evitar 3.14 pre-release)
- Redis para Windows
- Chrome + ChromeDriver

#### **Pasos:**

```bash
# 1. Instalar Redis para Windows
# Descargar e instalar de: https://github.com/tporadowski/redis/releases
# Después de instalar, iniciar Redis:
redis-server

# 2. Clonar repositorio
git clone <repo-url>
cd twitter

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Verificar instalación
python VERIFICAR_SISTEMA.py
# O usar el batch file:
VERIFICAR_SISTEMA.bat

# 5. Si todo OK, iniciar servicios
# OPCIÓN A: Inicio completo (instala + inicia)
start_windows.bat

# OPCIÓN B: Inicio rápido (solo inicia)
INICIO_RAPIDO.bat
```

### **Opción 3: Instalación Local (Linux/Mac)**

```bash
# 1. Instalar Redis
# Ubuntu/Debian:
sudo apt-get install redis-server
sudo systemctl start redis

# macOS:
brew install redis
brew services start redis

# 2. Clonar repositorio
git clone <repo-url>
cd twitter

# 3. Crear entorno virtual
python -m venv venv
source venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Copiar configuración
cp .env.example .env

# 6. Verificar instalación
python VERIFICAR_SISTEMA.py

# 7. Iniciar servicios manualmente
# Terminal 1: Flask
python run.py

# Terminal 2: Celery Worker
celery -A celery_app.celery_config worker --loglevel=info

# Terminal 3 (opcional): Flower
celery -A celery_app.celery_config flower --port=5555
```

---

## 🎯 Uso

### **1. Dashboard Principal**

Accede a `http://localhost:5000`

- Ver estadísticas generales
- Agregar nuevos perfiles a monitorear
- Scrapear perfiles manualmente
- Ver tweets guardados

### **2. Scraping Manual**

1. Click en "🚀 Scrapear Ahora" en cualquier perfil
2. El sistema:
   - Encola la tarea en Celery
   - Adquiere un driver del pool
   - Scrapea en background
   - Muestra progreso en tiempo real
   - Actualiza dashboard automáticamente

**Múltiples usuarios pueden scrapear simultáneamente** (hasta 3 por defecto)

### **3. Búsqueda de Tweets**

`http://localhost:5000/search`

- Buscar por palabras clave
- Filtrar por usuario, idioma, fecha
- Ordenar por fecha o likes
- Resaltado de términos buscados

### **4. Monitoreo del Sistema**

`http://localhost:5000/monitoring`

- Estado del pool de drivers (disponibles/activos)
- Tareas activas en Celery
- Estadísticas de uso
- Métricas en tiempo real

### **5. Flower (Celery Monitoring)**

`http://localhost:5555`

- Monitoreo avanzado de Celery
- Historial de tareas
- Workers activos
- Gráficos de performance

---

## 🔄 Cómo Funciona el Pool de Drivers

### **Problema Original:**

```
Usuario A: Click "Scrapear @elonmusk"
  ├─ Abre Chrome
  ├─ Navega a x.com/elonmusk
  │
  │  Usuario B: Click "Scrapear @openai"
  │   ├─ ❌ Intenta usar el mismo Chrome
  │   └─ ❌ CONFLICTO: Chrome ya está ocupado
  │
  └─ Usuario A termina (2-5 min después)
```

### **Solución con Pool:**

```
┌─────────────────────────────────┐
│      DRIVER POOL (Size: 3)      │
├──────────┬──────────┬───────────┤
│ Driver 1 │ Driver 2 │ Driver 3  │
│ (libre)  │ (libre)  │ (libre)   │
└──────────┴──────────┴───────────┘

Usuario A scrapea @elonmusk
  → Adquiere Driver 1

Usuario B scrapea @openai (simultáneamente)
  → Adquiere Driver 2

Usuario C scrapea @python (simultáneamente)
  → Adquiere Driver 3

Usuario D scrapea @netflix
  → Espera en cola (todos ocupados)
  → Cuando A termina, obtiene Driver 1
```

---

## ⚙️ Configuración

### **Variables de Entorno (`.env`)**

```bash
# Pool de Drivers
DRIVER_POOL_SIZE=3              # Scrapers concurrentes
HEADLESS=True                   # Chrome sin GUI

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Scraping
MAX_TWEETS_PER_SCRAPE=100
SCRAPE_SCROLL_COUNT=15
SCRAPE_SCROLL_DELAY=6

# Flask
FLASK_PORT=5000
FLASK_DEBUG=False
```

### **Ajustar Concurrencia**

**Para más scrapers simultáneos:**

```bash
# .env
DRIVER_POOL_SIZE=5  # Hasta 5 simultáneos

# docker-compose.yml (celery_worker)
command: celery -A celery_app.celery_config worker --concurrency=5
```

⚠️ **Nota**: Más drivers = más RAM/CPU

---

## 📊 Arquitectura del Sistema

```
┌──────────────┐
│   USUARIOS   │
│ (navegador)  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    FLASK     │  ← Web UI + API REST
│   (Puerto    │
│    5000)     │
└──────┬───────┘
       │
       ├──► POST /scrape_now/username
       │     └─► Encola tarea en Celery
       │
       ├──► GET /api/task/<id>
       │     └─► Consulta progreso
       │
       ▼
┌──────────────┐
│    REDIS     │  ← Message Broker + Result Backend
│   (Puerto    │
│    6379)     │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────┐
│         CELERY WORKERS               │
│  ┌────────┬────────┬────────┐       │
│  │Worker 1│Worker 2│Worker 3│       │
│  └────┬───┴────┬───┴────┬───┘       │
│       │        │        │            │
│       ▼        ▼        ▼            │
│  ┌────────────────────────────┐     │
│  │     DRIVER POOL            │     │
│  │  ┌────────┬────────┬─────┐ │     │
│  │  │Chrome 1│Chrome 2│Chr 3│ │     │
│  │  └────────┴────────┴─────┘ │     │
│  └────────────────────────────┘     │
└──────────────────────────────────────┘
       │
       ▼
┌──────────────┐
│   TWITTER/X  │  ← Scraping target
│   (x.com)    │
└──────────────┘
```

---

## 🐛 Troubleshooting

### **🔍 Verificación del Sistema**

Antes de reportar errores, ejecuta el script de verificación:

```bash
python VERIFICAR_SISTEMA.py
# O:
VERIFICAR_SISTEMA.bat
```

Este script verifica:
- ✓ Python 3.8+
- ✓ Redis corriendo
- ✓ Dependencias instaladas
- ✓ Archivo .env configurado
- ✓ Directorios creados
- ✓ ChromeDriver funcional
- ✓ Celery configurado
- ✓ Flask app cargable
- ✓ Redis Python conexión

### **Redis no se conecta**

```bash
# Verificar que Redis está corriendo
redis-cli ping
# Debe responder: PONG

# Iniciar Redis
redis-server

# Linux:
sudo systemctl start redis

# macOS:
brew services start redis
```

### **Error: 'celery' no reconocido (Windows)**

Los scripts de inicio ya usan `python -m celery` en lugar de `celery` para compatibilidad con Windows.

Si necesitas ejecutar Celery manualmente:

```bash
# ✓ CORRECTO (Windows):
python -m celery -A celery_app.celery_config worker --loglevel=info --pool=solo

# ✗ INCORRECTO:
celery -A celery_app.celery_config worker --loglevel=info
```

### **Error: Botones no funcionan / Web rota**

Verifica que `.env` use `localhost` en lugar de `redis`:

```ini
# ✓ CORRECTO (instalación local Windows):
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
REDIS_URL=redis://localhost:6379/0

# ✗ INCORRECTO (solo para Docker):
CELERY_BROKER_URL=redis://redis:6379/0
```

### **Error: lxml no se instala (Python 3.14)**

Si usas Python 3.14 (pre-release), lxml puede fallar. Soluciones:

```bash
# Opción 1: Actualizar a lxml con binarios
pip install --upgrade lxml

# Opción 2: Usar Python 3.10 o 3.11 (recomendado)
```

El `requirements.txt` incluye `lxml>=5.0.0` que tiene binarios para Python 3.14.

### **Chrome no se encuentra**

```bash
# Instalar Chrome/Chromium
# Ubuntu:
sudo apt-get install google-chrome-stable

# macOS:
brew install --cask google-chrome

# Windows:
# Descargar de: https://www.google.com/chrome/

# Instalar ChromeDriver:
# https://chromedriver.chromium.org/
# Debe coincidir con tu versión de Chrome
```

### **Error: "No driver available"**

- Todos los drivers están ocupados
- Espera a que se libere uno, o
- Aumenta `DRIVER_POOL_SIZE` en `.env`

```ini
# .env
DRIVER_POOL_SIZE=5  # Aumentar de 3 a 5
```

### **Tareas quedan en "PENDING"**

```bash
# Verificar que Celery worker está corriendo
python -m celery -A celery_app.celery_config inspect active

# Reiniciar worker (Windows):
# Cerrar ventana de Celery y ejecutar de nuevo:
python -m celery -A celery_app.celery_config worker --loglevel=info --pool=solo

# Docker:
docker-compose restart celery_worker
```

### **GPU warnings al iniciar Chrome**

Mensajes como estos son normales y no afectan el funcionamiento:

```
[WARNING]: GPU is not supported
DevToolsActivePort file doesn't exist
```

El scraper funciona correctamente con estos warnings.

---

## 📈 Escalabilidad

### **Escalar Workers**

```yaml
# docker-compose.yml
celery_worker_1:
  # ... config ...
  command: celery -A celery_app.celery_config worker --concurrency=3

celery_worker_2:
  # ... config ...
  command: celery -A celery_app.celery_config worker --concurrency=3

celery_worker_3:
  # ... config ...
  command: celery -A celery_app.celery_config worker --concurrency=3
```

Ahora puedes scrapear **9 perfiles simultáneamente** (3 workers × 3 concurrency)

### **Escalar en la Nube**

- Deploy workers en múltiples servidores
- Usar Redis en la nube (AWS ElastiCache, Redis Cloud)
- PostgreSQL en vez de SQLite

---

## 🔒 Seguridad

**TODO (para producción):**

- [ ] Agregar autenticación (Flask-Login)
- [ ] HTTPS con certificados SSL
- [ ] Rate limiting (Flask-Limiter)
- [ ] Validación de inputs (Pydantic)
- [ ] CSRF protection
- [ ] Secrets en vault (no en .env)

---

## 📝 Logs

Los logs se guardan en:

```
logs/
├── app.log          # Flask app logs
└── celery.log       # Celery worker logs
```

Ver logs en tiempo real:

```bash
# Docker
docker-compose logs -f web
docker-compose logs -f celery_worker

# Local
tail -f logs/app.log
```

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

---

## 📄 Licencia

MIT License - Ver `LICENSE` para más detalles

---

## 🎉 Créditos

Desarrollado con ❤️ por [Tu Nombre]

**Stack Tecnológico:**
- Flask (Web Framework)
- Celery (Async Tasks)
- Redis (Message Broker)
- Selenium (Web Scraping)
- BeautifulSoup (HTML Parsing)
- Docker (Containerization)

---

## 📞 Soporte

¿Problemas? Abre un [Issue](https://github.com/tu-usuario/twitter-scraper/issues)

---

**¡Feliz Scraping! 🚀**
