import os
from pathlib import Path
import toml

def sync_secrets():
    root = Path(__file__).resolve().parent
    sec_file = root / ".streamlit" / "secrets.toml"
    env_file = root / ".env"

    if sec_file.exists():
        try:
            data = toml.load(str(sec_file))
            with open(env_file, "w", encoding="utf-8") as f:
                for k, v in data.items():
                    if isinstance(v, (str, int, float, bool)):
                        f.write(f'{k}="{v}"\n')
            print(f"[OK] Successfully synced {len(data)} secrets from .streamlit/secrets.toml to .env")
            return True
        except Exception as e:
            print(f"[!] Error syncing secrets.toml: {e}")
            return False
    else:
        print("[!] .streamlit/secrets.toml not found on disk.")
        return False

if __name__ == "__main__":
    sync_secrets()
