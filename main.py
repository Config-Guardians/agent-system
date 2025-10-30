import json
import os
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import START, MessagesState, StateGraph
from sseclient import SSEClient

from agents.command import command_node
from utils.reporting import generate_report
from utils.filetype import with_filetype_conversion

load_dotenv()
from agents.monitoring import monitoring_node
from agents.remediation import remediation_node


workflow = StateGraph(MessagesState)
workflow.add_node("monitoring", monitoring_node)
workflow.add_node("remediation", remediation_node)
workflow.add_node("command", command_node)

workflow.add_edge(START, "monitoring")
graph = workflow.compile()

graph.get_graph().draw_mermaid_png(output_file_path="graph.png")

hachiware_endpoint = os.getenv('HACHIWARE_ENDPOINT')
if not hachiware_endpoint:
    raise ValueError("Missing HACHIWARE_ENDPOINT env var")

@with_filetype_conversion
def run_agents(contents: str, filename: str, policy_path: str):

    prompt = "This is the file content:\n"
    prompt += contents
    prompt += f"What are the recommended changes for this file \"{filename}\" against the policy in {policy_path}?"

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

# messages = SSEClient(f"{hachiware_endpoint}/sse", retry=5000)
#
# print("Agent system started")
# try:
#     for msg in messages:
#         if msg.data:
#             data = json.loads(msg.data)
#             match data['type']:
#                 case "github_files":
#                     file = data["data"]
#                     filename = file['path'].split("/")[-1]
#                     file_content = file['content']
#                     print(file['path'])
#                     if not file['path'] == 'src/main/resources/application.properties':
#                         continue
#
#                     if not os.path.isdir("tmp"):
#                         os.mkdir("tmp")
#                     with open(f"tmp/{filename}", "w") as f: # TODO: security vulnerability
#                         f.write(file_content)
#
#                     remediation_start = datetime.now()
#                     policy_path = "policy/deny-application-properties.rego"
#                     final_state = run_agents(file_content, filename, policy_path)
#
#                     if final_state:
#                         generate_report(remediation_start,
#                                         final_state["messages"],
#                                         file['path'],
#                                         final_state["parsed_patched_content"] if "parsed_patched_content" in final_state else None)
#                 case case if case.startswith("aws"):
#                     pass
#
# except KeyboardInterrupt:
#     print("Interrupt detected, terminating gracefully")
#     messages.resp.close()

with open("tmp/application.properties", "r") as f:
    contents = f.read()
    run_agents(contents, "application.properties", "policy/deny-application-properties.rego")
