import asyncio
import json
import os
import random
import secrets
import struct
import time
import urllib.request
from typing import Optional, Dict, Tuple, Any
from core.config import PROXY_FILE, get_max_proxy_latency


def parse_proxy_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parses a proxy line in format hostname:port:login:password (or with socks5://, http:// prefix).
    Returns a proxy dict with protocol, host, port, server, username, password.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    protocol = None
    if line.startswith("socks5://"):
        protocol = "socks5"
        line = line[len("socks5://"):]
    elif line.startswith("http://"):
        protocol = "http"
        line = line[len("http://"):]
    elif line.startswith("https://"):
        protocol = "https"
        line = line[len("https://"):]

    parts = line.split(":")
    if len(parts) >= 4:
        hostname = parts[0].strip()
        port_str = parts[1].strip()
        login = parts[2].strip()
        password = ":".join(parts[3:]).strip()

        try:
            port = int(port_str)
        except ValueError:
            return None

        if protocol is None:
            # Default DataImpulse port 824 and standard 1080 are SOCKS5
            if port in (824, 1080):
                protocol = "socks5"
            else:
                protocol = "http"

        return {
            "protocol": protocol,
            "host": hostname,
            "port": port,
            "server": f"{protocol}://{hostname}:{port}",
            "username": login,
            "password": password
        }
    return None


def get_random_proxy(file_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Randomly selects and returns a proxy from proxy.txt.
    Returns None if file does not exist or contains no valid proxies.
    """
    path = file_path or PROXY_FILE
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            valid_proxies = []
            for line in f:
                parsed = parse_proxy_line(line)
                if parsed:
                    valid_proxies.append(parsed)

            if valid_proxies:
                return random.choice(valid_proxies)
    except Exception:
        pass

    return None


async def query_ip_via_socks5(upstream_host: str, upstream_port: int, username: str, password: str, timeout: int = 8) -> Optional[dict]:
    """Queries ipinfo.io/json directly through an authenticated SOCKS5 proxy using pure asyncio."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(upstream_host, int(upstream_port)),
            timeout=timeout
        )
        # 1. Auth negotiation (Method 0x02 = Username/Password)
        writer.write(b'\x05\x01\x02')
        await writer.drain()
        resp = await reader.readexactly(2)
        if resp != b'\x05\x02':
            writer.close()
            return None

        # 2. Username/Password credentials
        u = username.encode('utf-8')
        p = password.encode('utf-8')
        writer.write(bytes([1, len(u)]) + u + bytes([len(p)]) + p)
        await writer.drain()
        auth_resp = await reader.readexactly(2)
        if auth_resp != b'\x01\x00':
            writer.close()
            return None

        # 3. CONNECT to ipinfo.io:80
        h = b'ipinfo.io'
        writer.write(bytes([5, 1, 0, 3, len(h)]) + h + struct.pack('>H', 80))
        await writer.drain()
        cmd_resp = await reader.readexactly(4)
        if cmd_resp[1] != 0:
            writer.close()
            return None
        atyp = cmd_resp[3]
        if atyp == 1:
            await reader.readexactly(6)
        elif atyp == 3:
            dlen = (await reader.readexactly(1))[0]
            await reader.readexactly(dlen + 2)
        elif atyp == 4:
            await reader.readexactly(18)

        # 4. HTTP GET request
        req = b'GET /json HTTP/1.1\r\nHost: ipinfo.io\r\nUser-Agent: curl/7.68.0\r\nAccept: application/json\r\nConnection: close\r\n\r\n'
        writer.write(req)
        await writer.drain()

        raw_resp = await reader.read(4096)
        writer.close()
        await writer.wait_closed()

        body = raw_resp.split(b'\r\n\r\n', 1)[1] if b'\r\n\r\n' in raw_resp else raw_resp
        return json.loads(body.decode('utf-8', errors='ignore'))
    except Exception:
        return None


def _sync_http_test(proxy: dict, timeout: float) -> Tuple[bool, float, Optional[dict]]:
    t0 = time.time()
    try:
        server = proxy["server"].replace("http://", "").replace("https://", "")
        user = proxy.get("username", "")
        pwd = proxy.get("password", "")
        proxy_url = f"http://{user}:{pwd}@{server}" if user and pwd else f"http://{server}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
        with opener.open("http://ipinfo.io/json", timeout=timeout) as res:
            data = json.loads(res.read().decode())
            lat = (time.time() - t0) * 1000
            return True, lat, data
    except Exception:
        lat = (time.time() - t0) * 1000
        return False, lat, None


async def test_proxy_speed(proxy: dict, timeout: float = 4.0) -> Tuple[bool, float, Optional[dict]]:
    """
    Tests proxy connection and measures round-trip latency in milliseconds.
    Returns (success: bool, latency_ms: float, ip_data: Optional[dict]).
    """
    proto = proxy.get("protocol", "http").lower()
    if proto == "socks5" or proxy.get("server", "").startswith("socks5://"):
        t0 = time.time()
        upstream_host = proxy.get("host") or proxy["server"].split("://", 1)[1].split(":")[0]
        upstream_port = proxy.get("port") or int(proxy["server"].split(":")[-1])
        data = await query_ip_via_socks5(
            upstream_host, upstream_port, proxy["username"], proxy["password"], timeout=int(timeout)
        )
        lat = (time.time() - t0) * 1000
        if data and "ip" in data:
            return True, lat, data
        return False, lat, None
    else:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_http_test, proxy, timeout)


async def get_high_speed_proxy(
    file_path: Optional[str] = None,
    max_attempts: int = 5,
    max_latency_ms: Optional[int] = None,
    logger=None
) -> Tuple[Optional[dict], Optional[dict]]:
    """
    Tests and returns only a verified high-speed proxy from proxy.txt before browser launch.
    Candidates are tested against latency threshold (MAX_PROXY_LATENCY_MS).
    Returns (proxy_dict, ip_data).
    """
    threshold = max_latency_ms if max_latency_ms is not None else get_max_proxy_latency()
    path = file_path or PROXY_FILE
    if not os.path.exists(path):
        if logger:
            logger.log("[WARNING] proxy.txt tidak ditemukan di root project.")
        return None, None

    proxies = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                p = parse_proxy_line(line)
                if p:
                    proxies.append(p)
    except Exception:
        pass

    if not proxies:
        if logger:
            logger.log("[WARNING] proxy.txt kosong atau tidak memiliki format proxy yang valid.")
        return None, None

    if logger:
        logger.log(f"[*] [Proxy Tester] Menguji kecepatan proxy (Target: High Speed < {threshold}ms)...")

    best_proxy = None
    best_data = None
    best_lat = float("inf")

    # Shuffle candidates
    random.shuffle(proxies)

    for attempt in range(1, max_attempts + 1):
        base = proxies[(attempt - 1) % len(proxies)]
        candidate = dict(base)

        # For rotating residential proxies (e.g. DataImpulse), isolate a fresh node via session id
        if "dataimpulse" in candidate.get("host", "").lower() and "sessid." not in candidate.get("username", ""):
            sess_token = secrets.token_hex(4)
            candidate["username"] = f"{candidate['username']};sessid.{sess_token}"

        server_disp = candidate["server"].replace("http://", "").replace("socks5://", "")
        if logger:
            logger.log(f"[*] [Percobaan {attempt}/{max_attempts}] Menguji respons node: {server_disp}...")

        success, lat, data = await test_proxy_speed(candidate, timeout=max(3.0, threshold / 1000.0 + 1.0))

        if success and data:
            ip_val = data.get("ip", "Unknown")
            city = data.get("city", "")
            loc_str = f" ({city})" if city else ""

            if lat < best_lat:
                best_lat = lat
                best_proxy = candidate
                best_data = data

            if lat <= threshold:
                if logger:
                    logger.log(
                        f"[+] [High Speed Proxy Terverifikasi] IP: {ip_val}{loc_str} | Latency: {lat:.0f}ms (Lolos < {threshold}ms) [OK]"
                    )
                return candidate, data
            else:
                if logger:
                    logger.log(
                        f"[-] [Node Lambat] IP: {ip_val}{loc_str} | Latency: {lat:.0f}ms > {threshold}ms. Mencari node lebih cepat..."
                    )
        else:
            if logger:
                logger.log(f"[-] [Node Gagal] Percobaan {attempt} timeout / unreachable ({lat:.0f}ms).")

    # If max_attempts reached, fall back to best candidate if responsive
    if best_proxy and best_data:
        if logger:
            logger.log(
                f"[+] [Proxy Terpilih] Menggunakan node tercepat yang berhasil: IP {best_data.get('ip')} ({best_lat:.0f}ms)"
            )
        return best_proxy, best_data

    if logger:
        logger.log("[-] [Error] Seluruh percobaan koneksi proxy gagal atau tidak ada respons.")
    return None, None


class LocalSocksBridge:
    """
    Lightweight local HTTP-to-SOCKS5 bridge.
    Chromium/Playwright does not support SOCKS5 username/password authentication natively.
    This bridge accepts standard HTTP/HTTPS proxy connections on 127.0.0.1 and securely
    tunnels them through the authenticated SOCKS5 upstream.
    """
    def __init__(self, upstream_host: str, upstream_port: int, username: str, password: str):
        self.upstream_host = upstream_host
        self.upstream_port = int(upstream_port)
        self.username = username
        self.password = password
        self.server = None
        self.port = None

    async def _socks5_connect(self, target_host: str, target_port: int):
        reader, writer = await asyncio.open_connection(self.upstream_host, self.upstream_port)
        # Methods negotiation
        writer.write(b'\x05\x01\x02')
        await writer.drain()
        resp = await reader.readexactly(2)
        if resp != b'\x05\x02':
            raise Exception('SOCKS5 auth negotiation rejected')

        # Credentials
        u = self.username.encode('utf-8')
        p = self.password.encode('utf-8')
        writer.write(bytes([1, len(u)]) + u + bytes([len(p)]) + p)
        await writer.drain()
        auth_resp = await reader.readexactly(2)
        if auth_resp != b'\x01\x00':
            raise Exception('SOCKS5 credentials rejected')

        # Connect command
        h_bytes = target_host.encode('utf-8')
        port_bytes = struct.pack('>H', int(target_port))
        writer.write(bytes([5, 1, 0, 3, len(h_bytes)]) + h_bytes + port_bytes)
        await writer.drain()
        cmd_resp = await reader.readexactly(4)
        if cmd_resp[1] != 0:
            raise Exception(f'SOCKS5 connect error: {cmd_resp[1]}')
        atyp = cmd_resp[3]
        if atyp == 1:
            await reader.readexactly(6)
        elif atyp == 3:
            dlen = (await reader.readexactly(1))[0]
            await reader.readexactly(dlen + 2)
        elif atyp == 4:
            await reader.readexactly(18)
        return reader, writer

    async def _pipe(self, r, w):
        try:
            while True:
                data = await r.read(65536)
                if not data:
                    break
                w.write(data)
                await w.drain()
        except Exception:
            pass
        finally:
            try:
                w.close()
            except Exception:
                pass

    async def _handle_client(self, client_reader, client_writer):
        try:
            line = await client_reader.readline()
            if not line:
                client_writer.close()
                return
            req_line = line.decode('utf-8', errors='ignore').strip()
            parts = req_line.split()
            if len(parts) < 2:
                client_writer.close()
                return
            method, target = parts[0], parts[1]
            if method.upper() == 'CONNECT':
                if ':' in target:
                    thost, tport = target.split(':', 1)
                    tport = int(tport)
                else:
                    thost = target
                    tport = 443

                while True:
                    hdr = await client_reader.readline()
                    if not hdr or hdr in (b'\r\n', b'\n'):
                        break

                up_reader, up_writer = await self._socks5_connect(thost, tport)
                client_writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                await client_writer.drain()
                await asyncio.gather(self._pipe(client_reader, up_writer), self._pipe(up_reader, client_writer))
            else:
                headers = [line]
                host_val = None
                while True:
                    hdr = await client_reader.readline()
                    if not hdr or hdr in (b'\r\n', b'\n'):
                        break
                    headers.append(hdr)
                    if hdr.lower().startswith(b'host:'):
                        host_val = hdr.decode('utf-8', errors='ignore').split(':', 1)[1].strip()

                if not host_val and '://' in target:
                    host_val = target.split('://', 1)[1].split('/')[0]

                if host_val:
                    if ':' in host_val:
                        thost, tport = host_val.split(':', 1)
                        tport = int(tport)
                    else:
                        thost = host_val
                        tport = 80

                    up_reader, up_writer = await self._socks5_connect(thost, tport)
                    for h in headers:
                        up_writer.write(h)
                    up_writer.write(b'\r\n')
                    await up_writer.drain()
                    await asyncio.gather(self._pipe(client_reader, up_writer), self._pipe(up_reader, client_writer))
                else:
                    client_writer.close()
        except Exception:
            try:
                client_writer.close()
            except Exception:
                pass

    async def start(self) -> int:
        self.server = await asyncio.start_server(self._handle_client, '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
