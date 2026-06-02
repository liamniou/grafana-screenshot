#!/usr/bin/env python3
"""
Grafana Dashboard Screenshot Service - Memory Optimized
"""

import asyncio
import threading
import time
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GRAFANA_URL = os.environ.get('GRAFANA_URL')
SCREENSHOT_INTERVAL = int(os.environ.get('SCREENSHOT_INTERVAL', '15'))
WIDTH = int(os.environ.get('WIDTH', '800'))
HEIGHT = int(os.environ.get('HEIGHT', '480'))
HTTP_PORT = int(os.environ.get('HTTP_PORT', '8080'))
BROWSER_RESTART_INTERVAL = 30

current_screenshot = None
screenshot_lock = threading.Lock()
last_update = 0


class ScreenshotHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global current_screenshot, last_update
        
        if self.path in ('/', '/dashboard.png', '/screenshot'):
            with screenshot_lock:
                if current_screenshot:
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Length', len(current_screenshot))
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    self.wfile.write(current_screenshot)
                else:
                    self.send_response(503)
                    self.end_headers()
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            age = int(time.time() - last_update) if last_update else -1
            self.wfile.write(f'{{"status":"ok","age":{age}}}'.encode())
        elif self.path == '/page':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html = f'<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="{SCREENSHOT_INTERVAL}"></head><body style="margin:0;padding:0;background:#111;overflow:hidden;width:100vw;height:100vh;display:flex;align-items:center;justify-content:center"><img src="/dashboard.png" style="max-width:100vw;max-height:100vh;object-fit:contain"></body></html>'
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass


async def capture_screenshot():
    global current_screenshot, last_update
    
    browser_args = [
        '--no-sandbox',
        '--disable-setuid-sandbox', 
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-extensions',
        '--disable-background-networking',
        '--disable-default-apps',
        '--disable-sync',
        '--disable-translate',
        '--mute-audio',
        '--no-first-run',
        '--safebrowsing-disable-auto-update',
        '--js-flags=--max-old-space-size=256',
    ]
    
    screenshot_count = 0
    
    while True:
        browser = None
        context = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=browser_args)
                context = await browser.new_context(
                    viewport={'width': WIDTH, 'height': HEIGHT},
                    device_scale_factor=1,
                )
                page = await context.new_page()
                
                while screenshot_count < BROWSER_RESTART_INTERVAL:
                    try:
                        start = time.time()
                        
                        # Force fresh load with cache bust
                        url = f"{GRAFANA_URL}&_cb={int(time.time())}"
                        await page.goto(url, wait_until='networkidle', timeout=30000)
                        await asyncio.sleep(1.5)
                        
                        screenshot_bytes = await page.screenshot(type='png')
                        
                        with screenshot_lock:
                            current_screenshot = screenshot_bytes
                            last_update = time.time()
                        
                        screenshot_count += 1
                        logger.info(f"Screenshot {screenshot_count}/{BROWSER_RESTART_INTERVAL} ({len(screenshot_bytes)}b, {time.time()-start:.1f}s)")
                        
                    except Exception as e:
                        error_msg = str(e).lower()
                        # If browser/page was closed (OOM killed), break out to restart
                        if 'closed' in error_msg or 'target' in error_msg or 'crashed' in error_msg:
                            logger.error(f"Browser died, restarting: {e}")
                            break
                        logger.error(f"Screenshot failed: {e}")
                    
                    await asyncio.sleep(SCREENSHOT_INTERVAL)
                
                await context.close()
                await browser.close()
                
            logger.info("Browser restart for memory cleanup")
            screenshot_count = 0
            
        except Exception as e:
            logger.error(f"Browser error: {e}")
            # Ensure cleanup on error
            try:
                if context:
                    await context.close()
                if browser:
                    await browser.close()
            except:
                pass
            await asyncio.sleep(5)
            screenshot_count = 0  # Reset counter on browser crash


def main():
    logger.info(f"Screenshot service starting - {WIDTH}x{HEIGHT} every {SCREENSHOT_INTERVAL}s")
    
    http_thread = threading.Thread(target=lambda: HTTPServer(('0.0.0.0', HTTP_PORT), ScreenshotHandler).serve_forever(), daemon=True)
    http_thread.start()
    logger.info(f"HTTP server on port {HTTP_PORT}")
    
    asyncio.run(capture_screenshot())


if __name__ == '__main__':
    main()
