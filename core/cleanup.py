import os
import shutil
from core.config import BASE_DIR, PROFILES_DIR


def cleanup_account_profile(profile_path: str):
    """Deletes an account's temporary profile folder completely from disk."""
    try:
        if os.path.exists(profile_path):
            shutil.rmtree(profile_path, ignore_errors=True)
    except Exception:
        pass


def cleanup_project_data() -> dict:
    """Cleans up all leftover profiles, crash dumps, and __pycache__ folders in project."""
    cleaned_profiles = 0
    cleaned_pycache = 0

    # 1. Clean profiles directory
    if os.path.exists(PROFILES_DIR):
        try:
            for item in os.listdir(PROFILES_DIR):
                item_path = os.path.join(PROFILES_DIR, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                    cleaned_profiles += 1
                else:
                    os.remove(item_path)
                    cleaned_profiles += 1
        except Exception:
            pass

    # 2. Clean __pycache__ directories
    for root, dirs, files in os.walk(BASE_DIR):
        for d in dirs:
            if d == "__pycache__":
                try:
                    shutil.rmtree(os.path.join(root, d), ignore_errors=True)
                    cleaned_pycache += 1
                except Exception:
                    pass

    return {
        "status": "success",
        "cleaned_profiles": cleaned_profiles,
        "cleaned_pycache": cleaned_pycache
    }