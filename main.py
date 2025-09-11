import subprocess
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from dotenv import load_dotenv


@tool
def run_conftest(config_path: str, policy_path: str) -> str:
    """Runs a conftest on a config file against a opa policy file"""
    result = subprocess.run(["conftest", "test", config_path, "--policy", policy_path], capture_output=True)
    output = result.stdout.decode("utf-8")
    print(output)
    # output += result.stderr.decode("utf-8"), not needed since tool throwing error is handled by langchain

    return output


def main():
    load_dotenv()
    agent = create_react_agent(
        model="openai:gpt-4.1-mini",
        tools=[run_conftest],
        prompt="""
            You are a helpful assistant that generates a recommended fix for a configuration with security vulnerabilities.
            You are provided with the configuration file and the opa policy file directory that corresponds to this type of configuration.
            You will use the run_conftest tool to determine what issues are present by passing in the configuration file path and the policy file path.
        """,
    )

    input_message = {
        "role": "user",
        "content": """
            This is the file content, which is located in sample-terraform/ecr.tf:

            provider "aws" {
              region = "ap-southeast-1"
            }
            resource "aws_ecr_repository" "scrooge_ecr" {
              name                 = "scrooge-ecr"

              image_scanning_configuration {
                scan_on_push = true
              }
            }

            What is the recommended changes for this file against the policy in policy/deny.rego?
        """,
    }
    for step in agent.stream(
        {"messages": [input_message]}, stream_mode="values"
    ):
        step["messages"][-1].pretty_print()


main()
