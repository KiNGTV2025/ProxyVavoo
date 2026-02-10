from gevent import monkey
monkey.patch_all()

from flask import Flask, request, Response, render_template_string
import requests
from urllib.parse import urlparse, urljoin, quote, unquote
import re
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

app = Flask(__name__)

# ======================================================
# ✅ MODERN DARK UI PANEL
# ======================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr" class="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StreamFlow Proxy</title>

<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">

<style>
body{
    background:#0f172a;
    color:white;
    font-family:Arial;
    text-align:center;
    padding:40px;
}
.card{
    max-width:800px;
    margin:auto;
    background:#1e293b;
    padding:30px;
    border-radius:20px;
    border:1px solid #334155;
}
input{
    width:70%;
    padding:15px;
    border-radius:12px;
    border:none;
    outline:none;
}
button{
    padding:15px 25px;
    border-radius:12px;
    border:none;
    cursor:pointer;
    background:linear-gradient(135deg,#6366f1,#ec4899);
    color:white;
    font-weight:bold;
}
button:hover{opacity:0.8;}
.endpoint{
    margin-top:15px;
    background:#0f172a;
    padding:10px;
    border-radius:10px;
    font-family:monospace;
}
</style>
</head>

<body>
<div class="card">
<h1>🚀 StreamFlow Proxy</h1>
<p>Ultra Low Latency M3U8 Proxy Sistemi</p>

<input id="streamUrl" value="https://example.com/playlist.m3u8">
<button onclick="proxyStream()">Proxy Başlat</button>

<h3>📌 Endpointler</h3>

<div class="endpoint">/proxy/m3u?url=AKIŞ_URL</div>
<div class="endpoint">/proxy/resolve?url=KAYNAK_URL</div>
<div class="endpoint">/proxy?url=PLAYLIST_URL</div>

<p style="margin-top:20px;color:gray;">
Geliştirici: Ümitm0d 💚
</p>
</div>

<script>
function proxyStream(){
    let url=document.getElementById("streamUrl").value;
    if(!url){
        alert("URL gir kanka!");
        return;
    }
    window.open("/proxy/resolve?url="+encodeURIComponent(url));
}
</script>

</body>
</html>
"""

# ======================================================
# ✅ SESSION + RETRY OPTIMIZATION
# ======================================================

def create_session():
    s = requests.Session()
    retry_strategy = Retry(
        total=2,
        backoff_factor=0.2,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(
        pool_connections=200,
        pool_maxsize=200,
        max_retries=retry_strategy,
        pool_block=False
    )
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


# ======================================================
# ✅ M3U DETECTION
# ======================================================

def detect_m3u_type(content):
    if "#EXTM3U" in content[:100]:
        return "m3u8"
    return "m3u"


# ======================================================
# ✅ KEY URI FIX
# ======================================================

def replace_key_uri(line, headers_query):
    if 'URI="' not in line:
        return line
    match = re.search(r'URI="([^"]+)"', line)
    if match:
        return line.replace(
            match.group(1),
            f"/proxy/key?url={quote(match.group(1))}&{headers_query}"
        )
    return line


# ======================================================
# ✅ VAVOO + EMBED RESOLVER
# ======================================================

PATTERNS = {
    "iframe": re.compile(r'iframe\s+src=[\'"]([^\'"]+)[\'"]'),
    "channel_key": re.compile(r'channelKey\s*=\s*"([^"]*)"'),
    "auth_ts": re.compile(r'authTs\s*=\s*"([^"]*)"'),
    "auth_rnd": re.compile(r'authRnd\s*=\s*"([^"]*)"'),
    "auth_sig": re.compile(r'authSig\s*=\s*"([^"]*)"'),
    "auth_host": re.compile(r'\}\s*fetchWithRetry\(\s*[\'"]([^\'"]*)[\'"]'),
    "server_lookup": re.compile(r'n\s+fetchWithRetry\(\s*[\'"]([^\'"]*)[\'"]'),
    "host": re.compile(r'm3u8\s*=.*?[\'"]([^\'"]*)[\'"]')
}


def resolve_m3u8_link(url, headers=None):
    if not url:
        return {"resolved_url": None, "headers": {}}

    current_headers = headers or {"User-Agent": "Mozilla/5.0"}
    s = create_session()

    try:
        resp = s.get(url, headers=current_headers, timeout=(3, 8))
        content = resp.text
        final_url = resp.url

        # Direkt playlist geldiyse
        if content.strip().startswith("#EXTM3U"):
            return {"resolved_url": final_url, "headers": current_headers}

        # iframe çözümle
        iframe_match = PATTERNS["iframe"].search(content)
        if not iframe_match:
            return {"resolved_url": url, "headers": current_headers}

        iframe_url = iframe_match.group(1)

        resp2 = s.get(iframe_url, headers=current_headers, timeout=(3, 8))
        iframe_text = resp2.text

        matches = {k: p.search(iframe_text) for k, p in PATTERNS.items()}
        needed = ["channel_key", "auth_ts", "auth_rnd", "auth_sig", "auth_host", "server_lookup", "host"]

        if not all(matches[k] for k in needed):
            return {"resolved_url": url, "headers": current_headers}

        channel_key = matches["channel_key"].group(1)
        auth_ts = matches["auth_ts"].group(1)
        auth_rnd = matches["auth_rnd"].group(1)
        auth_sig = quote(matches["auth_sig"].group(1))

        auth_host = matches["auth_host"].group(1)
        server_lookup = matches["server_lookup"].group(1)
        host = matches["host"].group(1)

        auth_url = f"{auth_host}{channel_key}&ts={auth_ts}&rnd={auth_rnd}&sig={auth_sig}"
        s.get(auth_url, headers=current_headers)

        lookup_url = f"https://{urlparse(iframe_url).netloc}{server_lookup}{channel_key}"
        srv_resp = s.get(lookup_url, headers=current_headers)
        server_key = srv_resp.json().get("server_key")

        if not server_key:
            return {"resolved_url": url, "headers": current_headers}

        stream_url = f"https://{server_key}{host}{server_key}/{channel_key}/mono.m3u8"

        return {"resolved_url": stream_url, "headers": current_headers}

    except:
        return {"resolved_url": url, "headers": current_headers}

    finally:
        s.close()


# ======================================================
# ✅ MAIN PROXY PLAYLIST
# ======================================================

@app.route("/proxy/m3u")
def proxy_m3u():
    m3u_url = request.args.get("url", "").strip()
    if not m3u_url:
        return "URL eksik", 400

    headers = {"User-Agent": "Mozilla/5.0"}

    result = resolve_m3u8_link(m3u_url, headers)
    resolved_url = result["resolved_url"]

    s = create_session()
    resp = s.get(resolved_url, headers=headers, timeout=(3, 10))
    content = resp.text
    final_url = resp.url
    s.close()

    if detect_m3u_type(content) == "m3u":
        return Response(content, content_type="application/vnd.apple.mpegurl")

    parsed = urlparse(final_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rsplit('/',1)[0]}/"

    lines = []
    for line in content.split("\n"):
        line=line.strip()
        if not line:
            lines.append(line)
        elif line.startswith("#EXT-X-KEY"):
            lines.append(replace_key_uri(line,""))
        elif not line.startswith("#"):
            seg = urljoin(base_url,line)
            lines.append(f"/proxy/ts?url={quote(seg)}")
        else:
            lines.append(line)

    return Response("\n".join(lines), content_type="application/vnd.apple.mpegurl")


# ======================================================
# ✅ ULTRA LOW LATENCY TS STREAM
# ======================================================

@app.route("/proxy/ts")
def proxy_ts():
    ts_url = request.args.get("url", "").strip()
    if not ts_url:
        return "TS URL eksik", 400

    try:
        s = create_session()
        resp = s.get(ts_url, stream=True, timeout=(3, 15))
        resp.raise_for_status()

        # 🚀 NO BUFFER REALTIME STREAM
        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        return Response(
            generate(),
            content_type="video/mp2t",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )

    except Exception as e:
        return f"Hata: {str(e)}", 500


# ======================================================
# ✅ KEY PROXY
# ======================================================

@app.route("/proxy/key")
def proxy_key():
    key_url = request.args.get("url", "").strip()
    if not key_url:
        return "KEY URL eksik", 400

    s = create_session()
    resp = s.get(key_url, timeout=(3, 8))
    data = resp.content
    s.close()

    return Response(data, content_type="application/octet-stream")


# ======================================================
# ✅ RESOLVE ENDPOINT
# ======================================================

@app.route("/proxy/resolve")
def proxy_resolve():
    url = request.args.get("url", "").strip()
    if not url:
        return "URL eksik", 400

    result = resolve_m3u8_link(url)

    return Response(
        f"#EXTM3U\n#EXTINF:-1,Stream\n/proxy/m3u?url={quote(result['resolved_url'])}",
        content_type="application/vnd.apple.mpegurl"
    )


# ======================================================
# ✅ HOME PANEL
# ======================================================

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/health")
def health():
    return {"status": "ok", "time": time.time()}


# ======================================================
# ✅ RUN
# ======================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=7860,
        threaded=True,
        debug=False
    )