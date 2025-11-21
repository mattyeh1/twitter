"""
Cloudflare Tunnel Setup para Twitter Scraper
Expone tu aplicación local a internet de forma segura
"""

import subprocess
import sys
import os
import json

def check_cloudflared():
    """Verifica si cloudflared está instalado"""
    try:
        result = subprocess.run(['cloudflared', '--version'], 
                              capture_output=True, text=True)
        print(f"✓ Cloudflared instalado: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("✗ Cloudflared no está instalado")
        return False

def install_cloudflared_instructions():
    """Instrucciones para instalar cloudflared"""
    print("\n" + "="*60)
    print("INSTALAR CLOUDFLARED")
    print("="*60)
    print("\n📥 WINDOWS:")
    print("   1. Descarga desde:")
    print("      https://github.com/cloudflare/cloudflared/releases/latest")
    print("   2. Busca: cloudflared-windows-amd64.exe")
    print("   3. Renómbralo a: cloudflared.exe")
    print("   4. Muévelo a este directorio o a C:\\Windows\\System32")
    print("\n📥 ALTERNATIVA - Con winget:")
    print("   winget install --id Cloudflare.cloudflared")
    print("\n📥 LINUX:")
    print("   wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64")
    print("   sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared")
    print("   sudo chmod +x /usr/local/bin/cloudflared")
    print("="*60)

def login_cloudflare():
    """Inicia sesión en Cloudflare"""
    print("\n🔐 Iniciando sesión en Cloudflare...")
    print("Se abrirá tu navegador para autenticarte")
    
    try:
        subprocess.run(['cloudflared', 'tunnel', 'login'], check=True)
        print("✓ Sesión iniciada correctamente")
        return True
    except subprocess.CalledProcessError:
        print("✗ Error al iniciar sesión")
        return False
    except FileNotFoundError:
        print("✗ cloudflared no encontrado")
        return False

def create_tunnel(tunnel_name="twitter-scraper"):
    """Crea un nuevo tunnel"""
    print(f"\n🌐 Creando tunnel '{tunnel_name}'...")
    
    try:
        result = subprocess.run(
            ['cloudflared', 'tunnel', 'create', tunnel_name],
            capture_output=True,
            text=True,
            check=True
        )
        print("✓ Tunnel creado:")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        if "tunnel already exists" in e.stderr.lower():
            print(f"⚠️  Tunnel '{tunnel_name}' ya existe")
            return True
        print(f"✗ Error creando tunnel: {e.stderr}")
        return False

def list_tunnels():
    """Lista todos los tunnels"""
    print("\n📋 Tus tunnels:")
    try:
        result = subprocess.run(
            ['cloudflared', 'tunnel', 'list'],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
    except subprocess.CalledProcessError:
        print("✗ Error listando tunnels")

def create_config_file(tunnel_name="twitter-scraper", local_port=5000):
    """Crea el archivo de configuración"""
    
    # Obtener el tunnel UUID
    try:
        result = subprocess.run(
            ['cloudflared', 'tunnel', 'list'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parsear para obtener UUID
        lines = result.stdout.split('\n')
        tunnel_id = None
        for line in lines:
            if tunnel_name in line:
                parts = line.split()
                if parts:
                    tunnel_id = parts[0]
                    break
        
        if not tunnel_id:
            print("✗ No se pudo obtener el ID del tunnel")
            return False
        
        print(f"✓ Tunnel ID: {tunnel_id}")
        
    except subprocess.CalledProcessError:
        print("✗ Error obteniendo tunnel ID")
        return False
    
    # Crear directorio .cloudflared si no existe
    cloudflared_dir = os.path.expanduser('~/.cloudflared')
    if sys.platform == 'win32':
        cloudflared_dir = os.path.join(os.getenv('USERPROFILE'), '.cloudflared')
    
    os.makedirs(cloudflared_dir, exist_ok=True)
    
    # Crear config.yml
    config_path = os.path.join(cloudflared_dir, 'config.yml')
    
    config_content = f"""tunnel: {tunnel_id}
credentials-file: {os.path.join(cloudflared_dir, tunnel_id + '.json')}

ingress:
  - hostname: {tunnel_name}.cfargotunnel.com
    service: http://localhost:{local_port}
  - service: http_status:404
"""
    
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    print(f"✓ Archivo de configuración creado: {config_path}")
    print("\n📝 Contenido:")
    print(config_content)
    return True

def route_dns(tunnel_name="twitter-scraper", domain=None):
    """Configura el DNS para el tunnel"""
    
    if not domain:
        print("\n🌐 Configuración de DNS")
        print("="*60)
        print("Opciones:")
        print(f"1. Usar subdomain gratuito: {tunnel_name}.cfargotunnel.com")
        print("2. Usar tu propio dominio (debes tenerlo en Cloudflare)")
        choice = input("\nElige (1 o 2): ").strip()
        
        if choice == "2":
            domain = input("Ingresa tu dominio (ej: twitter.midominio.com): ").strip()
        else:
            domain = f"{tunnel_name}.cfargotunnel.com"
    
    print(f"\n🔗 Configurando DNS para: {domain}")
    
    try:
        subprocess.run(
            ['cloudflared', 'tunnel', 'route', 'dns', tunnel_name, domain],
            check=True
        )
        print(f"✓ DNS configurado correctamente")
        print(f"\n🎉 Tu aplicación estará disponible en:")
        print(f"   https://{domain}")
        return domain
    except subprocess.CalledProcessError as e:
        print(f"✗ Error configurando DNS")
        return None

def create_run_script(tunnel_name="twitter-scraper"):
    """Crea scripts para ejecutar el tunnel"""
    
    # Script de Windows
    bat_content = f"""@echo off
title Cloudflare Tunnel - {tunnel_name}
color 0A
echo ========================================
echo Cloudflare Tunnel - {tunnel_name}
echo ========================================
echo.
echo Iniciando tunnel...
echo Presiona Ctrl+C para detener
echo ========================================
echo.

cloudflared tunnel run {tunnel_name}

pause
"""
    
    with open('start_tunnel.bat', 'w') as f:
        f.write(bat_content)
    
    print("✓ Script 'start_tunnel.bat' creado")
    
    # Script para ejecutar todo junto
    all_in_one = f"""@echo off
title Twitter Scraper - All Services
color 0B

echo ========================================
echo Twitter Scraper - Starting All Services
echo ========================================
echo.

REM Iniciar Flask App
echo [1/3] Iniciando Flask App...
start "Flask App" cmd /k "python app.py"
timeout /t 3 /nobreak

REM Iniciar Scraper Daemon
echo [2/3] Iniciando Scraper Daemon...
start "Scraper Daemon" cmd /k "python background_scraper.py"
timeout /t 3 /nobreak

REM Iniciar Cloudflare Tunnel
echo [3/3] Iniciando Cloudflare Tunnel...
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel run {tunnel_name}"

echo.
echo ========================================
echo ✓ Todos los servicios iniciados
echo ========================================
echo.
echo Flask App: http://localhost:5000
echo Tunnel: https://{tunnel_name}.cfargotunnel.com
echo.
echo Cierra esta ventana cuando termines
pause
"""
    
    with open('start_all_services.bat', 'w') as f:
        f.write(all_in_one)
    
    print("✓ Script 'start_all_services.bat' creado")
    print("\n💡 Uso:")
    print("   - start_tunnel.bat: Solo el tunnel")
    print("   - start_all_services.bat: Todo junto (App + Daemon + Tunnel)")

def install_as_service(tunnel_name="twitter-scraper"):
    """Instala el tunnel como servicio de Windows"""
    print("\n⚙️  INSTALAR COMO SERVICIO DE WINDOWS")
    print("="*60)
    print("\n1. Abrir CMD como Administrador")
    print("\n2. Ejecutar:")
    print(f"   cloudflared service install")
    print("\n3. El tunnel se ejecutará automáticamente al iniciar Windows")
    print("\n4. Para detener:")
    print("   cloudflared service uninstall")
    print("="*60)

def main():
    print("\n" + "="*60)
    print("🌐 CLOUDFLARE TUNNEL SETUP")
    print("Twitter Scraper Web App")
    print("="*60)
    
    tunnel_name = input("\nNombre del tunnel (default: twitter-scraper): ").strip()
    if not tunnel_name:
        tunnel_name = "twitter-scraper"
    
    port = input("Puerto local de Flask (default: 5000): ").strip()
    if not port:
        port = "5000"
    
    # Verificar cloudflared
    if not check_cloudflared():
        install_cloudflared_instructions()
        print("\n⚠️  Instala cloudflared y vuelve a ejecutar este script")
        return
    
    # Menu
    print("\n" + "="*60)
    print("¿Qué deseas hacer?")
    print("="*60)
    print("\n1. Setup completo (Primera vez)")
    print("2. Solo crear scripts de ejecución")
    print("3. Ver tunnels existentes")
    print("4. Instalar como servicio de Windows")
    
    choice = input("\nElige (1-4): ").strip()
    
    if choice == "1":
        print("\n📋 SETUP COMPLETO")
        print("="*60)
        
        # Login
        if not login_cloudflare():
            return
        
        # Crear tunnel
        if not create_tunnel(tunnel_name):
            return
        
        # Crear config
        if not create_config_file(tunnel_name, int(port)):
            return
        
        # Configurar DNS
        domain = route_dns(tunnel_name)
        
        # Crear scripts
        create_run_script(tunnel_name)
        
        print("\n" + "="*60)
        print("✅ SETUP COMPLETADO")
        print("="*60)
        print("\n🚀 Próximos pasos:")
        print(f"\n1. Inicia Flask: python app.py")
        print(f"2. Inicia Tunnel: start_tunnel.bat")
        print(f"   O ejecuta todo: start_all_services.bat")
        print(f"\n3. Accede desde internet: https://{domain or tunnel_name + '.cfargotunnel.com'}")
        print("\n💡 Tip: Usa 'start_all_services.bat' para iniciar todo de una vez")
        print("="*60)
        
    elif choice == "2":
        create_run_script(tunnel_name)
        print("\n✓ Scripts creados")
        
    elif choice == "3":
        list_tunnels()
        
    elif choice == "4":
        install_as_service(tunnel_name)
    
    else:
        print("Opción inválida")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelado")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()