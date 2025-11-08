import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import START, MessagesState, StateGraph
from sseclient import SSEClient

# from agents.command import command_node
from utils.reporting import generate_report
from utils.filetype import json2prop, prop2json, with_filetype_conversion

load_dotenv()
from agents.monitoring import monitoring_node
from agents.remediation import remediation_node

from utils.github_pr import create_remediation_pr

workflow = StateGraph(MessagesState)
workflow.add_node("monitoring", monitoring_node)
workflow.add_node("remediation", remediation_node)
# workflow.add_node("command", command_node)

workflow.add_edge(START, "monitoring")
graph = workflow.compile()

graph.get_graph().draw_mermaid_png(output_file_path="graph.png")

def run_agents(prompt: str):
    message = HumanMessage(prompt)
    msg_state = MessagesState(messages=[message])
    events = graph.stream(msg_state,
        {"recursion_limit": 20},
        stream_mode='values'
    )
    final_state = None
    for s in events:
        print(s["messages"][-1].pretty_print())
        print("----")
        final_state = s
    return final_state

# --- Local file testing mode ---
test_file_path = "sample-configs/application.properties"

if not os.path.isdir("tmp"):
    os.mkdir("tmp")

filename = os.path.basename(test_file_path)
extension = os.path.splitext(filename)[1]
base_name = os.path.splitext(filename)[0]
remediation_start = datetime.now()

with open(test_file_path, "r") as f:
    file_content = f.read()

with open(f"tmp/{filename}", "w") as f:
    f.write(file_content)

match extension:
    case ".properties":
        file_content = prop2json(f"tmp/{filename}", f"tmp/{base_name}.json")
        filename = f"{base_name}.json"
    case _:
        pass

# Choose policy file based on extension or file type
policy_path = "policy/deny-application-properties.rego" if extension == ".properties" else "policy/deny.rego"

prompt = "This is the file content:\n"
prompt += file_content
prompt += f"What are the recommended changes for this file \"{filename}\" against the policy in {policy_path}?"

final_state = run_agents(prompt)

monitoring_message = final_state["messages"][-1].content if final_state else ""
if (
    final_state
    and ("FAIL" in monitoring_message or "violation" in monitoring_message.lower() or "recommended change" in monitoring_message.lower())
):
    # Parse patched file back into original filetype in tmp/
    patched_file_path = f"tmp/{base_name}_patched{extension}"
    match extension:
        case ".properties":
            file_content = json2prop(f"tmp/{base_name}_patched.json", patched_file_path)
            final_state["parsed_patched_content"] = file_content
        case _:
            with open(patched_file_path, "w") as pf:
                pf.write(final_state.get("parsed_patched_content", ""))

    # Copy patched file from tmp/ to remediation_patches/ for PR/reporting
    remediation_patch_path = f"remediation_patches/{base_name}_patched{extension}"
    os.makedirs(os.path.dirname(remediation_patch_path), exist_ok=True)
    with open(patched_file_path, "r") as src, open(remediation_patch_path, "w") as dst:
        dst.write(src.read())

    approval_data = generate_report(remediation_start,
                    final_state["messages"],
                    test_file_path,
                    final_state["parsed_patched_content"] if "parsed_patched_content" in final_state else None)

    print("\n--- Remediation Report ---")
    pr_body = (
        "This PR contains automated security/configuration remediations.\n\n"
        "## Remediation Report\n"
        "```json\n"
        f"{json.dumps(approval_data, indent=2)}\n"
        "```"
    )
    create_remediation_pr(remediation_patch_path, pr_body=pr_body)
else:
    print("No violations detected.")
