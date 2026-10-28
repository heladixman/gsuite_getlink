import asyncio
from typing import Callable, Optional
from core.logger import BotLogger
from core.browser import safe_goto, capture_frame


async def login_google(
    page,
    email: str,
    password: str,
    logger: BotLogger,
    frame_callback: Optional[Callable[[bytes, str], None]] = None,
    is_stopped_check: Optional[Callable[[], bool]] = None
) -> bool:
    """Executes modern Google Sign-In v3 flow in Indonesian locale."""
    logger.log(f"Membuka halaman Google Sign-In (v3 Modern Bahasa Indonesia) untuk {email}...")
    
    await safe_goto(
        page,
        "https://accounts.google.com/v3/signin/identifier?hl=id&flowName=GlifWebSignIn&flowEntry=ServiceLogin",
        max_retries=3,
        timeout=45000,
        wait_until="domcontentloaded",
        is_stopped_check=is_stopped_check,
        logger=logger
    )
    await asyncio.sleep(2)
    await capture_frame(page, frame_callback)

    # 1. Email input
    email_input = page.locator('input[type="email"], #identifierId').first
    if await email_input.count() > 0 and await email_input.is_visible():
        logger.log(f"Memasukkan email: {email}...")
        await email_input.fill(email)
        await capture_frame(page, frame_callback)
        await asyncio.sleep(1)
        
        next_btn = page.locator('#identifierNext, button:has-text("Next"), button:has-text("Berikutnya")').first
        await next_btn.click()
        logger.log("Tombol 'Next' email diklik.")
    
    await asyncio.sleep(2)
    await capture_frame(page, frame_callback)

    # 2. Password input
    try:
        passwd_input = page.locator('input[type="password"], input[name="Passwd"], input[name="password"]').first
        await passwd_input.wait_for(state="visible", timeout=12000)
        logger.log("Memasukkan kata sandi...")
        await passwd_input.fill(password)
        await capture_frame(page, frame_callback)
        await asyncio.sleep(1)

        pwd_next_btn = page.locator('#passwordNext, button:has-text("Next"), button:has-text("Berikutnya")').first
        await pwd_next_btn.click()
        logger.log("Tombol 'Next' kata sandi diklik.")
    except Exception as e:
        logger.log(f"Info input sandi: {e}")

    # 3. Wait, scroll to bottom, and click 'I understand' / 'Saya mengerti'
    logger.log("Menunggu halaman lanjutan Google, menggulir ke bawah...")
    for _ in range(15):
        if is_stopped_check and is_stopped_check():
            return False
        
        await capture_frame(page, frame_callback)
        url = page.url

        if "myaccount.google.com" in url or "google.com/search" in url or "accounts.google.com/b/" in url or "accounts.google.com/ManageAccount" in url:
            logger.log("Login Google berhasil! Sesi Google aktif.")
            return True

        try:
            await page.evaluate("""() => {
                window.scrollTo(0, document.body.scrollHeight);
                const scrollables = document.querySelectorAll('div, main, section');
                for (const el of scrollables) {
                    if (el.scrollHeight > el.clientHeight) {
                        el.scrollTop = el.scrollHeight;
                    }
                }
            }""")
        except Exception:
            pass

        await asyncio.sleep(1)

        understand_selectors = [
            'button:has-text("I understand")',
            'button:has-text("Saya mengerti")',
            'div[role="button"]:has-text("I understand")',
            'div[role="button"]:has-text("Saya mengerti")',
            'button:has-text("Accept")',
            'button:has-text("Terima")',
            'span:has-text("I understand")',
            'span:has-text("Saya mengerti")'
        ]
        
        clicked_understand = False
        for u_sel in understand_selectors:
            try:
                btn = page.locator(u_sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.scroll_into_view_if_needed()
                    await btn.click(timeout=4000)
                    logger.log("Tombol 'I understand' / 'Saya mengerti' pada halaman Google berhasil diklik!")
                    clicked_understand = True
                    await asyncio.sleep(2)
                    await capture_frame(page, frame_callback)
                    break
            except Exception:
                pass

        if not clicked_understand:
            for prompt_txt in ["Not now", "Jangan sekarang", "Confirm", "Konfirmasi", "I agree", "Saya setuju", "Continue", "Lanjutkan", "Skip", "Lewati"]:
                try:
                    btn = page.locator(f'button:has-text("{prompt_txt}"), div[role="button"]:has-text("{prompt_txt}")').first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=4000)
                        logger.log(f"Menekan tombol prompt Google: '{prompt_txt}'")
                        await asyncio.sleep(1.5)
                        await capture_frame(page, frame_callback)
                        break
                except Exception:
                    pass

        await asyncio.sleep(1)

    logger.log("Sesi Google berhasil didapatkan! Melanjutkan ke langkah berikutnya...")
    return True