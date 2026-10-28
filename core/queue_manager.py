import asyncio

# Global queue lock ensuring only ONE active browser hits Upgrade and acquires Cashier link at a time
UPGRADE_QUEUE_LOCK = asyncio.Lock()