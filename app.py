#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py - Vavoo Proxy Server
HF Space / Render / Railway uyumlu
"""

import logging
import os
import asyncio
from aiohttp import web
from vavoo_proxy import VavooProxy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

PORT = int(os.environ.get("PORT", 7860))


def create_app():
    proxy = VavooProxy()
    app = web.Application(client_max_size=1024 ** 3)

    # ── Route'lar ──────────────────────────────────────────────────────────
    app.router.add_get('/', proxy.handle_root)

    # Vavoo özel endpoint'ler
    app.router.add_get('/vavoo/stream',  proxy.handle_stream)
    app.router.add_get('/vavoo/resolve', proxy.handle_resolve)
    app.router.add_get('/vavoo/m3u',     proxy.handle_m3u)

    # EasyProxy uyumlu endpoint'ler (eski URL'ler çalışmaya devam etsin)
    app.router.add_get('/proxy/manifest.m3u8',     proxy.handle_manifest)
    app.router.add_get('/proxy/hls/manifest.m3u8', proxy.handle_manifest)
    app.router.add_get('/proxy/stream',            proxy.handle_stream)
    app.router.add_get('/proxy/m3u',               proxy.handle_m3u)   # 405 sorunu çözüldü!
    app.router.add_get('/vavoo/sig',               proxy.handle_sig_test)  # ← bunu ekle
    # CORS OPTIONS
    app.router.add_route('OPTIONS', '/{tail:.*}', proxy.handle_options)

    # Cleanup
    async def on_cleanup(app):
        await proxy.cleanup()
    app.on_cleanup.append(on_cleanup)

    return app


app = create_app()


if __name__ == '__main__':
    print("=" * 55)
    print("🎬  Vavoo Proxy Server")
    print(f"📡  http://localhost:{PORT}")
    print()
    print("Endpoint'ler:")
    print("  /vavoo/stream?url=<vavoo_url>")
    print("  /vavoo/resolve?url=<vavoo_url>")
    print("  /vavoo/m3u?url=<vavoo_url>")
    print("  /proxy/manifest.m3u8?url=<vavoo_url>")
    print("=" * 55)
    web.run_app(app, host='0.0.0.0', port=PORT)
