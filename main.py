import subprocess
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from dotenv import load_dotenv


@tool
def run_conftest(path: str) -> str:
    """Runs a conftest against a file with the given path"""
    result = subprocess.run(["conftest", "test", path], capture_output=True)
    output = result.stdout.decode("utf-8")
    # output += result.stderr.decode("utf-8"), not needed since tool throwing error is handled by langchain

    return output


def main():
    load_dotenv()
    agent = create_react_agent(
        model="openai:gpt-4.1-mini", tools=[run_conftest]
    )

    input_message = {
        "role": "user",
        "content": "what is the conftest output for the file in sample-terraform/ecr.tf?",
    }
    for step in agent.stream(
        {"messages": [input_message]}, stream_mode="values"
    ):
        step["messages"][-1].pretty_print()


main()
