from typing import Callable, Optional
from core.logger import BotLogger
from offers.base_offer import BaseOffer


class OfferSkip(BaseOffer):
    """Handler for skipping claim (saving session only)."""
    
    name = "Skip Claim (Save Session Only)"

    async def process_offer(
        self,
        page,
        logger: BotLogger,
        captured_holder: dict,
        frame_callback: Optional[Callable[[bytes, str], None]] = None,
        is_stopped_check: Optional[Callable[[], bool]] = None
    ) -> Optional[str]:
        await self.open_my_edit(page, logger, frame_callback, is_stopped_check)
        await self.dismiss_popups_and_modals(page, logger, frame_callback, is_stopped_check)
        logger.log("Pilihan 'Lewati Klaim' aktif: Sesi login berhasil disimpan tanpa checkout.")
        return "SESSION_SAVED"
