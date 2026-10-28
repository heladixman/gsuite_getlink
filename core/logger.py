import sys
import time
from typing import Callable, Optional


class BotLogger:
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.log_callback = log_callback

    def log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        try:
            print(formatted)
        except UnicodeEncodeError:
            try:
                print(formatted.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8"))
            except Exception:
                print(formatted.encode("ascii", errors="replace").decode("ascii"))
        if self.log_callback:
            try:
                self.log_callback(formatted)
            except Exception:
                pass