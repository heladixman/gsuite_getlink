from typing import Dict, Type
from offers.base_offer import BaseOffer
from offers.offer_5seat import Offer5Seat, Offer7Seat
from offers.offer_30d import Offer30D, OfferTrial7D
from offers.offer_skip import OfferSkip

OFFER_REGISTRY: Dict[str, Type[BaseOffer]] = {
    "5seat": Offer5Seat,
    "5_seat": Offer5Seat,
    "30d_5seat": Offer5Seat,
    "7seat": Offer5Seat,
    "30d_7seat": Offer5Seat,
    "30d": Offer30D,
    "individual": Offer30D,
    "offer_30d": Offer30D,
    "trial_30d": Offer30D,
    "trial_7d": Offer30D,
    "trial": Offer30D,
    "skip": OfferSkip
}


def get_offer_handler(claim_type: str = "5seat") -> BaseOffer:
    """
    Factory function returning the appropriate Offer handler instance.
    Defaults to Offer5Seat if unrecognized.
    """
    handler_cls = OFFER_REGISTRY.get((claim_type or "").lower(), Offer5Seat)
    return handler_cls()


__all__ = [
    "BaseOffer",
    "Offer5Seat",
    "Offer7Seat",
    "Offer30D",
    "OfferTrial7D",
    "OfferSkip",
    "OFFER_REGISTRY",
    "get_offer_handler"
]
