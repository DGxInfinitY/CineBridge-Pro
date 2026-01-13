import sys
import os
sys.path.insert(0, os.path.abspath("src"))
try:
    from cinebridge import CineBridgeApp
    print("SMOKE TEST: Application imported successfully.")
except Exception as e:
    print(f"SMOKE TEST FAILED: {e}")
    sys.exit(1)
