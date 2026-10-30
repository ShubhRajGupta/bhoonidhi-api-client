"""
Bhoonidhi Credentials Loader and Validator CLI.
Execute directly (`python credentials.py`) to verify that credentials can be read
from .env or environment variables without exposing sensitive secrets.
"""

import sys
from bhoonidhi.credentials import BhoonidhiCredentials, parse_env_file

__all__ = ["BhoonidhiCredentials", "parse_env_file"]


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
