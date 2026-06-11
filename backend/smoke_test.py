"""Quick smoke test for the TelecomAI router. Run: python backend/smoke_test.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from telecom_ai import TelecomAI

QUERIES = [
    "Does the S24 support n79?",            # 1. device band capability
    "Compare Pixel 9 vs iPhone 16",         # 1. device comparison
    "Does the iPhone 17 support carrier aggregation?",  # 1. device combo summary
    "Does the S23 support n77+n78 CA?",     # 1. device combo -> supported
    "Can the Pixel 8 do n77+n261 NR-DC?",   # 1. device combo -> NOT supported
    "Is carrier aggregation n41-n71 supported?",        # 2. network CA combo
    "Can I run endc with b66+n77?",         # 2. EN-DC combo (+ separator)
    "Is b66-n77-n261 a valid EN-DC combo?", # 5. fallback -> combo (no keyword hit)
    "What is EN-DC?",                       # 5. fallback -> glossary
    "What is NR-DC?",                       # 5. fallback -> glossary
    "ARFCN 620000 n78",                     # 3. ARFCN -> frequency (band raster)
    "GSCN 7880",                            # 3. GSCN -> SSB frequency
    "max capacity 100 MHz 4 layers 256QAM", # 3. throughput via 'capacity'
    "Is n77 FCC licensed?",                 # 4. FCC licensed
    "Is n48 licensed by the FCC?",          # 4. FCC unlicensed/shared
    "Is n261 FCC licensed?",                # 4. FCC mmWave category
    "What FCC US bands exist for NR?",      # 4. regulatory overview
    "What is band n78?",                    # 5. fallback -> band lookup
    "What is DSS?",                         # 5. fallback -> glossary
    "tell me about quantum entanglement",   # 5. fallback -> help message
]


def main() -> None:
    ai = TelecomAI(str(Path(__file__).resolve().parent / "data"))
    for q in QUERIES:
        print(f"Q: {q}")
        print(f"A: {ai.run(q)}")
        print()


if __name__ == "__main__":
    main()
