import requests
import os

os.makedirs("data", exist_ok=True)

DATASETS = {
    "HDFS": "https://raw.githubusercontent.com/logpai/loghub/master/HDFS/HDFS_2k.log",
    "OpenStack": "https://raw.githubusercontent.com/logpai/loghub/master/OpenStack/OpenStack_2k.log",
    "Spark": "https://raw.githubusercontent.com/logpai/loghub/master/Spark/Spark_2k.log",
    "Linux": "https://raw.githubusercontent.com/logpai/loghub/master/Linux/Linux_2k.log",
}

for name, url in DATASETS.items():
    print(f"Fetching {name}...")
    r = requests.get(url)
    if r.status_code == 200:
        path = f"data/{name}_2k.log"
        with open(path, "w") as f:
            f.write(r.text)
        print(f"  Saved: {path} ({len(r.text)} bytes)")
    else:
        print(f"  Failed: {r.status_code}")

print("\nDone. Run explore_data.py next.")
