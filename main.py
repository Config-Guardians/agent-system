import json
import os
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import START, MessagesState, StateGraph
from sseclient import SSEClient

from agents.reporting import generate_report
from utils import prop2json

load_dotenv()
from agents.monitoring import monitoring_node
from agents.remediation import remediation_node


workflow = StateGraph(MessagesState)
workflow.add_node("monitoring", monitoring_node)
workflow.add_node("remediation", remediation_node)

workflow.add_edge(START, "monitoring")
graph = workflow.compile()

hachiware_endpoint = os.getenv('HACHIWARE_ENDPOINT')
if not hachiware_endpoint:
    raise ValueError("Missing HACHIWARE_ENDPOINT env var")

def run_agents(contents, filename, filepath):
    remediation_start = datetime.now()

    prompt = "This is the file content:\n"
    prompt += contents
    prompt += f"What are the recommended changes for this file \"{filename}\" against the policy in policy/deny-application-properties.rego?"

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

    if final_state:
        generate_report(remediation_start, final_state["messages"], filepath)

messages = SSEClient(f"{hachiware_endpoint}/sse", retry=5000)

print("Agent system started")
try:
    for msg in messages:
        if msg.data:

            data = json.loads(msg.data)
            file = data["data"]
            filename = file['path'].split("/")[-1]
            file_content = file['content']
            print(file['path'])
            if not file['path'] == 'src/main/resources/application.properties':
                continue


            if not os.path.isdir("tmp"):
                os.mkdir("tmp")
            with open(f"tmp/{filename}", "w") as f: # TODO: security vulnerability
                f.write(file_content)

            if filename.split(".")[-1] == "properties":
                filename_prefix = filename[:-(len("properties")+1)]
                prop2json.convert(f"tmp/{filename}", f"tmp/{filename_prefix}.json")
                with open(f"tmp/{filename_prefix}.json", "r") as f:
                    file_content = f.read()

                filename = f"{filename_prefix}.json"

            run_agents(file_content, filename, file['path'])
except KeyboardInterrupt:
    print("Interrupt detected, terminating gracefully")
    messages.resp.close()
#
# with open("tmp/application.json", "r") as f:
#     contents = f.read()
#     run_agents(contents, "application.json", "utils/application.json")
