import asyncio
from typing import Callable, Optional
from core.logger import BotLogger
from core.browser import capture_frame
from offers.base_offer import BaseOffer


class Offer5Seat(BaseOffer):
    """Handler for the 30-Day 5-Seat Team Offer."""
    
    name = "30-Day 5-Seat Team Offer"

    async def execute_offer_flow(
        self,
        page,
        logger: BotLogger,
        frame_callback: Optional[Callable[[bytes, str], None]] = None
    ):
        # 1. Open seat selector dropdown
        logger.log("Membuka dropdown pemilihan kursi (section.subscriptionProductSection-teams)...")
        try:
            seat_trigger = page.locator('section.subscriptionProductSection-teams section.subscriptionSeatSelector button.subscriptionSeatSelector-trigger, section.subscriptionSeatSelector button.subscriptionSeatSelector-trigger').first
            if await seat_trigger.count() > 0:
                await seat_trigger.scroll_into_view_if_needed()
                await seat_trigger.click(timeout=3000, force=True)
                await asyncio.sleep(0.8)
                await capture_frame(page, frame_callback)

                # 2. Select 5 seats inside dropdown panel
                logger.log("Memilih opsi '5 kursi' pada div.subscriptionSeatSelector-panel...")
                seat_opt = page.locator(
                    'div.subscriptionSeatSelector-panel button.subscriptionSeatSelector-option:has(span[title*="5"]), '
                    'div.subscriptionSeatSelector-panel button.subscriptionSeatSelector-option:has-text("5 kursi"), '
                    'div.subscriptionSeatSelector-panel button.subscriptionSeatSelector-option:has-text("5 seats"), '
                    'button.subscriptionSeatSelector-option:has(span[title*="5"])'
                ).first
                if await seat_opt.count() > 0:
                    await seat_opt.scroll_into_view_if_needed()
                    await seat_opt.click(timeout=3000, force=True)
                    logger.log("Opsi '5 kursi' berhasil dipilih!")
                    await asyncio.sleep(0.8)
                    await capture_frame(page, frame_callback)
        except Exception as e:
            logger.log(f"Info pemilihan kursi: {e}")

        # 3. Click Upgrade button from section.subscriptionProductSection-teams
        logger.log("Mengklik tombol 'Upgrade / Tingkatkan' pada section.subscriptionProductSection-teams...")
        try:
            checkout_btn = page.locator('section.subscriptionProductSection-teams button.subscriptionProductSection-action, section.subscriptionProductSection-teams button.subscriptionProductSection-actionDark, section.subscriptionProductSection-teams button:has(span.subscriptionProductSection-actionText)').first
            if await checkout_btn.count() > 0:
                await checkout_btn.scroll_into_view_if_needed()
                await checkout_btn.click(timeout=4000, force=True)
                logger.log("Tombol Upgrade paket 5 kursi berhasil diklik! Menunggu response init_trade API...")
            
            await page.evaluate("""() => {
                const btn = document.querySelector('section.subscriptionProductSection-teams button.subscriptionProductSection-action, button.subscriptionProductSection-action');
                if (btn) btn.click();
            }""")
        except Exception as e:
            logger.log(f"Info klik upgrade: {e}")


# Alias for backward compatibility
Offer7Seat = Offer5Seat

__all__ = ["Offer5Seat", "Offer7Seat"]