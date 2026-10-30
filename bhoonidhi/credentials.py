"""
Bhoonidhi Credentials Container and Parser.
Provides secure loading of Bhoonidhi credentials from .env files or environment variables.
Sensitive credentials are protected and masked in representations.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Dict


def parse_env_file(filepath: Path | str) -> Dict[str, str]:
    """Parse a .env file into key-value pairs without requiring third-party libraries."""
    env_vars: Dict[str, str] = {}
    path = Path(filepath)
    if not path.is_file():
        return env_vars

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # Strip matching surrounding quotes
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    env_vars[key] = val
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to parse env file at {path}: {type(e).__name__}\n")
    return env_vars


class BhoonidhiCredentials:
    """Secure credentials container for Bhoonidhi API."""

    def __init__(self, user_id: str, password: str):
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string.")
        if not password or not isinstance(password, str) or not password.strip():
            raise ValueError("password must be a non-empty string.")

        self._user_id = user_id.strip()
        self._password = password.strip()

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def password(self) -> str:
        return self._password

    def __repr__(self) -> str:
        masked_id = self._user_id[:3] + "***" if len(self._user_id) > 3 else "***"
        return f"<BhoonidhiCredentials user_id='{masked_id}', password='***'>"

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def load(cls, env_path: Optional[str | Path] = None) -> BhoonidhiCredentials:
        """
        Load credentials from:
        1. Environment variables BHOONIDHI_USER_ID and BHOONIDHI_PASSWORD.
        2. Specified env_path, or default search locations (.env in cwd, parent, or project root).
        """
        user_id = os.environ.get("BHOONIDHI_USER_ID")
        password = os.environ.get("BHOONIDHI_PASSWORD")

        # Try to read from .env if not found in environment
        if not user_id or not password:
            search_paths = []
            if env_path:
                search_paths.append(Path(env_path))
            else:
                cwd = Path.cwd()
                module_dir = Path(__file__).resolve().parent
                project_root = module_dir.parent
                search_paths.extend([
                    cwd / ".env",
                    project_root / ".env",
                    cwd.parent / ".env",
                ])

            for p in search_paths:
                if p.is_file():
                    vars_from_file = parse_env_file(p)
                    if not user_id and "BHOONIDHI_USER_ID" in vars_from_file:
                        user_id = vars_from_file["BHOONIDHI_USER_ID"]
                    if not password and "BHOONIDHI_PASSWORD" in vars_from_file:
                        password = vars_from_file["BHOONIDHI_PASSWORD"]
                    if user_id and password:
                        break

        if not user_id or not password:
            missing = []
            if not user_id:
                missing.append("BHOONIDHI_USER_ID")
            if not password:
                missing.append("BHOONIDHI_PASSWORD")
            raise ValueError(
                f"Missing required Bhoonidhi credentials: {', '.join(missing)}. "
                "Set them in your .env file or environment variables."
            )

        return cls(user_id=user_id, password=password)


def main():
    """CLI helper to verify that credentials can be read without exposing them."""
    print("=" * 60)
    print("Bhoonidhi Credentials Reader & Verification")
    print("=" * 60)

    try:
        creds = BhoonidhiCredentials.load()
        masked_user = creds.user_id[:2] + "****" + (creds.user_id[-1:] if len(creds.user_id) > 2 else "")
        print("[SUCCESS] Credentials loaded successfully.")
        print(f"  User ID : {masked_user}")
        print("  Password: [CONFIGURED - HIDDEN]")
        print("Ready for Bhoonidhi API authentication.")
    except Exception as e:
        print(f"[STATUS] {e}")
        print("\nTo configure credentials, add your Bhoonidhi account details to '.env':")
        print("  BHOONIDHI_USER_ID=your_username")
        print("  BHOONIDHI_PASSWORD=your_password")
        sys.exit(1)


if __name__ == "__main__":
    main()

