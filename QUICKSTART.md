# 🚀 Quick Start Guide

## Inicio Rápido (5 minutos)

### Opción A: Docker (Más Fácil)

```bash
# 1. Copiar configuración
cp .env.example .env

# 2. Iniciar todo
docker-compose up -d

# 3. Abrir en navegador
# http://localhost:5000
```

### Opción B: Local

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Instalar Redis
# Ubuntu: sudo apt-get install redis-server
# macOS: brew install redis
# Windows: https://github.com/microsoftarchive/redis/releases

# 3. Iniciar
./start_local.sh      # Linux/Mac
start_local.bat       # Windows
```

---

## ✅ Verificar que Funciona

### 1. Acceder al Dashboard
Abre: http://localhost:5000

### 2. Agregar un Perfil
- Click en "Agregar Nuevo Perfil"
- Username: `elonmusk` (sin @)
- Intervalo: `12` horas
- Click "Agregar Perfil"

### 3. Scrapear
- Click "🚀 Scrapear Ahora" en @elonmusk
- Verás progreso en tiempo real (esquina superior derecha)
- En ~2 minutos, verás los tweets

### 4. Ver Resultados
- Click "👁 Ver Tweets" para ver los tweets scrapeados
- O usa "Buscar Tweets" para buscar por palabras clave

---

## 🎯 Probar Scraping Concurrente

Abre 3 navegadores/pestañas diferentes y haz click en "Scrapear Ahora" en diferentes perfiles **al mismo tiempo**.

Verás que:
- ✅ Los 3 scrapings corren **en paralelo**
- ✅ Cada uno tiene su propio driver
- ✅ No hay conflictos

**Antes**: Solo 1 a la vez, los demás esperaban
**Ahora**: Hasta 3 simultáneos (configurable)

---

## 📊 Monitoreo

### Dashboard del Sistema
http://localhost:5000/monitoring

- Estado del pool de drivers
- Drivers activos vs disponibles
- Estadísticas de uso

### Flower (Celery Monitor)
http://localhost:5555

- Tareas en cola/activas/completadas
- Gráficos de performance
- Workers activos

---

## ⚙️ Configuración Rápida

### Más Scrapers Simultáneos

Editar `.env`:
```bash
DRIVER_POOL_SIZE=5  # Ahora hasta 5 simultáneos
```

Reiniciar:
```bash
docker-compose restart
# O Ctrl+C y ./start_local.sh
```

### Cambiar Puerto
```bash
# .env
FLASK_PORT=8080

# Ahora: http://localhost:8080
```

---

## 🐛 Solución de Problemas

### Redis no conecta
```bash
# Verificar
redis-cli ping

# Debe responder: PONG
```

### Celery no procesa tareas
```bash
# Ver logs
docker-compose logs celery_worker

# Reiniciar
docker-compose restart celery_worker
```

### Chrome no funciona
```bash
# Instalar Chrome
sudo apt-get install google-chrome-stable
```

---

## 📁 Archivos Importantes

```
.env                 # Configuración (copiar de .env.example)
run.py               # Iniciar aplicación
docker-compose.yml   # Todos los servicios
README.md            # Documentación completa
```

---

## 🎓 Siguiente Paso

Lee el [README.md](README.md) completo para:
- Arquitectura del sistema
- Cómo funciona el pool de drivers
- Escalabilidad
- Deployment en producción

---

**¡Listo! Ya tienes scraping concurrente profesional 🚀**
