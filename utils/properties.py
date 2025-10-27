import json
import sys
import os

def prop2json(src, des):
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


def json2prop(src, des):
    file_path = src

    if not os.path.isfile(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)

    with open(file_path, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON file. {e}")
            sys.exit(1)

    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                lines.append(f"{key}.{sub_key}={sub_value}")
        else:
            lines.append(f"{key}={value}")

    with open(des, "w") as f:
        f.write("\n".join(lines))
