"""
Verification script for the 6 live search scenarios.
"""
import time
from bhoonidhi.client import BhoonidhiClient

client = BhoonidhiClient()

print("--- Case 1: Valid search against confirmed collection ---")
r1 = client.search(collections=["EOS-04_SAR-FRS2_L2A"], limit=2, online_only=False, max_pages=1)
sample_id_1 = r1.features[0]["id"] if r1.features else "None"
print(f"Case 1 Result: {r1.total_returned} features returned (Sample ID: {sample_id_1})")
time.sleep(1.5)

print("--- Case 2: Bounding box search ---")
# India bbox: [75.0, 15.0, 80.0, 20.0]
r2 = client.search(collections=["EOS-04_SAR-FRS2_L2A"], bbox=[75.0, 15.0, 80.0, 20.0], limit=2, online_only=False, max_pages=1)
sample_id_2 = r2.features[0]["id"] if r2.features else "None"
print(f"Case 2 Result: {r2.total_returned} features returned (Sample ID: {sample_id_2})")
time.sleep(1.5)

print("--- Case 3: Date range search ---")
r3 = client.search(collections=["EOS-04_SAR-FRS2_L2A"], datetime_range="2026-10-01T00:00:00Z/2026-10-29T23:59:59Z", limit=2, online_only=False, max_pages=1)
dt_3 = r3.features[0]["properties"].get("datetime") if r3.features else "None"
print(f"Case 3 Result: {r3.total_returned} features returned (Date: {dt_3})")
time.sleep(1.5)

print("--- Case 4: Search with Online-product filter ---")
r4 = client.search(collections=["EOS-04_SAR-FRS2_L2A"], limit=2, online_only=True, max_pages=1)
online_4 = r4.features[0]["properties"].get("Online") if r4.features else "None"
print(f"Case 4 Result: {r4.total_returned} features returned (Online: {online_4})")
time.sleep(1.5)

print("--- Case 5: Valid query returning zero features ---")
r5 = client.search(collections=["EOS-04_SAR-FRS2_L2A"], datetime_range="1990-01-01T00:00:00Z/1990-01-02T00:00:00Z", limit=2, max_pages=1)
print(f"Case 5 Result: {r5.total_returned} features returned, pagination_capped={r5.pagination_capped}")
time.sleep(1.5)

print("--- Case 6: Pagination when rel=next link is provided ---")
r6 = client.search(collections=["EOS-04_SAR-FRS2_L2A"], limit=1, online_only=False, max_pages=2)
print(f"Case 6 Result: {r6.total_returned} features retrieved across {r6.pages_retrieved} pages")

