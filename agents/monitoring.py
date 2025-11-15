import subprocess

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from .base import get_next_node, make_system_prompt


@tool
def run_conftest(filename: str, policy_path: str) -> str:
    """Runs a conftest on a configuration with a filename against a opa policy file"""
    result = subprocess.run(
        ["conftest", "test", f"tmp/{filename}", "--policy", policy_path],
        capture_output=True
    )
    output = result.stdout.decode("utf-8")
    print(output)
    # output += result.stderr.decode("utf-8"), not needed since tool throwing error is handled by langchain
    return output

llm = ChatOpenAI(model="gpt-4.1-mini")
# llm = ChatOllama(model="qwen3:8b", reasoning=False)

monitoring_agent = create_react_agent(
    model=llm,
    tools=[run_conftest],
    prompt=make_system_prompt("""
        You will only check whether the current or patched configuration passes Conftest by using the provided filename.
        You may use the run_conftest tool to identify any issues by supplying the configuration filename and the policy file path.
        Keep your output concise and clear.
        Do not generate any fixes; a remediation colleague is responsible for producing the recommended configuration changes.
        Always use the conftest tool before determining if your task is completed.
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
