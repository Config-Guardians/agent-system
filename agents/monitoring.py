import subprocess
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from pydantic import BaseModel, Field
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
# llm = ChatOllama(model="qwen3:8b")

monitoring_agent = create_react_agent(
    model=llm,
    tools=[run_conftest],
    prompt=make_system_prompt("""
        You will only check if the current or patched configuration passes conftest by using the provided filename.
        You can use the run_conftest tool to determine what issues are present by passing in the configuration filename and the policy file path.
        Do not generate anything; A remediation colleague will handle generation of the recommended fix for the configuration.
        You are only done when conftest passes all tests.
    """
    ),
)


class Route(BaseModel):
    step: Literal["remediation", "command", "end"] = Field(
        "end", description="The next step in the routing process"
    )


def monitoring_node(state: MessagesState):
    result = monitoring_agent.invoke(state)
    router = llm.with_structured_output(Route)
    decision = router.invoke(
        [
            SystemMessage(
                content="Route the input to remediation or command based on the input."
            ),
            HumanMessage(content=result["messages"][-1].content),
        ]
    )
    print(decision)
    goto = get_next_node(result["messages"][-1], decision.step)
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
