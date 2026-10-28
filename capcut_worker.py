import asyncio
import json
import os
import sys
import re
import time
import urllib.request
from typing import Callable, Optional
from playwright.async_api import async_playwright

# Ensure project root is in python search path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from core.config import (
    BASE_DIR, PROFILES_DIR, ACCOUNTS_FILE, RESULTS_FILE, OUTPUT_FILE, PROXY_FILE,
    APP_ID, REGION, PRODUCT_ID, SKU_ID, SKU_PLAN_ID, PRICE, CURRENCY,
    get_max_proxy_latency
)
from core.logger import BotLogger
from core.queue_manager import UPGRADE_QUEUE_LOCK
from core.cleanup import cleanup_account_profile, cleanup_project_data
from core.browser import launch_browser_context, capture_frame, attach_cashier_interceptor
from core.google_auth import login_google
from core.capcut_auth import login_capcut
from core.proxy import get_random_proxy, get_high_speed_proxy, query_ip_via_socks5
from offers import get_offer_handler


class CapcutWorker:
    """
    Main Orchestrator Worker for CapCut Automation.
    Coordinates browser initialization, Google authentication, CapCut session setup,
    and plug-and-play offer claiming.
    """

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, frame_callback: Optional[Callable[[bytes, str], None]] = None):
        self.logger = BotLogger(log_callback)
        self.frame_callback = frame_callback
        self.is_running = False
        self.should_stop = False
        self.current_url = "about:blank"
        self.captured_pipopay = None

    def is_stopped(self) -> bool:
        return self.should_stop

    async def _log_network_ip(self, email: str, proxy: Optional[dict] = None):
        """Helper to log public IP and location information."""
        try:
            ip_data = None
            if proxy:
                proto = proxy.get("protocol", "http").lower()
                if proto == "socks5" or proxy.get("server", "").startswith("socks5://"):
                    upstream_host = proxy.get("host") or proxy["server"].split("://", 1)[1].split(":")[0]
                    upstream_port = proxy.get("port") or int(proxy["server"].split(":")[-1])
                    ip_data = await query_ip_via_socks5(
                        upstream_host, upstream_port, proxy["username"], proxy["password"]
                    )

            if not ip_data:
                opener = None
                if proxy and "server" in proxy and not proxy.get("server", "").startswith("socks5://"):
                    server = proxy["server"].replace("http://", "").replace("https://", "")
                    user = proxy.get("username", "")
                    pwd = proxy.get("password", "")
                    proxy_url = f"http://{user}:{pwd}@{server}" if user and pwd else f"http://{server}"
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))

                if opener:
                    with opener.open("http://ipinfo.io/json", timeout=8) as ip_res:
                        ip_data = json.loads(ip_res.read().decode())
                else:
                    with urllib.request.urlopen("https://ipinfo.io/json", timeout=5) as ip_res:
                        ip_data = json.loads(ip_res.read().decode())

            if ip_data:
                ip_str = ip_data.get("ip", "Unknown")
                country = ip_data.get("country", "ID")
                city = ip_data.get("city", "")
                org = ip_data.get("org", "")
                self.logger.log(f"[{email}] IP Jaringan Saat Ini: {ip_str} (Negara: {country}, Lokasi: {city}, ISP: {org})")
        except Exception:
            try:
                with urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5) as ip_res:
                    ip_data = json.loads(ip_res.read().decode())
                self.logger.log(f"[{email}] IP Jaringan Saat Ini: {ip_data.get('ip', 'Unknown')}")
            except Exception:
                pass

    async def process_single_account(self, email: str, password: str, claim_type: str = "5seat", use_proxy: bool = True) -> dict:
        self.is_running = True
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', email)
        profile_path = os.path.join(PROFILES_DIR, safe_name)
        
        # Step 0: Ensure a clean fresh profile directory on disk
        cleanup_account_profile(profile_path)
        os.makedirs(profile_path, exist_ok=True)

        result_data = {"email": email, "status": "DIPROSES", "link": None, "error": None}
        t_start = time.time()

        try:
            proxy_config = None
            if use_proxy:
                # Test proxy first and only allow high-speed proxy before launching browser
                self.logger.log(f"[{email}] [PROXY AKTIF] Menguji koneksi & kecepatan proxy dari proxy.txt...")
                proxy_config, ip_data = await get_high_speed_proxy(
                    logger=self.logger,
                    max_latency_ms=get_max_proxy_latency()
                )

                if not proxy_config and os.path.exists(PROXY_FILE):
                    raise Exception("Semua percobaan koneksi proxy gagal atau tidak ada proxy berkecepatan tinggi yang merespons!")

                if ip_data:
                    ip_str = ip_data.get("ip", "Unknown")
                    country = ip_data.get("country", "ID")
                    city = ip_data.get("city", "")
                    org = ip_data.get("org", "")
                    self.logger.log(f"[{email}] IP Jaringan Terverifikasi: {ip_str} (Negara: {country}, Lokasi: {city}, ISP: {org})")
                else:
                    await self._log_network_ip(email, proxy=proxy_config)
            else:
                self.logger.log(f"[{email}] [PROXY NONAKTIF] Browser menggunakan koneksi internet langsung (Direct Connection).")
                await self._log_network_ip(email, proxy=None)

            async with async_playwright() as p:
                context = await launch_browser_context(p, profile_path, self.logger, proxy=proxy_config if use_proxy else False)
                page = context.pages[0] if context.pages else await context.new_page()

                # Holder dict for thread-safe instant API response capture
                captured_holder = {"link": None}

                def on_link_captured(link: str):
                    captured_holder["link"] = link
                    self.captured_pipopay = link

                attach_cashier_interceptor(context, on_link_captured, self.logger)

                try:
                    # Step 1: Google Sign-In v3
                    google_ok = await login_google(
                        page=page,
                        email=email,
                        password=password,
                        logger=self.logger,
                        frame_callback=self.frame_callback,
                        is_stopped_check=self.is_stopped
                    )
                    if self.should_stop:
                        result_data["status"] = "DIHENTIKAN"
                        return result_data

                    # Step 2: CapCut Login via Google & Session Verification
                    login_ok = await login_capcut(
                        context=context,
                        page=page,
                        email=email,
                        logger=self.logger,
                        frame_callback=self.frame_callback,
                        is_stopped_check=self.is_stopped,
                        password=password
                    )
                    if self.should_stop:
                        result_data["status"] = "DIHENTIKAN"
                        return result_data

                    if not login_ok:
                        self.logger.log(f"Sesi CapCut tidak aktif untuk {email}. Proses dihentikan.")
                        result_data["status"] = "GAGAL"
                        result_data["error"] = "Sesi akun CapCut tidak aktif"
                        return result_data

                    # Step 3: Execute Offer Strategy (5seat, trial_7d, etc.)
                    offer_handler = get_offer_handler(claim_type)
                    self.logger.log(f"Menjalankan alur offer: '{offer_handler.name}' (Tipe: {claim_type})...")
                    
                    final_link = await offer_handler.process_offer(
                        page=page,
                        logger=self.logger,
                        captured_holder=captured_holder,
                        frame_callback=self.frame_callback,
                        is_stopped_check=self.is_stopped
                    )

                    if final_link == "SESSION_SAVED":
                        result_data["status"] = "SUKSES"
                        result_data["link"] = "SESSION_SAVED"
                    elif final_link:
                        self.logger.log(f"Pipopay Cashier URL berhasil digenerate & diamankan: {final_link}")
                        result_data["status"] = "SUKSES"
                        result_data["link"] = final_link
                        
                        # Save results securely to files immediately
                        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
                            f.write(f"{email}|{password}\n{final_link}\n\n")
                        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {final_link}\n")
                        
                        self.logger.log("Data link berhasil disimpan. Menutup seluruh jendela browser seketika...")
                    else:
                        self.logger.log("Link Pipopay tidak dapat diambil.")
                        result_data["status"] = "GAGAL"
                        result_data["error"] = "Gagal mengambil cashier_url"

                except Exception as e:
                    self.logger.log(f"Error: {e}")
                    result_data["status"] = "GAGAL"
                    result_data["error"] = str(e)
                finally:
                    # Close context & pages
                    try:
                        for p_item in list(context.pages):
                            if not p_item.is_closed():
                                await p_item.close()
                        await context.close()
                        self.logger.log("Jendela browser berhasil ditutup sempurna.")
                    except Exception:
                        pass

                    # Step 4: Auto clean profile directory immediately from disk
                    cleanup_account_profile(profile_path)
                    self.logger.log(f"Profile cache & storage untuk {email} berhasil dibersihkan dari disk.")
        finally:
            elapsed = time.time() - t_start
            mins, secs = divmod(elapsed, 60)
            dur_str = f"{int(mins)}m {secs:.1f}s" if mins > 0 else f"{secs:.1f}s"
            self.logger.log(f"[{email}] Selesai diproses dalam {dur_str} (Status: {result_data['status']})")

        return result_data


# Exported symbols for full backward compatibility
__all__ = [
    "CapcutWorker",
    "RESULTS_FILE",
    "OUTPUT_FILE",
    "UPGRADE_QUEUE_LOCK",
    "cleanup_project_data"
]