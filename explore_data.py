import os

files = [f for f in os.listdir("data") if f.endswith(".log")]
print(f"Files downloaded: {files}\n")

for fname in files:
    path = f"data/{fname}"
    with open(path) as f:
        lines = f.readlines()
    print(f"--- {fname} ---")
    print(f"Total lines: {len(lines)}")
    print("Sample lines:")
    for line in lines[:3]:
        print(" ", line.strip())

    errors = [
        line for line in lines
        if "ERROR" in line or "WARN" in line or "Exception" in line or "FAILED" in line
    ]
    print(f"Error/warning lines found: {len(errors)}")
    for line in errors[:3]:
        print("  >>", line.strip())
    print()
