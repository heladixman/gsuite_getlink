import asyncio
import random
import re
from typing import Callable, Optional
from core.config import MONTH_NAMES_ID, MONTH_NAMES_EN
from core.logger import BotLogger
from core.browser import safe_goto, capture_frame


async def check_session_obtained(page) -> dict | None:
    """Checks if CapCut session is successfully established and returns user info."""
    if not page or page.is_closed():
        return None
    try:
        js_code = """
        async () => {
            try {
                const res = await fetch("https://www.capcut.com/passport/web/account/info/?aid=348188");
                const data = await res.json();
                if (data && data.data && data.data.user_id) {
                    return data.data;
                }
                return null;
            } catch(e) { return null; }
        }
        """
        return await page.evaluate(js_code)
    except Exception:
        return None


async def handle_birthday_form_once(page, logger: BotLogger, frame_callback: Optional[Callable[[bytes, str], None]] = None):
    """Fills the CapCut birthday form in exact left-to-right order and clicks Lanjutkan."""
    if not page or page.is_closed():
        return

    try:
        content = await page.content()
        if "When's your birthday" in content or "tanggal lahir" in content or "birthday" in content.lower() or "age_gate" in content or "gate_birthday-picker" in content:
            rand_year = random.randint(1995, 2005)
            rand_month_idx = random.randint(0, 11)
            month_id = MONTH_NAMES_ID[rand_month_idx]
            month_en = MONTH_NAMES_EN[rand_month_idx]
            rand_day = random.randint(1, 28)

            logger.log(f"Formulir tanggal lahir terdeteksi! Mengisi: Tahun={rand_year}, Bulan={month_id}, Hari={rand_day}...")
            await capture_frame(page, frame_callback)

            # 1. Fill Year Input
            logger.log(f"[1/4] Mengisi Tahun: {rand_year}...")
            year_input = page.locator('input.gate_birthday-picker-input, input[placeholder="Tahun"], input[placeholder="Year"]').first
            if await year_input.count() > 0:
                await year_input.click(timeout=3000)
                await year_input.fill(str(rand_year))
            await asyncio.sleep(0.5)

            # 2. Select Month
            logger.log(f"[2/4] Membuka dropdown Bulan dan memilih: {month_id} / {month_en}...")
            month_trigger = page.locator('div[aria-controls="lv-select-popup-0"], div.gate_birthday-picker-selector:has(input[placeholder*="an"])').first
            if await month_trigger.count() > 0:
                await month_trigger.click(timeout=3000)
                await asyncio.sleep(0.5)
                month_opt = page.locator(f'#lv-select-popup-0 li:has-text("{month_id}"), #lv-select-popup-0 li:has-text("{month_en}"), .lv-select-popup li:has-text("{month_id}")').first
                if await month_opt.count() > 0:
                    await month_opt.click(timeout=3000)

            # 3. Select Day
            logger.log(f"[3/4] Membuka dropdown Hari dan memilih: {rand_day}...")
            day_trigger = page.locator('div[aria-controls="lv-select-popup-1"], div.gate_birthday-picker-selector:has(input[placeholder*="ar"])').first
            if await day_trigger.count() > 0:
                await day_trigger.click(timeout=3000)
                await asyncio.sleep(0.5)
                day_opt = page.locator('#lv-select-popup-1 li').filter(has_text=re.compile(rf'^\s*{rand_day}\s*$|^\s*{rand_day}\b')).first
                if await day_opt.count() > 0:
                    await day_opt.scroll_into_view_if_needed()
                    await day_opt.click(timeout=3000)

            # 4. Click Continue
            continue_btn = page.locator('button.lv_sign_in_panel_wide-birthday-next, button:has-text("Continue"), button:has-text("Lanjutkan")').first
            if await continue_btn.count() > 0:
                try:
                    await continue_btn.click(timeout=3000, force=True)
                except Exception:
                    pass

            await page.evaluate("""() => {
                const btn = document.querySelector('button.lv_sign_in_panel_wide-birthday-next');
                if (btn) btn.click();
            }""")
            logger.log("Tombol 'Continue' formulir tanggal lahir berhasil diklik!")
            await asyncio.sleep(2)
            await capture_frame(page, frame_callback)
    except Exception as e:
        logger.log(f"Info birthday form: {e}")


async def handle_google_oauth_popup(
    context,
    email: str,
    logger: BotLogger,
    frame_callback: Optional[Callable[[bytes, str], None]] = None,
    is_stopped_check: Optional[Callable[[], bool]] = None,
    timeout_seconds: int = 25,
    password: Optional[str] = None
) -> bool:
    """Handles Google accountchooser / OAuth consent popup tab whenever it opens (from backup_v2)."""
    logger.log(f"Menunggu dan menangani popup Google accountchooser untuk {email}...")
    account_chosen = False

    for _ in range(timeout_seconds):
        if is_stopped_check and is_stopped_check():
            logger.log("Proses dihentikan oleh pengguna.")
            return False

        active_pages = list(context.pages)
        for p in active_pages:
            if p is None or p.is_closed():
                continue

            try:
                p_url = p.url
            except Exception:
                continue

            if "accounts.google.com" in p_url:
                await capture_frame(p, frame_callback)

                # 1. Click the specific Google account
                try:
                    # Find account element via selectors or JS evaluation
                    clicked = await p.evaluate(f"""(userEmail) => {{
                        // Look for exact email container in AccountChooser
                        const candidates = Array.from(document.querySelectorAll('li, div[data-identifier], div[data-email], div[role="link"], div[role="button"], div.JdaQae, div.w1I7fb'));
                        for (const el of candidates) {{
                            if (el.textContent && el.textContent.includes(userEmail)) {{
                                el.scrollIntoView();
                                el.click();
                                const clickTarget = el.querySelector('div, span, button') || el;
                                ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {{
                                    clickTarget.dispatchEvent(new MouseEvent(evt, {{ bubbles: true, cancelable: true, view: window }}));
                                }});
                                return true;
                            }}
                        }}
                        return false;
                    }}""", email)

                    if clicked:
                        logger.log(f"Akun Google {email} berhasil diklik pada popup!")
                        account_chosen = True
                        await asyncio.sleep(2)
                        await capture_frame(p, frame_callback)
                    else:
                        acc_elem = p.locator(f'div:has-text("{email}"), [data-identifier="{email}"], [data-email="{email}"], div[role="link"]:has-text("{email}"), li:has-text("{email}")').first
                        if await acc_elem.count() > 0 and await acc_elem.is_visible():
                            logger.log(f"Memilih akun Google pada popup via Playwright: {email}")
                            await acc_elem.click(timeout=3000, force=True)
                            account_chosen = True
                            await asyncio.sleep(2)
                            await capture_frame(p, frame_callback)
                        else:
                            # Fallback if "Continue as" / "Lanjutkan sebagai" button is shown
                            continue_as = p.locator('button:has-text("Lanjutkan sebagai"), div[role="button"]:has-text("Lanjutkan sebagai"), button:has-text("Continue as"), div[role="button"]:has-text("Continue as")').first
                            if await continue_as.count() > 0 and await continue_as.is_visible():
                                await continue_as.click(timeout=3000, force=True)
                                account_chosen = True
                                await asyncio.sleep(2)
                                await capture_frame(p, frame_callback)
                except Exception as e:
                    logger.log(f"Info pemilihan akun: {e}")

                # 2. Click Continue / Allow / Lanjutkan on OAuth consent screen
                for agree_txt in ["Continue", "Lanjutkan", "Allow", "Izinkan", "Confirm", "Konfirmasi", "Next", "Berikutnya", "Saya setuju", "I agree"]:
                    try:
                        if p.is_closed() or (is_stopped_check and is_stopped_check()):
                            break
                        btn = p.locator(f'button:has-text("{agree_txt}"), div[role="button"]:has-text("{agree_txt}"), #submit_approve_access, button[id*="submit"]').first
                        if await btn.count() > 0 and await btn.is_visible():
                            await btn.scroll_into_view_if_needed()
                            await btn.click(timeout=3000, force=True)
                            logger.log(f"Tombol otorisasi Google '{agree_txt}' berhasil diklik!")
                            await asyncio.sleep(2)
                            await capture_frame(p, frame_callback)
                    except Exception:
                        pass

        if account_chosen:
            remaining = [p for p in context.pages if not p.is_closed() and "accounts.google.com" in p.url]
            if not remaining:
                logger.log("Popup otorisasi Google selesai & tertutup.")
                return True

        await asyncio.sleep(1)

    return account_chosen


async def login_capcut(
    context,
    page,
    email: str,
    logger: BotLogger,
    frame_callback: Optional[Callable[[bytes, str], None]] = None,
    is_stopped_check: Optional[Callable[[], bool]] = None,
    password: Optional[str] = None
) -> bool:
    """Executes CapCut OAuth sign in with Google (matching backup_v2)."""
    # Pre-check: If session is already valid, skip login entirely
    initial_user = await check_session_obtained(page)
    if initial_user:
        logger.log(f"Sesi CapCut sudah aktif ({initial_user.get('screen_name')}). Melewati tahap login.")
        return True

    # Set Indonesian regional cookies
    try:
        await context.add_cookies([
            {"name": "store-region", "value": "id-id", "domain": ".capcut.com", "path": "/"},
            {"name": "store-country-code", "value": "id", "domain": ".capcut.com", "path": "/"},
            {"name": "i18n-lang", "value": "id-ID", "domain": ".capcut.com", "path": "/"},
            {"name": "lang", "value": "id", "domain": ".capcut.com", "path": "/"}
        ])
    except Exception:
        pass

    logger.log("Membuka halaman login CapCut: https://www.capcut.com/account-center/login")
    await safe_goto(
        page,
        "https://www.capcut.com/account-center/login",
        max_retries=3,
        timeout=45000,
        wait_until="domcontentloaded",
        is_stopped_check=is_stopped_check,
        logger=logger
    )
    await asyncio.sleep(3)
    await capture_frame(page, frame_callback)

    # 1. Step: Ensure login modal is open. If not, click "Masuk" / "Sign in"
    logger.log("Memeriksa dan membuka modal opsi login CapCut...")
    modal_elem = page.locator('.lv_new_third_part_sign_in_expand-button, .lv_new_sign_in_panel_wide-1-col-wrapper').first
    if await modal_elem.count() == 0 or not await modal_elem.is_visible():
        signin_selectors = [
            "button.lv-btn:has-text('Masuk')",
            "button:has-text('Masuk')",
            "div[role='tab']:has-text('Masuk')",
            "a:has-text('Masuk')"
        ]
        for s_sel in signin_selectors:
            try:
                s_btn = page.locator(s_sel).first
                if await s_btn.count() > 0:
                    await s_btn.wait_for(state="visible", timeout=4000)
                    await s_btn.click(timeout=3000)
                    logger.log(f"Tombol 'Masuk' ({s_sel}) berhasil diklik.")
                    break
            except Exception:
                pass

    # 2. Step: Wait for and Click "Lanjutkan dengan Google"
    logger.log("Mencari dan menekan tombol 'Lanjutkan dengan Google'...")
    google_loc = page.locator(
        ".lv_new_third_part_sign_in_expand-button:has-text('Google'), "
        "span.lv_new_third_part_sign_in_expand-label:has-text('Google'), "
        "button:has-text('Lanjutkan dengan Google'), "
        "button:has-text('Continue with Google')"
    ).first

    popup_page = None
    try:
        await google_loc.wait_for(state="visible", timeout=8000)
        await google_loc.scroll_into_view_if_needed()
        
        try:
            async with page.expect_popup(timeout=6000) as popup_info:
                await google_loc.click(timeout=4000, force=True)
            popup_page = await popup_info.value
            logger.log("Tombol 'Lanjutkan dengan Google' diklik dan popup berhasil terbuka!")
            await popup_page.bring_to_front()
            await capture_frame(popup_page, frame_callback)
        except Exception:
            # Direct click if popup already opened or expect_popup timed out
            await google_loc.click(timeout=3000, force=True)
            logger.log("Tombol 'Lanjutkan dengan Google' diklik.")
    except Exception as e:
        logger.log(f"Info click Google button: {e}")
        # JS fallback click
        try:
            await page.evaluate("""() => {
                const btn = document.querySelector('.lv_new_third_part_sign_in_expand-button');
                if (btn) {
                    btn.click();
                    ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {
                        btn.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
                    });
                }
            }""")
            logger.log("Tombol Google di-trigger via JavaScript dispatch fallback.")
        except Exception:
            pass

    await asyncio.sleep(2)

    # 3. Handle First Google OAuth Popup
    await handle_google_oauth_popup(context, email, logger, frame_callback, is_stopped_check, timeout_seconds=20, password=password)

    # 4. Handle Birthday Form
    logger.log("Memeriksa formulir tanggal lahir (Birthday Form)...")
    await asyncio.sleep(3)
    await capture_frame(page, frame_callback)
    await handle_birthday_form_once(page, logger, frame_callback)

    # 5. Handle Second Google OAuth Popup (opened after birthday continue)
    logger.log("Menunggu popup autentikasi Google lanjutan setelah formulir tanggal lahir...")
    await asyncio.sleep(2)
    await handle_google_oauth_popup(context, email, logger, frame_callback, is_stopped_check, timeout_seconds=20, password=password)

    # 6. Wait until CapCut session & cookies are filled and strictly verified (exact from v2)
    logger.log("Memverifikasi sesi akun dan cookies CapCut...")
    user_info = None
    for attempt in range(15):
        if is_stopped_check and is_stopped_check():
            return False

        user_info = await check_session_obtained(page)
        if user_info:
            name = user_info.get("screen_name", "User")
            uid = user_info.get("user_id", "")
            logger.log(f"Sesi akun CapCut berhasil diverifikasi! Pengguna: {name} (ID: {uid})")
            logger.log("Menunggu jeda 3 detik sebelum menuju ke dashboard my-edit...")
            await asyncio.sleep(3)
            return True

        # If not yet obtained, also check for any pending Google popups
        active_popups = [p for p in context.pages if not p.is_closed() and "accounts.google.com" in p.url]
        if active_popups:
            await handle_google_oauth_popup(context, email, logger, frame_callback, is_stopped_check, timeout_seconds=5, password=password)

        await asyncio.sleep(1.5)

    logger.log(f"[GAGAL] Sesi akun CapCut TIDAK berhasil diperoleh untuk {email}! Menghentikan alur akun ini.")
    return False