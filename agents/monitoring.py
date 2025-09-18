import subprocess

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.graph import MessagesState
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from .graph import get_next_node, make_system_prompt


@tool
def run_conftest(filename: str, policy_path: str) -> str:
    """Runs a conftest on a configuration with a filename against a opa policy file"""
    result = subprocess.run(
        ["conftest", "test", f"tmp/{filename}", "--policy", policy_path],
        capture_output=True,
    )
    output = result.stdout.decode("utf-8")
    print(output)
    # output += result.stderr.decode("utf-8"), not needed since tool throwing error is handled by langchain
    return output


monitoring_agent = create_react_agent(
    model="openai:gpt-4.1-mini",
    tools=[run_conftest],
    prompt=make_system_prompt(
        """
        You are a monitoring agent that validates configuration files against policies.
        
        Your task:
        1. Use the run_conftest tool to validate the file against policies
        2. Analyze the conftest results AND the policy file to understand ALL requirements
        3. Provide complete requirements based on what the policy actually enforces
        
        IMPORTANT: 
        - Read the policy file content to understand what it requires
        - Don't just report the first violation - understand ALL policy rules
        - Be specific about required values, not just "set this attribute"
        - The policy file contains the complete requirements - use it as your source of truth
        
        When reporting violations, list ALL requirements that must be met, including specific values.
        """
    ),
)


def monitoring_node(state: MessagesState):
    result = monitoring_agent.invoke(state)
    goto = get_next_node(result["messages"][-1], "remediation")
    result["messages"][-1] = HumanMessage(
        content=result["messages"][-1].content, name="monitoring"
    )
    return Command(
        update={
            # share internal message history of research agent with other agents
            "messages": result["messages"],
        },
        goto=goto,
    )
