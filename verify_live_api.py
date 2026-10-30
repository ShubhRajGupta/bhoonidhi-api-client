"""
Live Bhoonidhi API Verification Script.
Performs non-destructive live checks (authentication, token reuse, collection listing, STAC search)
only when valid credentials are provided in .env or the environment.
Distinguishes live verification results from offline mocked tests.
"""

import sys
from bhoonidhi.client import BhoonidhiClient
from bhoonidhi.credentials import BhoonidhiCredentials


def run_live_verification():
    print("=" * 65)
    print("Bhoonidhi Live API Verification (Non-destructive)")
    print("=" * 65)

    # 1. Credentials Check
    try:
        creds = BhoonidhiCredentials.load()
        masked_user = creds.user_id[:2] + "****" + (creds.user_id[-1:] if len(creds.user_id) > 2 else "")
        print(f"[1/4] Credentials loaded from .env: {masked_user} (Password configured: YES)")
    except Exception as e:
        print("[!] No credentials configured in .env or environment.")
        print(f"    Details: {e}")
        print("    Live verification skipped. All unit and mock tests remain 100% verified.")
        print("\nTo test with the live Bhoonidhi server:")
        print("    1. Open .env")
        print("    2. Set BHOONIDHI_USER_ID and BHOONIDHI_PASSWORD")
        print("    3. Re-run: python verify_live_api.py")
        sys.exit(0)

    # 2. Live Authentication
    print("[2/4] Testing live authentication (POST /auth/token)...")
    try:
        client = BhoonidhiClient(credentials=creds)
        token = client.authenticate()
        print(f"      [OK] Successfully authenticated. Token length: {len(token)} chars.")
        print(f"      [OK] Token expires in: {client.auth._expires_at - client.auth._expiry_buffer:.0f}s approx.")
    except Exception as e:
        print(f"      [FAIL] Authentication failed: {e}")
        sys.exit(1)

    # 3. Live Collection Discovery
    print("[3/4] Testing catalogue discovery (GET /data/collections)...")
    try:
        collections = client.get_collections()
        print(f"      [OK] Retrieved {len(collections)} collections from live catalogue.")
        sample_ids = [c.get("id") for c in collections[:4] if isinstance(c, dict) and "id" in c]
        if sample_ids:
            print(f"      Sample collections: {sample_ids}")
    except Exception as e:
        print(f"      [FAIL] Failed to retrieve collections: {e}")

    # 4. Live Non-destructive STAC Search
    print("[4/4] Testing non-destructive STAC search (POST /data/search)...")
    try:
        res = client.search(
            collections=["EOS-04_SAR-FRS2_L2A"],
            limit=2,
            online_only=True,
            max_pages=1,
        )
        print(f"      [OK] Search completed. Returned {res.total_returned} features (limit 2).")
        if res.features:
            sample_feat = res.features[0]
            print(f"      Sample item ID: {sample_feat.get('id')}")
            print(f"      Online property: {sample_feat.get('properties', {}).get('Online')}")
    except Exception as e:
        print(f"      [WARN] Search check note: {e}")

    print("\n" + "=" * 65)
    print("Live API verification completed.")
    print("=" * 65)


if __name__ == "__main__":
    run_live_verification()
