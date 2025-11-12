import re
import yaml

def retrieve_policy(filename: str) -> str:
    with open("policies.yaml") as f:
        rules = yaml.safe_load(f)

    try:
        with open(f"tmp/{filename}", "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""

    for rule in rules:
        # Match filename pattern
        if not re.search(rule["filename_pattern"], filename):
            continue

        # If there's a content pattern, check that too
        content_pattern = rule.get("content_pattern")
        if content_pattern and not re.search(content_pattern, content):
            continue

        return rule["policy"]

    raise Exception(f"No matching policy found for {filename}")
