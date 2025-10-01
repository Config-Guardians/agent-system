import json
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import START, MessagesState, StateGraph
from sseclient import SSEClient

from agents.reporting import generate_report

load_dotenv()
from agents.monitoring import monitoring_node
from agents.remediation import remediation_node


def main():

    workflow = StateGraph(MessagesState)
    workflow.add_node("monitoring", monitoring_node)
    workflow.add_node("remediation", remediation_node)

    workflow.add_edge(START, "monitoring")
    graph = workflow.compile()

    hachiware_endpoint = os.getenv('HACHIWARE_ENDPOINT')
    if not hachiware_endpoint:
        raise ValueError("Missing HACHIWARE_ENDPOINT env var")

    messages = SSEClient(f"{hachiware_endpoint}/sse")

    try:
        for msg in messages:
            if msg.data:
                data = json.loads(msg.data)
                file = data["data"]
                filename = file['path'].split("/")[-1]
                print(file['path'])
                if not file['path'] == 'infra/modules/storage/main.tf':
                    continue

                if not os.path.isdir("tmp"):
                    os.mkdir("tmp")
                with open(f"tmp/{filename}", "w") as f: # TODO: security vulnerability
                    f.write(file['content'])

                prompt = "This is the file content:\n"
                prompt += file["content"]
                prompt += f"What are the recommended changes for this file \"{filename}\" against the policy in policy/deny-s3.rego?"

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
                    generate_report(final_state["messages"])
    except KeyboardInterrupt:
        print("Interrupt detected, terminating gracefully")
        messages.resp.close()

    # COMMENTED OUT: Sample terraform usage (uncomment when needed)
    # sample_file = "sample-terraform/ecr.tf"
    # filename = os.path.basename(sample_file)
    
    # with open(sample_file, "r") as f:
    #     content = f.read()
    
    # if not os.path.isdir("tmp"):
    #     os.mkdir("tmp")
    # with open(f"tmp/{filename}", "w") as f:
    #     f.write(content)
    
    # prompt = "This is the file content:\n"
    # prompt += content
    # prompt += f"What are the recommended changes for this file \"{filename}\" against the policy in policy/deny.rego?"
    
    # input_message = {
    #     "role": "user",
    #     "content": prompt,
    # }
    
    # print(f"Starting policy compliance workflow for {filename}...")
    # print("=" * 60)
    
    # events = graph.stream(
    #     {
    #         "messages": [input_message],
    #     },
    #     {"recursion_limit": 150},
    #     stream_mode='values'
    # )
    
    # for s in events:
    #     print(s["messages"][-1].pretty_print())
    #     print("----")
    
main()
