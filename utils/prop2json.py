import json
import sys
import os

def convert(src, des):
    file_path = src

    if not os.path.isfile(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)

    props = {}
    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                props[k.strip()] = v.strip()

    des_content = json.dumps(props, indent=2)

    with open(des, "w") as f:
        f.write(des_content)
