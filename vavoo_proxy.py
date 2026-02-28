#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vavoo_proxy.py - Vavoo Stream Proxy
Signature alır → stream URL çözer → HLS proxy yapar
"""

import asyncio
import aiohttp
import logging
import time
import re
from aiohttp import web

logger = logging.getLogger(__name__)

_signature_cache = {"sig": None, "ts": 0}
SIGNATURE_TTL = 900

PING_HEADERS = {
    "user-agent": "okhttp/4.11.0",
    "accept": "application/json",
    "content-type": "application/json; charset=utf-8",
    "content-length": "1106",
    "accept-encoding": "gzip"
}

PING_DATA = {
    "token": "tosFwQCJMS8qrW_AjLoHPQ41646J5dRNha6ZWHnijoYQQQoADQoXYSo7ki7O5-CsgN4CH0uRk6EEoJ0728ar9scCRQW3ZkbfrPfeCXW2VgopSW2FWDqPOoVYIuVPAOnXCZ5g",
    "reason": "app-blur",
    "locale": "de",
    "theme": "dark",
    "metadata": {
        "device": {
            "type": "Handset",
            "brand": "google",
            "model": "Nexus",
            "name": "21081111RG",
            "uniqueId": "d10e5d99ab665233"
        },
        "os": {
            "name": "android",
            "version": "7.1.2",
            "abis": ["arm64-v8a", "armeabi-v7a", "armeabi"],
            "host": "android"
        },
        "app": {
            "platform": "android",
            "version": "3.1.20",
            "buildId": "289515000",
            "engine": "hbc85",
            "signatures": ["6e8a975e3cbf07d5de823a760d4c2547f86c1403105020adee5de67ac510999e"],
            "installer": "app.revanced.manager.flutter"
        },
        "version": {
            "package": "tv.vavoo.app",
            "binary": "3.1.20",
            "js": "3.1.20"
        }
    },
    "appFocusTime": 0,
    "playerActive": False,
    "playDuration": 0,
    "devMode": False,
    "hasAddon": True,
    "castConnected": False,
    "package": "tv.vavoo.app",
    "version": "3.1.20",
    "process": "app",
    "firstAppStart": 1743962904623,
    "lastAppStart": 1743962904623,
    "ipLocation": "",
    "adblockEnabled": True,
    "proxy": {
        "supported": ["ss", "openvpn"],
        "engine": "ss",
        "ssVersion": 1,
        "enabled": True,
        "autoServer": True,
        "id": "pl-waw"
    },
    "iap": {"supported": False}
}

PING_URLS = [
    "https://www.vavoo.tv/api/app/ping",
    "https://vavoo.to/api/app/ping",
    "https://vavoo.tv/api/app/ping",
]


async def get_signature(session: aiohttp.ClientSession):
    now = time.time()
    if _signature_cache["sig"] and (now - _signature_cache["ts"]) < SIGNATURE_TTL:
        return _signature_cache["sig"]

    for ping_url in PING_URLS:
        try:
            async with session.post(
                ping_url,
                json=PING_DATA,
                headers=PING_HEADERS,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json(content_type=None)
                sig = data.get("addonSig")
                if sig:
                    _signature_cache["sig"] = sig
                    _signature_cache["ts"] = now
                    logger.info(f"✅ Signature alındı: {ping_url}")
                    return sig
        except Exception as e:
            logger.warning(f"⚠️ {ping_url} → {e}")
            continue

    logger.error("❌ Hiçbir ping URL çalışmadı")
    return None


async def resolve_vavoo_stream(session: aiohttp.ClientSession, vavoo_url: str):
    signature = await get_signature(session)
    if not signature:
        return None

    headers = {
        "user-agent": "okhttp/4.11.0",
        "accept": "*/*",
        "mediahubmx-signature": signature,
        "referer": "https://vavoo.to/",
    }

    try:
        async with session.get(
            vavoo_url,
            headers=headers,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=20)
        ) as resp:
            final_url = str(resp.url)
            logger.info(f"🔗 Resolved: {vavoo_url} → {final_url}")
            return final_url
    except Exception as e:
        logger.error(f"❌ Resolve hatası: {e}")
        return None


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
    "Access-Control-Allow-Headers": "*",
}


class VavooProxy:
    def __init__(self):
        self.session = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(ssl=False, limit=50)
            self.session = aiohttp.ClientSession(connector=connector)
        return self.session

    async def cleanup(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def handle_options(self, request: web.Request) -> web.Response:
        return web.Response(status=200, headers=CORS_HEADERS)

    async def handle_root(self, request: web.Request) -> web.Response:
        html = """<!DOCTYPE html>
<html><head><title>Vavoo Proxy</title></head>
<body style="font-family:monospace;background:#111;color:#eee;padding:2rem">
<h2>🎬 Vavoo Proxy</h2>
<h3>Endpoint'ler:</h3>
<ul>
  <li><b>/vavoo/stream?url=&lt;vavoo_play_url&gt;</b> — Stream'i proxy'ler</li>
  <li><b>/vavoo/resolve?url=&lt;vavoo_play_url&gt;</b> — Gerçek URL'yi döner</li>
  <li><b>/vavoo/m3u?url=&lt;vavoo_play_url&gt;</b> — M3U wrapper döner</li>
  <li><b>/proxy/manifest.m3u8?url=&lt;vavoo_play_url&gt;</b> — HLS proxy</li>
  <li><b>/vavoo/sig</b> — Signature test</li>
</ul>
<h3>Örnek:</h3>
<code>/vavoo/stream?url=https://vavoo.to/vavoo-iptv/play/267105889a25a483e5e80</code>
</body></html>"""
        return web.Response(text=html, content_type="text/html", headers=CORS_HEADERS)

    async def handle_sig_test(self, request: web.Request) -> web.Response:
        session = await self.get_session()
        sig = await get_signature(session)
        if sig:
            return web.Response(text=f"✅ Signature OK: {sig[:30]}...", headers=CORS_HEADERS)
        return web.Response(status=502, text="❌ Signature alınamadı", headers=CORS_HEADERS)

    async def handle_resolve(self, request: web.Request) -> web.Response:
        url = request.query.get("url", "").strip()
        if not url:
            return web.Response(status=400, text="?url= parametresi gerekli", headers=CORS_HEADERS)

        session = await self.get_session()
        resolved = await resolve_vavoo_stream(session, url)

        if not resolved:
            return web.Response(status=502, text="Stream çözülemedi", headers=CORS_HEADERS)

        return web.Response(text=resolved, content_type="text/plain", headers=CORS_HEADERS)

    async def handle_m3u(self, request: web.Request) -> web.Response:
        url = request.query.get("url", "").strip()
        if not url:
            return web.Response(status=400, text="?url= parametresi gerekli", headers=CORS_HEADERS)

        base = str(request.url.origin())
        stream_url = f"{base}/vavoo/stream?url={url}"
        m3u = f"#EXTM3U\n#EXTINF:-1,Vavoo Stream\n{stream_url}\n"
        headers = {**CORS_HEADERS, "Content-Type": "application/x-mpegurl"}
        return web.Response(text=m3u, headers=headers)

    async def handle_stream(self, request: web.Request) -> web.StreamResponse:
        url = request.query.get("url", "").strip()
        if not url:
            return web.Response(status=400, text="?url= parametresi gerekli", headers=CORS_HEADERS)

        session = await self.get_session()
        signature = await get_signature(session)
        if not signature:
            return web.Response(status=502, text="Signature alınamadı", headers=CORS_HEADERS)

        req_headers = {
            "user-agent": "okhttp/4.11.0",
            "accept": "*/*",
            "mediahubmx-signature": signature,
            "referer": "https://vavoo.to/",
        }

        if "Range" in request.headers:
            req_headers["Range"] = request.headers["Range"]

        try:
            async with session.get(
                url,
                headers=req_headers,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=60, connect=15)
            ) as upstream:
                status = upstream.status
                content_type = upstream.headers.get("Content-Type", "video/MP2T")

                resp_headers = {
                    **CORS_HEADERS,
                    "Content-Type": content_type,
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                }

                if "Content-Length" in upstream.headers:
                    resp_headers["Content-Length"] = upstream.headers["Content-Length"]
                if "Content-Range" in upstream.headers:
                    resp_headers["Content-Range"] = upstream.headers["Content-Range"]

                response = web.StreamResponse(status=status, headers=resp_headers)
                await response.prepare(request)

                async for chunk in upstream.content.iter_chunked(65536):
                    await response.write(chunk)

                await response.write_eof()
                return response

        except asyncio.TimeoutError:
            return web.Response(status=504, text="Upstream timeout", headers=CORS_HEADERS)
        except Exception as e:
            logger.error(f"❌ Stream hatası: {e}")
            return web.Response(status=502, text=f"Proxy hatası: {e}", headers=CORS_HEADERS)

    async def handle_manifest(self, request: web.Request) -> web.StreamResponse:
        return await self.handle_stream(request)
