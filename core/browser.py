import asyncio
import hashlib
import json
import os
import random
from typing import Callable, Optional
from core.logger import BotLogger
from core.proxy import get_random_proxy, get_high_speed_proxy, LocalSocksBridge


def generate_profile_fingerprint(profile_path: str) -> dict:
    """Generates unique deterministic hardware & browser fingerprint values based on profile path."""
    seed_int = int(hashlib.md5(profile_path.encode()).hexdigest(), 16)
    rng = random.Random(seed_int)

    resolutions = [
        {"width": 1920, "height": 1080},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
        {"width": 1600, "height": 900},
        {"width": 1366, "height": 768}
    ]
    res = rng.choice(resolutions)

    gpus = [
        {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"}
    ]
    gpu = rng.choice(gpus)

    cores = rng.choice([8, 12, 16, 6])
    memory = rng.choice([8, 16])
    noise_seed = rng.randint(1, 999999)

    return {
        "viewport": res,
        "gpu": gpu,
        "cores": cores,
        "memory": memory,
        "noise_seed": noise_seed
    }


async def capture_frame(page, frame_callback: Optional[Callable[[bytes, str], None]] = None) -> Optional[str]:
    """Captures a screenshot frame for the live monitor."""
    if not page or page.is_closed():
        return None
    try:
        current_url = page.url
        screenshot_bytes = await page.screenshot(type="jpeg", quality=65)
        if frame_callback:
            frame_callback(screenshot_bytes, current_url)
        return current_url
    except Exception:
        return None


async def safe_goto(
    page,
    url: str,
    max_retries: int = 3,
    timeout: int = 45000,
    wait_until: str = "domcontentloaded",
    is_stopped_check: Optional[Callable[[], bool]] = None,
    logger: Optional[BotLogger] = None
) -> bool:
    """Navigates to URL with automatic retry and custom timeout to prevent connection timeout failures."""
    for attempt in range(1, max_retries + 1):
        if is_stopped_check and is_stopped_check():
            return False
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            return True
        except Exception as e:
            if logger:
                logger.log(f"[Percobaan {attempt}/{max_retries}] Gagal membuka {url} (Error: {e})")
            if attempt < max_retries:
                if logger:
                    logger.log(f"Mencoba ulang membuka halaman dalam {attempt * 2} detik...")
                await asyncio.sleep(attempt * 2)
            else:
                raise e
    return False


async def launch_browser_context(
    playwright,
    profile_path: str,
    logger: Optional[BotLogger] = None,
    proxy: Optional[dict] = None
):
    """Launches Google Chrome persistent context with unique hardware fingerprint, Indonesian locale, proxy, and stealth args."""
    fp = generate_profile_fingerprint(profile_path)
    
    if proxy is None:
        proxy, _ = await get_high_speed_proxy(logger=logger)
    elif proxy is False:
        proxy = None

    if logger:
        msg = f"Meluncurkan browser Google Chrome Resmi (Resolusi: {fp['viewport']['width']}x{fp['viewport']['height']}, CPU: {fp['cores']} Cores, RAM: {fp['memory']}GB)"
        if proxy:
            server_host = proxy.get('server', '').replace('http://', '').replace('https://', '')
            msg += f" [Proxy: {server_host}]..."
        else:
            msg += "..."
        logger.log(msg)
    
    launch_kwargs = {
        "user_data_dir": profile_path,
        "channel": "chrome",
        "headless": False,
        "locale": "id-ID",
        "timezone_id": "Asia/Jakarta",
        "extra_http_headers": {
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"'
        },
        "viewport": fp["viewport"],
        "ignore_default_args": ["--enable-automation"],
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--lang=id-ID",
            "--accept-lang=id-ID,id",
            "--window-position=-9999,-9999",
            f"--window-size={fp['viewport']['width']},{fp['viewport']['height']}"
        ]
    }
    bridge = None
    if proxy:
        protocol = proxy.get("protocol", "http").lower()
        if protocol == "socks5" or proxy.get("server", "").startswith("socks5://"):
            upstream_host = proxy.get("host") or proxy["server"].split("://", 1)[1].split(":")[0]
            upstream_port = proxy.get("port") or int(proxy["server"].split(":")[-1])
            bridge = LocalSocksBridge(upstream_host, upstream_port, proxy["username"], proxy["password"])
            local_port = await bridge.start()
            launch_kwargs["proxy"] = {
                "server": f"http://127.0.0.1:{local_port}"
            }
        else:
            launch_kwargs["proxy"] = {
                "server": proxy["server"],
                "username": proxy["username"],
                "password": proxy["password"]
            }

    try:
        context = await playwright.chromium.launch_persistent_context(**launch_kwargs)
    except Exception:
        launch_kwargs.pop("channel", None)
        context = await playwright.chromium.launch_persistent_context(**launch_kwargs)

    if bridge:
        context._proxy_bridge = bridge
        context.on("close", lambda ctx: asyncio.create_task(bridge.stop()))

    # Inject stealth and unique hardware fingerprint scripts
    try:
        await context.add_init_script("""
            (fp) => {
                // 1. Hide automation flags & mock chrome object
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = {
                    app: { isInstalled: false, InstallState: { DISABLED: 'DISABLED', INSTALLED: 'INSTALLED', NOT_INSTALLED: 'NOT_INSTALLED' }, RunningState: { CANNOT_RUN: 'CANNOT_RUN', READY_TO_RUN: 'READY_TO_RUN', RUNNING: 'RUNNING' } },
                    runtime: { OnInstalledReason: {}, OnRestartRequiredReason: {}, PlatformArch: {}, PlatformNaclArch: {}, PlatformOs: {}, RequestUpdateCheckStatus: {} }
                };

                // 2. Hardware specs spoofing per profile
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => fp.cores });
                Object.defineProperty(navigator, 'deviceMemory', { get: () => fp.memory });
                Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
                Object.defineProperty(navigator, 'pdfViewerEnabled', { get: () => true });

                // 3. WebGL Vendor & Renderer spoofing per profile
                const getParam = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(param) {
                    if (param === 37445) return fp.gpu.vendor;
                    if (param === 37446) return fp.gpu.renderer;
                    return getParam.apply(this, arguments);
                };
                if (typeof WebGL2RenderingContext !== 'undefined') {
                    const getParam2 = WebGL2RenderingContext.prototype.getParameter;
                    WebGL2RenderingContext.prototype.getParameter = function(param) {
                        if (param === 37445) return fp.gpu.vendor;
                        if (param === 37446) return fp.gpu.renderer;
                        return getParam2.apply(this, arguments);
                    };
                }

                // 4. Subtle Canvas micro-noise for unique canvas fingerprint hash
                const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
                CanvasRenderingContext2D.prototype.getImageData = function() {
                    const imgData = origGetImageData.apply(this, arguments);
                    const data = imgData.data;
                    if (data.length > 4) {
                        const shift = (fp.noise_seed % 2 === 0) ? 1 : -1;
                        data[0] = Math.max(0, Math.min(255, data[0] + shift));
                    }
                    return imgData;
                };
            }
        """, fp)
    except Exception:
        pass

    # Set Indonesian regional cookies for CapCut
    try:
        await context.add_cookies([
            {"name": "store-region", "value": "id-id", "domain": ".capcut.com", "path": "/"},
            {"name": "store-country-code", "value": "id", "domain": ".capcut.com", "path": "/"},
            {"name": "i18n-lang", "value": "id-ID", "domain": ".capcut.com", "path": "/"},
            {"name": "lang", "value": "id", "domain": ".capcut.com", "path": "/"}
        ])
    except Exception:
        pass

    return context


def attach_cashier_interceptor(context, on_link_captured: Callable[[str], None], logger: Optional[BotLogger] = None):
    """
    Attaches response listener for init_trade direct API capture
    and auto-closes cashier popup windows instantly so client scripts don't run.
    """
    async def on_resp(r):
        if "init_trade" in r.url and r.status == 200:
            try:
                d = await r.json()
                raw = d.get("response")
                obj = json.loads(raw) if isinstance(raw, str) else d.get("data", {})
                u = obj.get("pipo_aggregate_pay_info", {}).get("cashier_url")
                if u:
                    on_link_captured(u)
                    if logger:
                        logger.log(f"⚡ [INSTANT API CAPTURE] Link Pipopay Cashier berhasil diperoleh dari network response: {u}")
            except Exception:
                pass

    context.on("response", on_resp)

    def on_new_page(new_p):
        try:
            p_url = new_p.url or ""
            if "pipopay.com" in p_url or "cashier" in p_url:
                on_link_captured(p_url)
                asyncio.create_task(new_p.close())
        except Exception:
            pass

    context.on("page", on_new_page)