import json
import os
from dotenv import load_dotenv
from langgraph.graph import START, MessagesState, StateGraph, END
from sseclient import SSEClient

load_dotenv()
from agents.monitoring import monitoring_node
from agents.remediation import remediation_node


def main():

    workflow = StateGraph(MessagesState)
    workflow.add_node("monitoring", monitoring_node)
    workflow.add_node("remediation", remediation_node)

    workflow.add_edge(START, "monitoring")
    graph = workflow.compile()

    messages = SSEClient("http://localhost:4000/sse")

    for msg in messages:
        if msg.data != "":
            # print("Data: ", msg.data)
            data = json.loads(msg.data)

            if not os.path.isdir("tmp"):
                os.mkdir("tmp")
            with open(f"tmp/{data['filename']}", "w") as f: # TODO: security vulnerability
                f.write(data['content'])

            prompt = "This is the file content:\n"
            prompt += data["content"]
            prompt += f"What are the recommended changes for this file \"{data['filename']}\" against the policy in policy/deny-s3.rego?"

            # print(prompt)

            input_message = {
                "role": "user",
                "content": prompt,
            }

            events = graph.stream(
                {
                    "messages": [input_message],
                },
                {"recursion_limit": 20},
                stream_mode='values'
            )
            for s in events:
                print(s["messages"][-1].pretty_print())
                print("----")

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
