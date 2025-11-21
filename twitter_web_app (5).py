"""
Twitter Scraper Web Application - app.py
"""

from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from flask_apscheduler import APScheduler
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime, timedelta
import time
import os
from threading import Lock

app = Flask(__name__)
scheduler = APScheduler()
scraper_lock = Lock()

# Usar ruta absoluta para la base de datos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'twitter_scraper.db')
CHROME_PROFILE = os.path.join(BASE_DIR, 'chrome_profile')
HEADLESS = True

class TwitterScraperService:
    def __init__(self):
        self.driver = None
        self.init_database()
    
    def init_database(self):
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    profile_url TEXT,
                    scrape_interval_hours INTEGER DEFAULT 12,
                    last_scraped TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tweets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER,
                    tweet_id TEXT UNIQUE,
                    tweet_text TEXT,
                    tweet_url TEXT,
                    author TEXT,
                    timestamp TEXT,
                    language TEXT,
                    likes INTEGER DEFAULT 0,
                    retweets INTEGER DEFAULT 0,
                    replies INTEGER DEFAULT 0,
                    is_retweet BOOLEAN DEFAULT 0,
                    original_author TEXT,
                    scraped_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles (id)
                )
            """)
            
            # Agregar columna is_retweet si no existe (para bases de datos existentes)
            try:
                cursor.execute("ALTER TABLE tweets ADD COLUMN is_retweet BOOLEAN DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # La columna ya existe
            
            # Agregar columna original_author si no existe (para bases de datos existentes)
            try:
                cursor.execute("ALTER TABLE tweets ADD COLUMN original_author TEXT")
            except sqlite3.OperationalError:
                pass  # La columna ya existe
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrape_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER,
                    status TEXT,
                    tweets_found INTEGER,
                    tweets_new INTEGER,
                    error_message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES profiles (id)
                )
            """)
            
            conn.commit()
            conn.close()
            print(f"Base de datos inicializada correctamente: {DATABASE}")
        except Exception as e:
            print(f"Error al inicializar base de datos: {e}")
            raise
    
    def init_driver(self):
        if self.driver:
            return
        
        chrome_options = Options()
        abs_profile = os.path.abspath(CHROME_PROFILE)
        chrome_options.add_argument(f'--user-data-dir={abs_profile}')
        
        if HEADLESS:
            chrome_options.add_argument('--headless=new')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--remote-debugging-port=9223')
        
        self.driver = webdriver.Chrome(options=chrome_options)
    
    def close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def extract_tweet_id(self, tweet_element):
        """Extrae el ID del tweet de múltiples formas"""
        try:
            # Método 1: Buscar enlaces con /status/
            links = tweet_element.find_all('a', href=lambda x: x and '/status/' in x)
            for link in links:
                href = link.get('href', '')
                if '/status/' in href:
                    tweet_id = href.split('/status/')[-1].split('?')[0].split('#')[0]
                    if tweet_id and tweet_id.isdigit():
                        return tweet_id
            
            # Método 2: Buscar en el atributo data-testid o data-tweet-id
            tweet_id_attr = tweet_element.get('data-tweet-id') or tweet_element.get('data-item-id')
            if tweet_id_attr:
                return str(tweet_id_attr)
            
            # Método 3: Buscar en cualquier elemento hijo
            for elem in tweet_element.find_all(['a', 'div', 'article']):
                href = elem.get('href', '')
                if '/status/' in href:
                    tweet_id = href.split('/status/')[-1].split('?')[0].split('#')[0]
                    if tweet_id and tweet_id.isdigit():
                        return tweet_id
                
                data_id = elem.get('data-tweet-id') or elem.get('data-item-id')
                if data_id:
                    return str(data_id)
        except Exception as e:
            print(f"Error extrayendo tweet_id: {e}")
        return None
    
    def extract_tweet_urls_from_dom_js(self, username):
        """
        Usa JavaScript para extraer todos los IDs de tweets directamente del DOM.
        Esto captura tweets cargados dinámicamente que no están en el HTML estático.
        """
        try:
            if not self.driver:
                return [], {}
            
            import re
            print("🔍 Extrayendo tweets del DOM usando JavaScript (DevTools)...")
            
            # JavaScript mejorado para extraer tweets de múltiples formas
            extract_js = """
            (function() {
                const tweetData = {};
                
                // Método 1: Buscar todos los enlaces con /status/
                const allLinks = document.querySelectorAll('a[href*="/status/"]');
                allLinks.forEach(link => {
                    const href = link.getAttribute('href');
                    if (href && href.includes('/status/')) {
                        // Extraer formato: /username/status/id
                        const match = href.match(/\\/([^/]+)\\/status\\/(\\d+)/);
                        if (match) {
                            const foundUsername = match[1];
                            const tweetId = match[2];
                            const fullPath = foundUsername + '/status/' + tweetId;
                            
                            if (!tweetData[tweetId]) {
                                tweetData[tweetId] = {
                                    username: foundUsername,
                                    full_path: fullPath,
                                    href: href
                                };
                            }
                        }
                    }
                });
                
                // Método 2: Buscar directamente en articles con data-testid='tweet'
                const articles = document.querySelectorAll('article[data-testid="tweet"]');
                articles.forEach(article => {
                    // Buscar enlaces dentro del article
                    const links = article.querySelectorAll('a[href*="/status/"]');
                    links.forEach(link => {
                        const href = link.getAttribute('href');
                        if (href && href.includes('/status/')) {
                            const match = href.match(/\\/([^/]+)\\/status\\/(\\d+)/);
                            if (match) {
                                const foundUsername = match[1];
                                const tweetId = match[2];
                                const fullPath = foundUsername + '/status/' + tweetId;
                                
                                if (!tweetData[tweetId]) {
                                    tweetData[tweetId] = {
                                        username: foundUsername,
                                        full_path: fullPath,
                                        href: href
                                    };
                                }
                            }
                        }
                    });
                });
                
                // Método 3: Buscar en cualquier elemento con href que contenga /status/
                const allElements = document.querySelectorAll('[href*="/status/"]');
                allElements.forEach(elem => {
                    const href = elem.getAttribute('href');
                    if (href && href.includes('/status/')) {
                        const match = href.match(/\\/([^/]+)\\/status\\/(\\d+)/);
                        if (match) {
                            const foundUsername = match[1];
                            const tweetId = match[2];
                            const fullPath = foundUsername + '/status/' + tweetId;
                            
                            if (!tweetData[tweetId]) {
                                tweetData[tweetId] = {
                                    username: foundUsername,
                                    full_path: fullPath,
                                    href: href
                                };
                            }
                        }
                    }
                });
                
                return tweetData;
            })();
            """
            
            tweet_data_dict = self.driver.execute_script(extract_js)
            if not tweet_data_dict:
                return [], {}
            
            tweet_ids = list(tweet_data_dict.keys())
            print(f"✓ JavaScript encontró {len(tweet_ids)} tweets en el DOM")
            
            return tweet_ids, tweet_data_dict
        except Exception as e:
            print(f"Error extrayendo tweets del DOM con JavaScript: {e}")
            import traceback
            traceback.print_exc()
            return [], {}
    
    def extract_tweet_urls_from_html(self, username):
        """
        Extrae todas las URLs de tweets del HTML completo del navegador.
        Extrae el formato: username/status/id del href
        Ejemplo: /XDevelopers/status/1991234245415534693 -> XDevelopers/status/1991234245415534693
        """
        try:
            import re
            # Obtener el HTML completo del navegador (como cuando abres DevTools)
            print("📋 Obteniendo HTML completo del navegador (como Inspector de Elementos)...")
            html_content = self.driver.page_source
            
            # Parsear el HTML completo con BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extraer todos los IDs de tweets del HTML con formato username/status/id
            tweet_data = {}  # {tweet_id: {'username': username, 'full_path': path}}
            
            # Método 1: Buscar todos los enlaces que contengan /status/
            print("🔍 Buscando enlaces con /status/ en el HTML...")
            all_links = soup.find_all('a', href=lambda x: x and '/status/' in str(x))
            print(f"   Encontrados {len(all_links)} enlaces con /status/")
            
            for link in all_links:
                href = link.get('href', '')
                if href and '/status/' in href:
                    # Extraer el formato: username/status/id
                    # Ejemplo: /XDevelopers/status/1991234245415534693
                    match = re.search(r'/([^/]+)/status/(\d+)', href)
                    if match:
                        found_username = match.group(1)
                        tweet_id = match.group(2)
                        # Guardar el formato completo: username/status/id
                        full_path = f"{found_username}/status/{tweet_id}"
                        tweet_data[tweet_id] = {
                            'username': found_username,
                            'full_path': full_path,
                            'href': href
                        }
            
            # Método 2: Buscar en articles con data-testid='tweet'
            print("🔍 Buscando articles con data-testid='tweet'...")
            articles = soup.find_all('article', attrs={'data-testid': 'tweet'})
            print(f"   Encontrados {len(articles)} articles")
            
            for article in articles:
                links = article.find_all('a', href=lambda x: x and '/status/' in str(x))
                for link in links:
                    href = link.get('href', '')
                    if href:
                        match = re.search(r'/([^/]+)/status/(\d+)', href)
                        if match:
                            found_username = match.group(1)
                            tweet_id = match.group(2)
                            full_path = f"{found_username}/status/{tweet_id}"
                            tweet_data[tweet_id] = {
                                'username': found_username,
                                'full_path': full_path,
                                'href': href
                            }
            
            # Método 3: Buscar directamente en el texto del HTML (último recurso)
            print("🔍 Buscando patrones username/status/id en el texto del HTML...")
            # Buscar patrones como /username/status/1234567890 en todo el HTML
            status_matches = re.findall(r'/([^/\s]+)/status/(\d{10,})', html_content)
            for found_username, tweet_id in status_matches:
                if tweet_id.isdigit():
                    full_path = f"{found_username}/status/{tweet_id}"
                    if tweet_id not in tweet_data:
                        tweet_data[tweet_id] = {
                            'username': found_username,
                            'full_path': full_path,
                            'href': f"/{full_path}"
                        }
            
            # Si no encontramos username en algunos tweets, usar el username del perfil
            for tweet_id, data in tweet_data.items():
                if not data.get('username'):
                    data['username'] = username
                    data['full_path'] = f"{username}/status/{tweet_id}"
            
            result = list(tweet_data.keys())
            print(f"✓ Total IDs únicos de tweets encontrados en HTML: {len(result)}")
            if result:
                # Mostrar algunos ejemplos del formato extraído
                examples = list(tweet_data.values())[:5]
                for ex in examples:
                    print(f"   Ejemplo: {ex['full_path']}")
            
            # Retornar también el diccionario con la información completa
            return result, tweet_data
        except Exception as e:
            print(f"Error extrayendo URLs de tweets del HTML: {e}")
            import traceback
            traceback.print_exc()
            return [], {}
    
    def extract_tweet_data_from_html(self, tweet_id, username, soup):
        """
        Extrae la información completa de un tweet del HTML completo.
        Busca el tweet por su ID en el HTML parseado y extrae texto, likes, retweets, etc.
        """
        import re
        try:
            # Buscar el article que contiene este tweet
            articles = soup.find_all('article', attrs={'data-testid': 'tweet'})
            
            for article in articles:
                # Buscar enlaces con este tweet_id
                links = article.find_all('a', href=lambda x: x and f'/status/{tweet_id}' in str(x))
                if links:
                    # Extraer texto del tweet
                    text_el = article.find('div', attrs={'data-testid': 'tweetText'})
                    text = ""
                    lang = ""
                    
                    if text_el:
                        # Buscar spans con lang para obtener el texto original
                        original_spans = text_el.find_all('span', attrs={'lang': True})
                        if original_spans:
                            text = ' '.join([s.get_text(strip=True) for s in original_spans if s.get_text(strip=True)])
                            lang = original_spans[0].get('lang', '') if original_spans else ''
                        else:
                            text = text_el.get_text(separator=' ', strip=True)
                        
                        # Obtener idioma
                        if not lang:
                            lang = text_el.get('lang', '')
                    
                    # Limpiar el texto
                    text = ' '.join(text.split()) if text else ""
                    
                    # DETECTAR SI ES UN RETWEET
                    is_retweet = False
                    original_author = None
                    
                    # Buscar indicadores de retweet en el article
                    article_text = article.get_text().lower()
                    
                    # Método 1: Buscar texto "retweeted" o "retuiteado"
                    if 'retweeted' in article_text or 'retuiteado' in article_text or 'retweet' in article_text:
                        is_retweet = True
                    
                    # Método 2: Buscar elementos con data-testid relacionados a retweet
                    retweet_indicators = article.find_all(attrs={'data-testid': lambda x: x and 'retweet' in str(x).lower()})
                    if retweet_indicators:
                        is_retweet = True
                    
                    # Método 3: Buscar iconos o elementos de retweet
                    retweet_icons = article.find_all('svg', attrs={'aria-label': lambda x: x and ('retweet' in str(x).lower() or 'repost' in str(x).lower())})
                    if retweet_icons:
                        is_retweet = True
                    
                    # Si es retweet, intentar extraer el autor original
                    if is_retweet:
                        # Buscar enlaces que puedan ser del autor original
                        # Generalmente está en un span o div cerca del inicio del article
                        author_links = article.find_all('a', href=lambda x: x and x.startswith('/') and not x.startswith('/status/'))
                        for link in author_links[:3]:  # Revisar los primeros 3 enlaces
                            href = link.get('href', '')
                            if href and not '/status/' in href and not '/i/' in href:
                                # Puede ser el autor original
                                author_match = re.search(r'/([^/]+)', href)
                                if author_match:
                                    potential_author = author_match.group(1)
                                    if potential_author and potential_author != username:
                                        original_author = potential_author
                                        break
                    
                    # Extraer métricas (likes, retweets, replies)
                    likes = retweets = replies = 0
                    buttons = article.find_all('button')
                    
                    for button in buttons:
                        aria = button.get('aria-label', '').lower()
                        if not aria:
                            continue
                        
                        # Extraer números del aria-label
                        digits = re.findall(r'\d+', aria)
                        if digits:
                            num = int(digits[0])
                            if 'like' in aria or 'me gusta' in aria:
                                likes = num
                            elif 'repost' in aria or 'retweet' in aria:
                                retweets = num
                            elif 'repl' in aria or 'respuesta' in aria:
                                replies = num
                    
                    return {
                        'tweet_id': tweet_id,
                        'text': text,
                        'likes': likes,
                        'retweets': retweets,
                        'replies': replies,
                        'language': lang,
                        'is_retweet': is_retweet,
                        'original_author': original_author,
                        'found': True
                    }
            
            return {'found': False}
        except Exception as e:
            print(f"Error extrayendo datos del tweet {tweet_id} del HTML: {e}")
            return {'found': False}
    
    def extract_tweet_data_from_dom_full(self, username):
        """
        Extrae datos completos de tweets directamente del DOM usando JavaScript.
        Esto captura tweets dinámicamente cargados con toda su información.
        """
        try:
            if not self.driver:
                return {}, []
            
            print("🔍 Extrayendo datos completos de tweets del DOM usando JavaScript...")
            
            extract_js = """
            (function() {
                const tweetData = {};
                const articles = document.querySelectorAll('article[data-testid="tweet"]');
                
                articles.forEach((article, index) => {
                    try {
                        // Buscar enlaces con /status/ para obtener el ID
                        const links = article.querySelectorAll('a[href*="/status/"]');
                        let tweetId = null;
                        let tweetUrl = null;
                        let foundUsername = null;
                        
                        for (let link of links) {
                            const href = link.getAttribute('href');
                            if (href && href.includes('/status/')) {
                                const match = href.match(/\\/([^/]+)\\/status\\/(\\d+)/);
                                if (match) {
                                    foundUsername = match[1];
                                    tweetId = match[2];
                                    tweetUrl = href.startsWith('http') ? href : 'https://x.com' + href;
                                    break;
                                }
                            }
                        }
                        
                        if (!tweetId) {
                            return; // Saltar si no encontramos ID
                        }
                        
                        // Extraer texto del tweet
                        let text = '';
                        let lang = '';
                        const textDiv = article.querySelector('div[data-testid="tweetText"]');
                        if (textDiv) {
                            // Buscar spans con lang para obtener el texto original
                            const spans = textDiv.querySelectorAll('span[lang]');
                            if (spans.length > 0) {
                                text = Array.from(spans).map(s => s.textContent).join(' ').trim();
                                lang = spans[0].getAttribute('lang') || '';
                            } else {
                                text = textDiv.textContent.trim();
                            }
                        }
                        
                        // Extraer métricas (likes, retweets, replies)
                        let likes = 0, retweets = 0, replies = 0;
                        const buttons = article.querySelectorAll('button');
                        buttons.forEach(button => {
                            const ariaLabel = button.getAttribute('aria-label') || '';
                            const digits = ariaLabel.match(/\\d+/);
                            if (digits) {
                                const num = parseInt(digits[0]);
                                if (ariaLabel.toLowerCase().includes('like') || ariaLabel.toLowerCase().includes('me gusta')) {
                                    likes = num;
                                } else if (ariaLabel.toLowerCase().includes('repost') || ariaLabel.toLowerCase().includes('retweet')) {
                                    retweets = num;
                                } else if (ariaLabel.toLowerCase().includes('repl') || ariaLabel.toLowerCase().includes('respuesta')) {
                                    replies = num;
                                }
                            }
                        });
                        
                        // Detectar si es retweet
                        let isRetweet = false;
                        let originalAuthor = null;
                        const articleText = article.textContent.toLowerCase();
                        if (articleText.includes('retweeted') || articleText.includes('retuiteado') || articleText.includes('retweet')) {
                            isRetweet = true;
                            // Intentar encontrar el autor original
                            const authorLinks = article.querySelectorAll('a[href^="/"]');
                            for (let link of authorLinks) {
                                const href = link.getAttribute('href');
                                if (href && !href.includes('/status/') && !href.includes('/i/')) {
                                    const match = href.match(/\\/([^/]+)/);
                                    if (match && match[1] !== foundUsername) {
                                        originalAuthor = match[1];
                                        break;
                                    }
                                }
                            }
                        }
                        
                        if (text && text.length > 10) {
                            tweetData[tweetId] = {
                                username: foundUsername || '""" + username + """',
                                full_path: (foundUsername || '""" + username + """') + '/status/' + tweetId,
                                href: tweetUrl || 'https://x.com/' + (foundUsername || '""" + username + """') + '/status/' + tweetId,
                                text: text,
                                language: lang,
                                likes: likes,
                                retweets: retweets,
                                replies: replies,
                                is_retweet: isRetweet,
                                original_author: originalAuthor
                            };
                        }
                    } catch (e) {
                        console.error('Error procesando article:', e);
                    }
                });
                
                return tweetData;
            })();
            """
            
            tweet_data_dict = self.driver.execute_script(extract_js)
            if not tweet_data_dict:
                return {}, []
            
            tweet_ids = list(tweet_data_dict.keys())
            print(f"✓ JavaScript extrajo datos completos de {len(tweet_ids)} tweets del DOM")
            
            return tweet_data_dict, tweet_ids
        except Exception as e:
            print(f"Error extrayendo datos completos del DOM: {e}")
            import traceback
            traceback.print_exc()
            return {}, []
    
    def scrape_tweet_directly(self, username, tweet_id):
        """Intenta acceder directamente a un tweet específico"""
        url = f"https://x.com/{username}/status/{tweet_id}"
        try:
            if not self.driver:
                self.init_driver()
            self.driver.get(url)
            print(f"Accediendo directamente al tweet {tweet_id}...")
            time.sleep(8)
            
            if "login" in self.driver.current_url or "i/flow/login" in self.driver.current_url:
                return None
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            tweet_elements = soup.find_all('article', attrs={'data-testid': 'tweet'})
            
            if tweet_elements:
                return tweet_elements[0]  # Retornar el primer tweet (el principal)
            return None
        except Exception as e:
            print(f"Error accediendo al tweet directamente: {e}")
        return None
    
    def scrape_profile(self, username, max_tweets=100):
        """
        Scrapea el perfil de un usuario de X/Twitter y captura los tweets más recientes.
        
        Estrategia:
        1. Carga la página del perfil
        2. Espera a que carguen los tweets más recientes (que aparecen al principio)
        3. Hace scrolls para cargar más tweets
        4. Vuelve arriba para procesar desde los más recientes
        5. Procesa los tweets en orden (más recientes primero)
        """
        url = f"https://x.com/{username}"
        
        try:
            # Verificar y inicializar el driver
            if not self.driver:
                self.init_driver()
            
            # Verificar que el driver esté activo
            try:
                _ = self.driver.current_url
            except:
                print("⚠ Driver cerrado, reinicializando...")
                self.init_driver()
            
            self.driver.get(url)
            print(f"Esperando carga inicial de @{username}...")
            time.sleep(8)
            
            # Verificar autenticación
            if "login" in self.driver.current_url or "i/flow/login" in self.driver.current_url:
                return {"status": "error", "message": "Requiere autenticacion"}
        
            # Esperar a que aparezcan los primeros tweets usando WebDriverWait
            print(f"Esperando tweets iniciales...")
            wait = WebDriverWait(self.driver, 20)
            try:
                # Intentar esperar a que aparezca al menos un tweet
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='tweet']")))
                print("✓ Tweets detectados en la página")
            except:
                print("⚠ No se detectaron tweets con data-testid='tweet', continuando...")
                # Intentar esperar cualquier article
                try:
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
                    print("✓ Se encontraron elementos <article>")
                except:
                    print("⚠ No se encontraron elementos <article>, la página puede estar vacía o bloqueada")
            
            # IMPORTANTE: Esperar más tiempo para que carguen los tweets MÁS RECIENTES al principio
            print(f"Esperando carga completa de tweets recientes...")
            time.sleep(12)  # Espera adicional para tweets recientes (aumentado de 8 a 12)
            
            # Verificar que hay tweets antes de continuar
            try:
                tweet_count_check = self.driver.execute_script("""
                    return document.querySelectorAll('article[data-testid="tweet"]').length;
                """)
                print(f"📊 Tweets detectados después de espera inicial: {tweet_count_check}")
                if tweet_count_check == 0:
                    print("⚠ No se detectaron tweets, esperando más tiempo...")
                    time.sleep(10)
                    tweet_count_check = self.driver.execute_script("""
                        return document.querySelectorAll('article[data-testid="tweet"]').length;
                    """)
                    print(f"📊 Tweets después de espera adicional: {tweet_count_check}")
            except Exception as e:
                print(f"⚠ Error verificando tweets iniciales: {e}")
            
            # Hacer algunos scrolls pequeños al principio para asegurar que se carguen los más recientes
            print(f"Haciendo scrolls iniciales suaves para cargar tweets recientes...")
            for i in range(3):  # Aumentado de 2 a 3
                try:
                    self.driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(3)  # Aumentado de 2 a 3
                except Exception as e:
                    print(f"⚠ Error en scroll inicial {i+1}: {e}")
                    break
            
            # Volver arriba inmediatamente para capturar los más recientes
            try:
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(8)  # Aumentado de 5 a 8 para dar más tiempo
            except Exception as e:
                print(f"⚠ Error volviendo arriba: {e}")
            
            # Hacer scrolls progresivos hacia abajo para cargar más tweets
            print(f"Haciendo scrolls hacia abajo para cargar más tweets...")
            last_height = 0
            scroll_attempts = 0
            max_scrolls = 15  # Aumentado de 10 a 15
            
            for i in range(max_scrolls):
                try:
                    # Verificar que el driver esté activo
                    _ = self.driver.current_url
                    
                    # Scroll hacia abajo
                    self.driver.execute_script("window.scrollBy(0, 1000);")
                    time.sleep(6)  # Aumentado de 4 a 6 para dar más tiempo de carga
                    
                    # Verificar si hay nuevos tweets
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        scroll_attempts += 1
                        if scroll_attempts >= 3:
                            print(f"  No hay más contenido, deteniendo scrolls")
                            break
                    else:
                        scroll_attempts = 0
                        last_height = new_height
                    
                    # Verificar cuántos tweets hay en el DOM
                    current_count = self.driver.execute_script("""
                        return document.querySelectorAll('article[data-testid="tweet"]').length;
                    """)
                    print(f"  Scroll {i+1}/{max_scrolls} - Altura: {new_height} - Tweets: {current_count}")
                except Exception as e:
                    print(f"  Error en scroll {i+1}: {e}")
                    # Si el driver se cerró, intentar reinicializar
                    try:
                        _ = self.driver.current_url
                    except:
                        print("⚠ Driver cerrado durante scroll, reinicializando...")
                        self.init_driver()
                        self.driver.get(url)
                        time.sleep(5)
                    break
            
            # Volver al inicio para procesar desde los más recientes
            print(f"Volviendo al inicio para procesar tweets recientes...")
            try:
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(10)  # Aumentado de 5 a 10 para dar más tiempo
                
                # Hacer algunos scrolls pequeños adicionales para activar carga
                for i in range(3):
                    self.driver.execute_script("window.scrollBy(0, 300);")
                    time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(5)
            except Exception as e:
                print(f"⚠ Error volviendo arriba: {e}")
            
            # Debug: Verificar el estado de la página
            try:
                print(f"URL actual: {self.driver.current_url}")
                print(f"Título de la página: {self.driver.title}")
                
                # Verificar cuántos tweets hay antes de extraer
                tweet_count_before = self.driver.execute_script("""
                    return document.querySelectorAll('article[data-testid="tweet"]').length;
                """)
                print(f"📊 Tweets visibles en DOM antes de extraer: {tweet_count_before}")
                
                # Si no hay tweets, esperar un poco más
                if tweet_count_before == 0:
                    print("⚠ No se detectaron tweets, esperando más tiempo antes de extraer...")
                    time.sleep(10)
                    tweet_count_before = self.driver.execute_script("""
                        return document.querySelectorAll('article[data-testid="tweet"]').length;
                    """)
                    print(f"📊 Tweets después de espera adicional: {tweet_count_before}")
            except Exception as e:
                print(f"⚠ Error verificando estado: {e}")
            
            # ESTRATEGIA MEJORADA: Extraer datos completos directamente del DOM
            print(f"🔍 Extrayendo datos completos de tweets del DOM...")
            tweet_data_dict_full, tweet_ids_full = self.extract_tweet_data_from_dom_full(username)
            
            # También extraer IDs usando el método anterior como respaldo
            tweet_ids_js, tweet_data_dict_js = self.extract_tweet_urls_from_dom_js(username)
            
            # También extraer del HTML estático como respaldo adicional
            print(f"📋 También extrayendo del HTML estático como respaldo...")
            soup = None
            try:
                html_content = self.driver.page_source
                print(f"✓ HTML obtenido: {len(html_content)} caracteres")
                soup = BeautifulSoup(html_content, 'html.parser')
                tweet_ids_html, tweet_data_dict_html = self.extract_tweet_urls_from_html(username)
            except Exception as e:
                print(f"⚠ Error extrayendo del HTML: {e}")
                tweet_ids_html = []
                tweet_data_dict_html = {}
            
            # COMBINAR: Priorizar datos completos del DOM, luego IDs, luego HTML
            tweet_data_dict = {}
            tweet_data_dict.update(tweet_data_dict_html)  # Primero HTML (solo IDs y paths)
            tweet_data_dict.update(tweet_data_dict_js)    # Luego JavaScript (IDs y paths)
            tweet_data_dict.update(tweet_data_dict_full)  # Finalmente datos completos (sobrescribe todo)
            
            # Combinar IDs únicos de todas las fuentes (asegurar que sean listas)
            if not isinstance(tweet_ids_full, list):
                tweet_ids_full = list(tweet_ids_full) if tweet_ids_full else []
            if not isinstance(tweet_ids_js, list):
                tweet_ids_js = list(tweet_ids_js) if tweet_ids_js else []
            if not isinstance(tweet_ids_html, list):
                tweet_ids_html = list(tweet_ids_html) if tweet_ids_html else []
            
            all_tweet_ids = list(set(tweet_ids_full + tweet_ids_js + tweet_ids_html))
            
            print(f"✓ Datos completos del DOM: {len(tweet_ids_full)} tweets")
            print(f"✓ JavaScript encontró: {len(tweet_ids_js)} tweets")
            print(f"✓ HTML estático encontró: {len(tweet_ids_html)} tweets")
            print(f"✓ Total único combinado: {len(all_tweet_ids)} tweets")
            
            if not all_tweet_ids:
                print("⚠ No se encontraron tweets")
                # Verificar si el perfil existe en la BD antes de retornar
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM profiles WHERE username = ?", (username,))
                result = cursor.fetchone()
                profile_id = result[0] if result else None
                conn.close()
                
                error_msg = "No se encontraron tweets en el DOM. Posibles causas: "
                error_msg += "1) La página requiere más tiempo de carga, "
                error_msg += "2) El perfil está protegido/privado, "
                error_msg += "3) X/Twitter cambió su estructura, "
                error_msg += "4) Requiere autenticación adicional"
                
                if profile_id:
                    conn = sqlite3.connect(DATABASE)
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO scrape_logs (profile_id, status, error_message)
                        VALUES (?, ?, ?)
                    """, (profile_id, 'error', error_msg))
                    conn.commit()
                    conn.close()
                
                return {"status": "error", "message": error_msg}
            
            if tweet_data_dict:
                # Mostrar algunos ejemplos del formato extraído
                examples = list(tweet_data_dict.values())[:5]
                for ex in examples:
                    print(f"   Formato extraído: {ex.get('full_path', 'N/A')}")
            
            # Usar los datos completos del DOM si están disponibles, sino usar IDs
            if tweet_ids_full:
                tweet_ids = tweet_ids_full[:max_tweets]
                print(f"Procesando {len(tweet_ids)} tweets desde datos completos del DOM...")
            elif tweet_ids_js:
                tweet_ids = tweet_ids_js[:max_tweets]
                print(f"Procesando {len(tweet_ids)} tweets desde IDs del DOM...")
            else:
                tweet_ids = all_tweet_ids[:max_tweets]
                print(f"Procesando {len(tweet_ids)} tweets desde todas las fuentes...")
            
            # Conectar a la base de datos
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM profiles WHERE username = ?", (username,))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return {"status": "error", "message": "Perfil no encontrado en la base de datos"}
            profile_id = result[0]
        
            # Procesar tweets usando datos extraídos del DOM
            tweets_found = 0
            tweets_new = 0
            seen_ids = set()
            
            print(f"Procesando {len(tweet_ids)} tweets...")
            for idx, tweet_id in enumerate(tweet_ids):
                try:
                    # Verificar duplicados en esta sesión
                    if tweet_id in seen_ids:
                        if idx < 5:
                            print(f"  Tweet {idx+1}: ID duplicado en sesión (ID: {tweet_id})")
                        continue
                    seen_ids.add(tweet_id)
                    
                    # Verificar si ya existe en BD
                    cursor.execute("SELECT id FROM tweets WHERE tweet_id = ?", (tweet_id,))
                    if cursor.fetchone():
                        if idx < 10:  # Mostrar los primeros 10 para debug
                            print(f"  Tweet {idx+1}: Ya existe en BD (ID: {tweet_id})")
                        continue
                    
                    # Usar datos completos del DOM si están disponibles
                    if tweet_id in tweet_data_dict_full:
                        tweet_data = tweet_data_dict_full[tweet_id]
                        text = tweet_data.get('text', '').strip()
                        lang = tweet_data.get('language', '')
                        likes = tweet_data.get('likes', 0)
                        retweets = tweet_data.get('retweets', 0)
                        replies = tweet_data.get('replies', 0)
                        is_retweet = tweet_data.get('is_retweet', False)
                        original_author = tweet_data.get('original_author', None)
                        tweet_url = tweet_data.get('href', f"https://x.com/{username}/status/{tweet_id}")
                    else:
                        # Intentar extraer del HTML como respaldo
                        if soup:
                            tweet_data = self.extract_tweet_data_from_html(tweet_id, username, soup)
                            if not tweet_data or not tweet_data.get('found'):
                                if idx < 5:
                                    print(f"  Tweet {idx+1} (ID: {tweet_id}): No se encontró en el HTML")
                                continue
                            text = tweet_data.get('text', '').strip()
                            lang = tweet_data.get('language', '')
                            likes = tweet_data.get('likes', 0)
                            retweets = tweet_data.get('retweets', 0)
                            replies = tweet_data.get('replies', 0)
                            is_retweet = tweet_data.get('is_retweet', False)
                            original_author = tweet_data.get('original_author', None)
                            tweet_url = f"https://x.com/{username}/status/{tweet_id}"
                        else:
                            if idx < 5:
                                print(f"  Tweet {idx+1} (ID: {tweet_id}): No hay datos disponibles")
                            continue
                    
                    # Validar texto
                    if not text or len(text) < 10:
                        if idx < 5:
                            print(f"  Tweet {idx+1} (ID: {tweet_id}): Texto muy corto o vacío")
                        continue
                    
                    if "Traducido de" in text or "Translated from" in text:
                        continue
                    
                    tweets_found += 1
                    
                    # Insertar en la base de datos
                    cursor.execute("""
                        INSERT INTO tweets (profile_id, tweet_id, tweet_text, tweet_url, author, timestamp, language, likes, retweets, replies, is_retweet, original_author)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        profile_id, tweet_id, text, tweet_url, username, datetime.now().isoformat(), lang, likes, retweets, replies, is_retweet, original_author
                    ))
                    tweets_new += 1
                    
                    # Mostrar si es RT
                    rt_indicator = " [RT]" if is_retweet else ""
                    if is_retweet and original_author:
                        rt_indicator = f" [RT de @{original_author}]"
                    print(f" ✓ Tweet {tweets_new} NUEVO{rt_indicator} (ID: {tweet_id}): {text[:60]}...")
                except Exception as e:
                    print(f" Error procesando tweet {idx+1} (ID: {tweet_id}): {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
            cursor.execute(
                "UPDATE profiles SET last_scraped = ? WHERE id = ?",
                (datetime.now().isoformat(), profile_id)
            )
            cursor.execute("""
                INSERT INTO scrape_logs (profile_id, status, tweets_found, tweets_new)
                VALUES (?, ?, ?, ?)
            """, (profile_id, 'success', tweets_found, tweets_new))
            conn.commit()
            conn.close()
            print(f"Resultado: {tweets_new} nuevos de {tweets_found} procesados")
            return {
                "status": "success",
                "tweets_found": tweets_found,
                "tweets_new": tweets_new
            }
        except Exception as e:
            print(f"Error en scrape_profile: {e}")
            import traceback
            traceback.print_exc()
            
            # Intentar reinicializar el driver si hay error de conexión
            if "Connection" in str(e) or "HTTPConnectionPool" in str(e) or "Failed to establish" in str(e) or "denegó expresamente" in str(e):
                print("⚠ Error de conexión con el driver, intentando reinicializar...")
                try:
                    if self.driver:
                        try:
                            self.driver.quit()
                        except:
                            pass
                    self.driver = None
                    self.init_driver()
                    print("✓ Driver reinicializado")
                except Exception as e2:
                    print(f"⚠ Error reinicializando driver: {e2}")
            
            try:
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM profiles WHERE username = ?", (username,))
                result = cursor.fetchone()
                if result:
                    cursor.execute("""
                        INSERT INTO scrape_logs (profile_id, status, error_message)
                        VALUES (?, ?, ?)
                    """, (result[0], 'error', str(e)))
                    conn.commit()
                conn.close()
            except:
                pass
            return {"status": "error", "message": str(e)}

scraper = TwitterScraperService()

def ensure_database():
    """Asegura que la base de datos esté inicializada"""
    try:
        scraper.init_database()
    except Exception as e:
        print(f"Error inicializando base de datos: {e}")

# Asegurar inicialización de la base de datos al cargar el módulo
ensure_database()

def scheduled_scrape_job():
    with scraper_lock:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, scrape_interval_hours, last_scraped
            FROM profiles
            WHERE is_active = 1
        """)
        
        profiles = cursor.fetchall()
        conn.close()
        
        for profile_id, username, interval_hours, last_scraped in profiles:
            if last_scraped:
                last_time = datetime.fromisoformat(last_scraped)
                if datetime.now() - last_time < timedelta(hours=interval_hours):
                    continue
            
            print(f"Scraping scheduled: @{username}")
            result = scraper.scrape_profile(username)
            print(f"Result: {result}")
            time.sleep(10)
        
        scraper.close_driver()

HOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Twitter Scraper Dashboard</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 30px;
        }
        h1 { color: #333; font-size: 2.5em; margin-bottom: 10px; }
        .subtitle { color: #666; font-size: 1.1em; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        .stat-label {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .section {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 30px;
        }
        h2 {
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        .form-group { margin-bottom: 20px; }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 500;
        }
        input[type="text"], input[type="number"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1em;
            transition: border 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th {
            background: #f8f9fa;
            color: #333;
            font-weight: 600;
        }
        tr:hover { background: #f8f9fa; }
        .badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }
        .badge-active {
            background: #d4edda;
            color: #155724;
        }
        .badge-inactive {
            background: #f8d7da;
            color: #721c24;
        }
        .btn-small {
            padding: 6px 15px;
            font-size: 0.9em;
            margin-right: 5px;
        }
        .btn-danger { background: #dc3545; }
        .btn-success { background: #28a745; }
        .search-link {
            background: #1da1f2;
            color: white;
            padding: 12px 30px;
            border-radius: 25px;
            text-decoration: none;
            display: inline-block;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Twitter Scraper Dashboard</h1>
            <p class="subtitle">Gestiona el scraping automatico de perfiles de X/Twitter</p>
            <a href="/search" class="search-link">Buscar Tweets</a>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{{ stats.total_profiles }}</div>
                <div class="stat-label">Perfiles</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.active_profiles }}</div>
                <div class="stat-label">Activos</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.total_tweets }}</div>
                <div class="stat-label">Tweets</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.today_tweets }}</div>
                <div class="stat-label">Hoy</div>
            </div>
        </div>

        <div class="section">
            <h2>Agregar Nuevo Perfil</h2>
            <form method="POST" action="/add_profile">
                <div class="form-group">
                    <label>Username (sin @)</label>
                    <input type="text" name="username" placeholder="ejemplo: jmilei" required>
                </div>
                <div class="form-group">
                    <label>Intervalo de scraping (horas)</label>
                    <input type="number" name="interval" value="12" min="1" max="168" required>
                </div>
                <button type="submit">Agregar Perfil</button>
            </form>
        </div>

        <div class="section">
            <h2>Perfiles Monitoreados</h2>
            <table>
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Intervalo</th>
                        <th>Ultimo Scrape</th>
                        <th>Tweets</th>
                        <th>Estado</th>
                        <th>Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    {% for profile in profiles %}
                    <tr>
                        <td><strong>@{{ profile.username }}</strong></td>
                        <td>{{ profile.scrape_interval_hours }}h</td>
                        <td>{{ profile.last_scraped or 'Nunca' }}</td>
                        <td>{{ profile.tweet_count }}</td>
                        <td>
                            {% if profile.is_active %}
                            <span class="badge badge-active">Activo</span>
                            {% else %}
                            <span class="badge badge-inactive">Inactivo</span>
                            {% endif %}
                        </td>
                        <td>
                            <button class="btn-small btn-success" onclick="scrapeNow('{{ profile.username }}')">Scrapear Ahora</button>
                            <button class="btn-small" onclick="viewTweets('{{ profile.username }}')">Ver Tweets</button>
                            <button class="btn-small btn-danger" onclick="deleteProfile({{ profile.id }})">Eliminar</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function scrapeNow(username) {
            if(confirm('Scrapear @' + username + ' ahora?')) {
                fetch('/scrape_now/' + username, {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        alert(data.message);
                        location.reload();
                    });
            }
        }

        function viewTweets(username) {
            window.location.href = '/tweets/' + username;
        }

        function deleteProfile(id) {
            if(confirm('Eliminar este perfil y todos sus tweets?')) {
                fetch('/delete_profile/' + id, {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        alert(data.message);
                        location.reload();
                    });
            }
        }
    </script>
</body>
</html>
"""

TWEETS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Tweets de @{{ username }}</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: #f5f8fa;
            padding: 20px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        .header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { color: #1da1f2; }
        .back-btn {
            display: inline-block;
            padding: 10px 20px;
            background: #1da1f2;
            color: white;
            text-decoration: none;
            border-radius: 25px;
            margin-bottom: 20px;
        }
        .tweet {
            background: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        .tweet:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .tweet-text {
            font-size: 1.1em;
            line-height: 1.5;
            margin-bottom: 15px;
            color: #14171a;
        }
        .tweet-meta {
            display: flex;
            gap: 20px;
            color: #657786;
            font-size: 0.9em;
        }
        .tweet-link {
            color: #1da1f2;
            text-decoration: none;
            font-weight: 500;
        }
        .lang-badge {
            display: inline-block;
            padding: 3px 8px;
            background: #e1e8ed;
            border-radius: 5px;
            font-size: 0.8em;
        }
            .rt-badge {
            display: inline-block;
            padding: 3px 8px;
            background: #1da1f2;
            color: white;
            border-radius: 5px;
            font-size: 0.8em;
            font-weight: bold;
            margin-bottom: 10px;
            }
            .rt-indicator {
            color: #1da1f2;
            font-weight: 600;
            margin-bottom: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-btn">Volver al Dashboard</a>
        
        <div class="header">
            <h1>@{{ username }}</h1>
            <p>{{ tweets|length }} tweets guardados</p>
        </div>

        {% for tweet in tweets %}
        <div class="tweet">
            {% if tweet.is_retweet %}
            <div class="rt-indicator">
                🔄 Retweet
                {% if tweet.original_author %}
                de @{{ tweet.original_author }}
                {% endif %}
            </div>
            {% endif %}
            <div class="tweet-text">{{ tweet.tweet_text }}</div>
            <div class="tweet-meta">
                <span>❤️ {{ tweet.likes }}</span>
                <span>🔄 {{ tweet.retweets }}</span>
                <span>💬 {{ tweet.replies }}</span>
                <span class="lang-badge">{{ tweet.language }}</span>
                {% if tweet.is_retweet %}
                <span class="rt-badge">RT</span>
                {% endif %}
                <a href="{{ tweet.tweet_url }}" target="_blank" class="tweet-link">Ver en X</a>
            </div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

SEARCH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Buscar Tweets</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #1da1f2 0%, #0d8bd9 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 900px; margin: 0 auto; }
        .search-header {
            text-align: center;
            margin-bottom: 40px;
            color: white;
        }
        .search-header h1 {
            font-size: 3em;
            margin-bottom: 10px;
        }
        .search-header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        .search-box {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-bottom: 30px;
        }
        .search-input-wrapper {
            position: relative;
            margin-bottom: 20px;
        }
        .search-input {
            width: 100%;
            padding: 20px 60px 20px 20px;
            border: 3px solid #e1e8ed;
            border-radius: 50px;
            font-size: 1.2em;
            transition: all 0.3s;
        }
        .search-input:focus {
            outline: none;
            border-color: #1da1f2;
            box-shadow: 0 0 0 4px rgba(29, 161, 242, 0.1);
        }
        .search-btn {
            position: absolute;
            right: 5px;
            top: 50%;
            transform: translateY(-50%);
            background: #1da1f2;
            border: none;
            padding: 12px 25px;
            border-radius: 50px;
            color: white;
            cursor: pointer;
            font-size: 1.1em;
            transition: all 0.2s;
        }
        .search-btn:hover {
            background: #0d8bd9;
            transform: translateY(-50%) scale(1.05);
        }
        .filters {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .filter-group {
            display: flex;
            flex-direction: column;
        }
        .filter-group label {
            margin-bottom: 5px;
            color: #657786;
            font-size: 0.9em;
            font-weight: 500;
        }
        .filter-group select, .filter-group input {
            padding: 10px;
            border: 2px solid #e1e8ed;
            border-radius: 8px;
            font-size: 1em;
        }
        .back-link {
            display: inline-block;
            color: white;
            text-decoration: none;
            margin-bottom: 20px;
            padding: 10px 20px;
            background: rgba(255,255,255,0.2);
            border-radius: 25px;
            transition: all 0.2s;
        }
        .back-link:hover {
            background: rgba(255,255,255,0.3);
        }
        .results {
            background: white;
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .results-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #e1e8ed;
        }
        .results-count {
            color: #657786;
            font-size: 1.1em;
        }
        .sort-options {
            display: flex;
            gap: 10px;
        }
        .sort-btn {
            padding: 8px 15px;
            border: 2px solid #e1e8ed;
            background: white;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .sort-btn:hover, .sort-btn.active {
            background: #1da1f2;
            color: white;
            border-color: #1da1f2;
        }
        .tweet-result {
            padding: 20px;
            border-bottom: 1px solid #e1e8ed;
            transition: all 0.2s;
        }
        .tweet-result:hover {
            background: #f7f9fa;
        }
        .tweet-result:last-child {
            border-bottom: none;
        }
        .tweet-author {
            color: #1da1f2;
            font-weight: bold;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .tweet-text {
            font-size: 1.1em;
            line-height: 1.6;
            margin-bottom: 15px;
            color: #14171a;
        }
        .highlight {
            background: #fff3cd;
            padding: 2px 4px;
            border-radius: 3px;
            font-weight: 500;
        }
        .tweet-meta {
            display: flex;
            gap: 20px;
            color: #657786;
            font-size: 0.9em;
            align-items: center;
        }
        .tweet-link {
            color: #1da1f2;
            text-decoration: none;
            font-weight: 500;
        }
        .lang-tag {
            padding: 4px 10px;
            background: #e1e8ed;
            border-radius: 12px;
            font-size: 0.85em;
            text-transform: uppercase;
        }
        .no-results {
            text-align: center;
            padding: 60px 20px;
            color: #657786;
        }
        .no-results-icon {
            font-size: 4em;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">Dashboard</a>
        
        <div class="search-header">
            <h1>Buscador de Tweets</h1>
            <p>Busca en {{ total_tweets }} tweets de {{ total_profiles }} perfiles</p>
        </div>

        <form method="GET" action="/search">
            <div class="search-box">
                <div class="search-input-wrapper">
                    <input 
                        type="text" 
                        name="q" 
                        class="search-input" 
                        placeholder="Buscar en todos los tweets..."
                        value="{{ query }}"
                        autofocus
                    >
                    <button type="submit" class="search-btn">Buscar</button>
                </div>
                
                <div class="filters">
                    <div class="filter-group">
                        <label>Usuario</label>
                        <select name="author">
                            <option value="">Todos</option>
                            {% for profile in profiles %}
                            <option value="{{ profile }}" {% if author == profile %}selected{% endif %}>
                                @{{ profile }}
                            </option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="filter-group">
                        <label>Idioma</label>
                        <select name="lang">
                            <option value="">Todos</option>
                            <option value="en" {% if lang == 'en' %}selected{% endif %}>English</option>
                            <option value="es" {% if lang == 'es' %}selected{% endif %}>Español</option>
                            <option value="pt" {% if lang == 'pt' %}selected{% endif %}>Português</option>
                            <option value="fr" {% if lang == 'fr' %}selected{% endif %}>Français</option>
                        </select>
                    </div>
                    
                    <div class="filter-group">
                        <label>Desde</label>
                        <input type="date" name="date_from" value="{{ date_from }}">
                    </div>
                    
                    <div class="filter-group">
                        <label>Hasta</label>
                        <input type="date" name="date_to" value="{{ date_to }}">
                    </div>
                </div>
            </div>
        </form>

        {% if searched %}
        <div class="results">
            <div class="results-header">
                <div class="results-count">
                    <strong>{{ results|length }}</strong> resultados
                    {% if query %}para "<strong>{{ query }}</strong>"{% endif %}
                </div>
                <div class="sort-options">
                    <button class="sort-btn {% if sort == 'date' %}active{% endif %}" 
                            onclick="sortBy('date')">Fecha</button>
                    <button class="sort-btn {% if sort == 'likes' %}active{% endif %}" 
                            onclick="sortBy('likes')">Likes</button>
                </div>
            </div>

            {% if results %}
                {% for tweet in results %}
                <div class="tweet-result">
                    <div class="tweet-author">
                        <span>@{{ tweet.author }}</span>
                        {% if tweet.is_retweet %}
                        <span style="color: #1da1f2; font-weight: 600;">🔄 RT</span>
                        {% if tweet.original_author %}
                        <span style="color: #657786;">de @{{ tweet.original_author }}</span>
                        {% endif %}
                        {% endif %}
                        <span class="lang-tag">{{ tweet.language or 'unknown' }}</span>
                    </div>
                    <div class="tweet-text">{{ tweet.highlighted_text|safe }}</div>
                    <div class="tweet-meta">
                        <span>❤️ {{ tweet.likes }}</span>
                        <span>🔄 {{ tweet.retweets }}</span>
                        <span>💬 {{ tweet.replies }}</span>
                        <span>{{ tweet.scraped_date[:10] }}</span>
                        <a href="{{ tweet.tweet_url }}" target="_blank" class="tweet-link">
                            Ver en X
                        </a>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-results">
                    <div class="no-results-icon">?</div>
                    <h2>No se encontraron resultados</h2>
                    <p>Intenta con otros terminos de busqueda o ajusta los filtros</p>
                </div>
            {% endif %}
        </div>
        {% endif %}
    </div>

    <script>
        function sortBy(sortType) {
            const url = new URL(window.location);
            url.searchParams.set('sort', sortType);
            window.location = url.toString();
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM profiles")
    total_profiles = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM profiles WHERE is_active = 1")
    active_profiles = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tweets")
    total_tweets = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM tweets 
        WHERE DATE(scraped_date) = DATE('now')
    """)
    today_tweets = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT p.id, p.username, p.scrape_interval_hours, p.last_scraped, p.is_active,
               COUNT(t.id) as tweet_count
        FROM profiles p
        LEFT JOIN tweets t ON p.id = t.profile_id
        GROUP BY p.id
        ORDER BY p.added_date DESC
    """)
    
    profiles = []
    for row in cursor.fetchall():
        profiles.append({
            'id': row[0],
            'username': row[1],
            'scrape_interval_hours': row[2],
            'last_scraped': row[3][:16] if row[3] else None,
            'is_active': row[4],
            'tweet_count': row[5]
        })
    
    conn.close()
    
    stats = {
        'total_profiles': total_profiles,
        'active_profiles': active_profiles,
        'total_tweets': total_tweets,
        'today_tweets': today_tweets
    }
    
    return render_template_string(HOME_TEMPLATE, stats=stats, profiles=profiles)

@app.route('/add_profile', methods=['POST'])
def add_profile():
    username = request.form.get('username', '').strip().replace('@', '')
    interval = int(request.form.get('interval', 12))
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO profiles (username, profile_url, scrape_interval_hours)
            VALUES (?, ?, ?)
        """, (username, f"https://x.com/{username}", interval))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    
    conn.close()
    return redirect('/')

@app.route('/delete_profile/<int:profile_id>', methods=['POST'])
def delete_profile(profile_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM tweets WHERE profile_id = ?", (profile_id,))
    cursor.execute("DELETE FROM scrape_logs WHERE profile_id = ?", (profile_id,))
    cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Perfil eliminado"})

@app.route('/scrape_now/<username>', methods=['POST'])
def scrape_now(username):
    result = scraper.scrape_profile(username)
    scraper.close_driver()
    
    if result['status'] == 'success':
        msg = f"{result['tweets_new']} tweets nuevos de {result['tweets_found']} encontrados"
    else:
        msg = f"Error: {result.get('message', 'Unknown')}"
    
    return jsonify({"message": msg})

@app.route('/tweets/<username>')
def view_tweets(username):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute("""
            SELECT tweet_text, tweet_url, language, likes, retweets, replies, is_retweet, original_author
        FROM tweets t
        JOIN profiles p ON t.profile_id = p.id
        WHERE p.username = ?
        ORDER BY t.scraped_date DESC
    """, (username,))
    
    tweets = []
    for row in cursor.fetchall():
        tweets.append({
            'tweet_text': row[0],
            'tweet_url': row[1],
            'language': row[2] or 'unknown',
            'likes': row[3],
            'retweets': row[4],
            'replies': row[5],
            'is_retweet': bool(row[6]) if row[6] is not None else False,
            'original_author': row[7]
        })
    
    conn.close()
    
    return render_template_string(TWEETS_TEMPLATE, username=username, tweets=tweets)

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    author = request.args.get('author', '').strip()
    lang = request.args.get('lang', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    sort = request.args.get('sort', 'date')
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT username FROM profiles ORDER BY username")
    profiles = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(*) FROM tweets")
    total_tweets = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM profiles")
    total_profiles = cursor.fetchone()[0]
    
    results = []
    searched = bool(query or author or lang or date_from or date_to)
    
    if searched:
        sql = """
            SELECT tweet_text, tweet_url, author, language,
                   likes, retweets, replies, scraped_date, is_retweet, original_author
            FROM tweets
            WHERE 1=1
        """
        params = []
        
        if query:
            sql += " AND tweet_text LIKE ?"
            params.append(f'%{query}%')
        
        if author:
            sql += " AND author = ?"
            params.append(author)
        
        if lang:
            sql += " AND language = ?"
            params.append(lang)
        
        if date_from:
            sql += " AND DATE(scraped_date) >= ?"
            params.append(date_from)
        
        if date_to:
            sql += " AND DATE(scraped_date) <= ?"
            params.append(date_to)
        
        if sort == 'date':
            sql += " ORDER BY scraped_date DESC"
        elif sort == 'likes':
            sql += " ORDER BY likes DESC"
        else:
            sql += " ORDER BY scraped_date DESC"
        
        sql += " LIMIT 100"
        
        cursor.execute(sql, params)
        
        import re
        for row in cursor.fetchall():
            tweet_text = row[0]
            
            highlighted = tweet_text
            if query:
                terms = query.split()
                for term in terms:
                    if term:
                        pattern = re.compile(f'({re.escape(term)})', re.IGNORECASE)
                        highlighted = pattern.sub(r'<span class="highlight">\1</span>', highlighted)
            
            results.append({
                'tweet_text': tweet_text,
                'highlighted_text': highlighted,
                'tweet_url': row[1],
                'author': row[2],
                'language': row[3] or 'unknown',
                'likes': row[4],
                'retweets': row[5],
                'replies': row[6],
                'scraped_date': row[7],
                'is_retweet': bool(row[8]) if row[8] is not None else False,
                'original_author': row[9]
            })
    
    conn.close()
    
    return render_template_string(
        SEARCH_TEMPLATE,
        query=query,
        author=author,
        lang=lang,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        results=results,
        searched=searched,
        profiles=profiles,
        total_tweets=total_tweets,
        total_profiles=total_profiles
    )

if __name__ == '__main__':
    scheduler.add_job(
        id='scrape_profiles',
        func=scheduled_scrape_job,
        trigger='interval',
        minutes=30
    )
    scheduler.start()
    
    scraper.init_database()
    
    print("="*60)
    print("Twitter Scraper Web App")
    print("="*60)
    print("Abre: http://localhost:5000")
    print("Scheduler: Activo (revisa cada 30 min)")
    print("="*60)
    
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)