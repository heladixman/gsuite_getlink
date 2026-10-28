import asyncio
from typing import Callable, Optional
from core.logger import BotLogger
from core.browser import safe_goto, capture_frame
from core.queue_manager import UPGRADE_QUEUE_LOCK


class BaseOffer:
    """Base offer class containing shared logic for my-edit navigation, modal dismissing, and queue handling."""
    
    name = "Base Offer"

    async def open_my_edit(
        self,
        page,
        logger: BotLogger,
        frame_callback: Optional[Callable[[bytes, str], None]] = None,
        is_stopped_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        """Navigates to my-edit dashboard in Indonesian language."""
        logger.log("Membuka halaman dashboard CapCut: https://www.capcut.com/my-edit?from_page=landing_page&lang=id-ID...")
        ok = await safe_goto(
            page,
            "https://www.capcut.com/my-edit?from_page=landing_page&lang=id-ID",
            max_retries=3,
            timeout=45000,
            wait_until="domcontentloaded",
            is_stopped_check=is_stopped_check,
            logger=logger
        )
        await asyncio.sleep(4)
        await capture_frame(page, frame_callback)
        return ok

    async def dismiss_popups_and_modals(
        self,
        page,
        logger: BotLogger,
        frame_callback: Optional[Callable[[bytes, str], None]] = None,
        is_stopped_check: Optional[Callable[[], bool]] = None
    ):
        """Dismisses onboarding popups ('Skip'/'Lewati'), feature modals ('Kabar terbaru' / operation-features-modal), etc."""
        logger.log("Memeriksa popup onboarding dan modal berita terbaru...")
        for _ in range(5):
            if page.is_closed() or (is_stopped_check and is_stopped_check()):
                break

            action_taken = False

            # 1. Skip / Lewati selectors (Onboarding / Guides)
            skip_selectors = [
                ".skip-mrkR37",
                "div[class*='skip']:has-text('Skip')",
                "div[class*='skip']:has-text('Lewati')",
                "div:text-is('Skip')",
                "div:text-is('Lewati')",
                "button:has-text('Skip')",
                "button:has-text('Lewati')",
                "button:has-text('Got it')",
                "button:has-text('Mengerti')"
            ]
            for s_sel in skip_selectors:
                try:
                    btn = page.locator(s_sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.scroll_into_view_if_needed()
                        await btn.click(timeout=2500, force=True)
                        logger.log(f"Tombol skip onboarding '{s_sel}' berhasil diklik!")
                        action_taken = True
                        await asyncio.sleep(1.5)
                        await capture_frame(page, frame_callback)
                        break
                except Exception:
                    pass

            # 2. Modal Close Icons (e.g. 'Dapatkan Pro diskon 40%' / 'Kabar terbaru' / operation-features-modal / global-modal / lv-modal-close-icon)
            close_selectors = [
                ".global-modal-H8tDM4 .lv-modal-close-icon",
                ".global-modal-H8tDM4 span[aria-label='Close']",
                "div[class*='global-modal'] .lv-modal-close-icon",
                ".lv-modal:has-text('Dapatkan Pro') .lv-modal-close-icon",
                ".lv-modal-closable .lv-modal-close-icon",
                "span.lv-icon-hover.lv-modal-close-icon",
                ".operation-features-modal .lv-modal-close-icon",
                ".operation-features-modal span[aria-label='Close']",
                ".lv-modal .lv-modal-close-icon",
                "span.lv-modal-close-icon",
                ".lv-modal-close-icon",
                "span[role='button'][aria-label='Close']",
                ".lv-icon-lv-close",
                ".arco-modal-close-btn",
                "button[aria-label='Close']",
                "svg.lv-icon-lv-close"
            ]
            for c_sel in close_selectors:
                try:
                    btn = page.locator(c_sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.scroll_into_view_if_needed()
                        box = await btn.bounding_box()
                        if box:
                            await page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                        await btn.click(timeout=2500, force=True)
                        logger.log(f"Tombol close popup/modal '{c_sel}' berhasil diklik!")
                        action_taken = True
                        await asyncio.sleep(1.5)
                        await capture_frame(page, frame_callback)
                        break
                except Exception:
                    pass

            # 3. Fallback JavaScript dispatch for lv-modal close button
            try:
                js_closed = await page.evaluate("""() => {
                    const closeBtn = document.querySelector(
                        '.global-modal-H8tDM4 .lv-modal-close-icon, ' +
                        'div[class*="global-modal"] .lv-modal-close-icon, ' +
                        '.lv-modal-closable .lv-modal-close-icon, ' +
                        '.operation-features-modal .lv-modal-close-icon, ' +
                        '.lv-modal-close-icon, ' +
                        'span.lv-modal-close-icon, ' +
                        '[aria-label="Close"].lv-modal-close-icon, ' +
                        '.operation-features-modal [aria-label="Close"], ' +
                        'span[role="button"][aria-label="Close"]'
                    );
                    if (closeBtn && (closeBtn.offsetWidth > 0 || closeBtn.offsetHeight > 0)) {
                        closeBtn.click();
                        ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {
                            closeBtn.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
                        });
                        return true;
                    }
                    return false;
                }""")
                if js_closed:
                    logger.log("Tombol close modal berhasil diklik via JavaScript dispatch!")
                    action_taken = True
                    await asyncio.sleep(1.5)
                    await capture_frame(page, frame_callback)
            except Exception:
                pass

            if not action_taken:
                break

    async def ensure_pricing_modal_open(
        self,
        page,
        logger: BotLogger,
        frame_callback: Optional[Callable[[bytes, str], None]] = None
    ):
        """Ensures the pricing / upgrade modal is visible on page."""
        is_modal_open = await page.locator('section.subscriptionProductSection-teams, section.subscriptionSeatSelector').count() > 0
        if not is_modal_open:
            logger.log("Mencari dan mengklik tombol 'Upgrade / Tingkatkan' di navbar...")
            upgrade_selectors = [
                "button:has-text('Tingkatkan')",
                "button:has-text('Upgrade')",
                "div[role='button']:has-text('Tingkatkan')",
                "div[role='button']:has-text('Upgrade')",
                "span:has-text('Tingkatkan')",
                "span:has-text('Upgrade')"
            ]
            for u_sel in upgrade_selectors:
                try:
                    u_btn = page.locator(u_sel).first
                    if await u_btn.count() > 0 and await u_btn.is_visible():
                        await u_btn.scroll_into_view_if_needed()
                        await u_btn.click(timeout=3000)
                        logger.log(f"Tombol '{u_sel}' berhasil diklik! Menunggu popup penawaran muncul...")
                        await asyncio.sleep(2)
                        await capture_frame(page, frame_callback)
                        break
                except Exception:
                    pass

        # Select 'Bulanan diskon' tab if present
        try:
            tab_bulanan = page.locator("div:has-text('Bulanan diskon'), button:has-text('Bulanan')").first
            if await tab_bulanan.count() > 0 and await tab_bulanan.is_visible():
                await tab_bulanan.click(timeout=2000)
                await asyncio.sleep(0.5)
        except Exception:
            pass

    async def wait_for_cashier_link(
        self,
        page,
        captured_holder: dict,
        logger: BotLogger,
        is_stopped_check: Optional[Callable[[], bool]] = None
    ) -> Optional[str]:
        """Waits for cashier link captured from init_trade network response or fallback tab."""
        cashier_url = None
        for _ in range(25):
            if is_stopped_check and is_stopped_check():
                break
            if captured_holder.get("link"):
                cashier_url = captured_holder["link"]
                break
            for p_check in page.context.pages:
                try:
                    p_url = p_check.url
                    if "pipopay.com" in p_url or "cashier" in p_url:
                        cashier_url = p_url
                        captured_holder["link"] = p_url
                        break
                except Exception:
                    pass
            if cashier_url:
                break
            await asyncio.sleep(0.2)

        # Close any open popup pages
        try:
            for p_check in list(page.context.pages):
                if p_check != page and not p_check.is_closed():
                    await p_check.close()
        except Exception:
            pass

        return cashier_url or captured_holder.get("link")

    async def execute_offer_flow(
        self,
        page,
        logger: BotLogger,
        frame_callback: Optional[Callable[[bytes, str], None]] = None
    ):
        """Override this method in subclasses to perform specific offer UI actions."""
        raise NotImplementedError("Subclasses must implement execute_offer_flow")

    async def process_offer(
        self,
        page,
        logger: BotLogger,
        captured_holder: dict,
        frame_callback: Optional[Callable[[bytes, str], None]] = None,
        is_stopped_check: Optional[Callable[[], bool]] = None
    ) -> Optional[str]:
        """Main template method executing the offer pipeline."""
        # 1. Open my-edit
        await self.open_my_edit(page, logger, frame_callback, is_stopped_check)
        if is_stopped_check and is_stopped_check():
            return None

        # 2. Dismiss popups & modals
        await self.dismiss_popups_and_modals(page, logger, frame_callback, is_stopped_check)

        # 3. Ensure pricing modal open
        await self.ensure_pricing_modal_open(page, logger, frame_callback)

        # 4. Wait for queue lock and execute offer checkout
        logger.log("Menunggu antrean giliran klik Upgrade (1 per 1 akun aktif)...")
        cashier_url = None

        async with UPGRADE_QUEUE_LOCK:
            logger.log(f"Giliran antrean didapatkan! Memulai alur offer: {self.name}...")
            await self.execute_offer_flow(page, logger, frame_callback)
            cashier_url = await self.wait_for_cashier_link(page, captured_holder, logger, is_stopped_check)
            logger.log("Proses upgrade akun ini selesai. Memberikan giliran antrean ke browser berikutnya...")

        return cashier_url
