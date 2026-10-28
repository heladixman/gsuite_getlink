import asyncio
import os
import sys
from capcut_worker import CapcutWorker
from core.config import ACCOUNTS_FILE, get_cooling_delay


def read_accounts():
    accounts = []
    if len(sys.argv) > 1 and "|" in sys.argv[1]:
        parts = sys.argv[1].strip().split("|")
        if len(parts) >= 2:
            return [(parts[0].strip(), parts[1].strip())]

    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        accounts.append((parts[0].strip(), parts[1].strip()))
    return accounts


async def main():
    accounts = read_accounts()

    if not accounts:
        print("=" * 65)
        print("Tidak ada akun di accounts.txt!")
        print("Format akun: email|password")
        print("=" * 65)
        user_input = input("Masukkan akun (email|password): ").strip()
        if "|" in user_input:
            parts = user_input.split("|")
            accounts.append((parts[0].strip(), parts[1].strip()))
        else:
            print("[-] Format tidak valid. Keluar.")
            return

    print(f"[*] Menemukan {len(accounts)} akun untuk diproses.")
    worker = CapcutWorker()

    for idx, (email, pwd) in enumerate(accounts, 1):
        print(f"\n>>> Memproses ({idx}/{len(accounts)}): {email}")
        await worker.process_single_account(email, pwd, claim_type="5seat")
        
        if idx < len(accounts):
            cooling_secs = get_cooling_delay()
            if cooling_secs > 0:
                print(f"⏳ [Cooling Process] Jeda {cooling_secs} detik sebelum memproses akun berikutnya...")
                await asyncio.sleep(cooling_secs)

    print("\n[+] Selesai memproses semua akun!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Dihentikan oleh pengguna.")
