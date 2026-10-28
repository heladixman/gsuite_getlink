from typing import Callable, Optional
from core.logger import BotLogger
from offers.base_offer import BaseOffer


class Offer30D(BaseOffer):
    """Handler for the 30-Day Offer."""
    
    name = "30-Day Offer"

    async def execute_offer_flow(
        self,
        page,
        logger: BotLogger,
        frame_callback: Optional[Callable[[bytes, str], None]] = None
    ):
        logger.log("Memilih paket '30 Hari'...")
        try:
            pro_btn = page.locator('section.subscriptionProductSection-pro button.subscriptionProductSection-action, section.subscriptionProductSection-pro button, button:has-text("Rp0"), div:has-text("Pro") button.subscriptionProductSection-action').first
            if await pro_btn.count() > 0:
                await pro_btn.scroll_into_view_if_needed()
                await pro_btn.click(timeout=4000, force=True)
                logger.log("Tombol klaim paket 30D berhasil diklik! Menunggu response init_trade API...")
            
            await page.evaluate("""() => {
                const btn = document.querySelector('section.subscriptionProductSection-pro button.subscriptionProductSection-action, section.subscriptionProductSection-pro button');
                if (btn) btn.click();
            }""")
        except Exception as e:
            logger.log(f"Info klaim 30d: {e}")


# Alias for backward compatibility
OfferTrial7D = Offer30D

__all__ = ["Offer30D", "OfferTrial7D"]
