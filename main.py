import json
import os
import requests
from typing import Literal

from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import START, MessagesState, StateGraph
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from sseclient import SSEClient
from pydantic import BaseModel, Field

from agents.command import command_node
from utils.reporting import generate_report
from utils.filetype import json2prop, prop2json, with_filetype_conversion
from utils.github_pr import create_remediation_pr

load_dotenv()
from agents.monitoring import monitoring_node
from agents.remediation import remediation_node

class Route(BaseModel):
    step: Literal["monitoring", "command"]

llm = ChatOpenAI(model="gpt-4.1-mini")
# llm = ChatOllama(model="qwen3:8b")

def decision_node(state: MessagesState):
    router = llm.with_structured_output(Route)
    decision = router.invoke(
        [
            SystemMessage(
                content=""" Route the input to monitoring or command based on the input. 
                    If the input is an aws resource, then route to command. 
                    If the input is a configuration file, then route to monitoring."""
            ),
            HumanMessage(content=state["messages"][-1].content),
        ]
    )
    print(f"{decision.step} agent was chosen.")
    return Command(
        update={
            # share internal message history of research agent with other agents
            "messages": decision.step,
        },
        goto=decision.step,
    )


workflow = StateGraph(MessagesState)
workflow.add_node("decision", decision_node)
workflow.add_node("command", command_node)
workflow.add_node("monitoring", monitoring_node)
workflow.add_node("remediation", remediation_node)

workflow.add_edge(START, "decision")
graph = workflow.compile()

graph.get_graph().draw_mermaid_png(output_file_path="graph.png")

hachiware_endpoint = os.getenv('HACHIWARE_ENDPOINT')
if not hachiware_endpoint:
    raise ValueError("Missing HACHIWARE_ENDPOINT env var")

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

messages = SSEClient(f"{hachiware_endpoint}/sse", retry=5000)

print("Agent system started")
try:
    for msg in messages:
        if msg.data:
            data = json.loads(msg.data)
            match data['type']:
                case "github_files":
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

                    remediation_start = datetime.now()
                    policy_path = "policy/deny-application-properties.rego"

                    base_name = os.path.splitext(filename)[0]
                    extension = os.path.splitext(filename)[1]

                    # parsing file into conftest compatible filetype
                    match extension:
                        case ".properties":
                            file_content = prop2json(f"tmp/{filename}", f"tmp/{base_name}.json")
                            filename = f"{base_name}.json"

                    prompt = "This is the file content:\n"
                    prompt += file_content
                    prompt += f"What are the recommended changes for this file \"{filename}\" against the policy in {policy_path}?"

                    final_state = run_agents(prompt)

                    if not final_state:
                        raise Exception("final_state was None.")

                    # parsing file back into original filetype
                    match extension:
                        case ".properties":
                            file_content = json2prop(f"tmp/{base_name}_patched.json", f"tmp/{base_name}_patched{extension}")
                            final_state["parsed_patched_content"] = file_content

                    approval_data = generate_report(remediation_start,
                                    final_state["messages"],
                                    file['path'],
                                    final_state["parsed_patched_content"] if "parsed_patched_content" in final_state else None)

                    # Create GitHub PR with remediation changes
                    remediation_patch_path = f"remediation_patches/{base_name}_patched{extension}"
                    os.makedirs(os.path.dirname(remediation_patch_path), exist_ok=True)
                    with open(f"tmp/{base_name}_patched{extension}", "r") as src, open(remediation_patch_path, "w") as dst:
                        dst.write(src.read())

                    print("\n--- Remediation Report ---")
                    pr_body = (
                        "This PR contains automated security/configuration remediations.\n\n"
                        "## Remediation Report\n"
                        "```json\n"
                        f"{json.dumps(approval_data, indent=2)}\n"
                        "```"
                    )
                    create_remediation_pr(remediation_patch_path, pr_body=pr_body)

                    res = requests.post(f'{hachiware_endpoint}/api/report', 
                        json={ "data": { "attributes": approval_data }}, 
                        headers={"Content-Type": "application/vnd.api+json"}
                    )
                    if res.status_code >= 400:
                        print(res.json())

                case case if case.startswith("aws"):
                    contents = data["data"]

                    prompt = "What are the recommended command fixes for the cloud resource below?\n"
                    prompt += json.dumps(contents, indent=2)

                    run_agents(prompt)

except KeyboardInterrupt:
    print("Interrupt detected, terminating gracefully")
    messages.resp.close()

# with open("tmp/application.properties", "r") as f:
#     contents = f.read()
#     filename = "application.properties"
#     policy_path = "policy/deny-application-properties.rego"
#     prompt = "This is the file content:\n"
#     prompt += contents
#     prompt += f"What are the recommended changes for this file \"{filename}\" against the policy in {policy_path}?"
#
#     run_agents(prompt)
#
# with open("tmp/aws-resource.json", "r") as f:
#     contents = f.read()
#     prompt = "This is the config content:\n"
#     prompt += contents
#     prompt += f"What are the recommended command fixes for this cloud resource?"
#
#     run_agents(prompt)
