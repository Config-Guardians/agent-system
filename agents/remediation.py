import os
import re
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langgraph.graph import MessagesState
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from .base import get_next_node, make_system_prompt


llm = ChatOpenAI(model="gpt-4.1-mini")
# llm = ChatOllama(model="qwen3:8b")

remediation_agent = create_react_agent(
    model=llm,
    tools=[],
    prompt=make_system_prompt(
        """
        You are a remediation agent responsible for fixing configuration file policy violations.
        
        Your task:
        1. Analyze the monitoring agent's findings (violations and recommendations)
        2. Generate the complete patched file content that fixes ALL policy violations
        3. Return ONLY the patched content - no explanations, no markdown, just the raw file content
        """
    ),
)


def get_filename_from_state(state: MessagesState) -> str:
    """Extract filename from the conversation state"""
    for message in reversed(state["messages"]):
        if "What are the recommended changes for this file" in message.content:
            # Extract filename from the prompt
            match = re.search(r'for this file "([^"]+)"', str(message.content))
            if match:
                return match.group(1)
    raise ValueError("Could not extract filename from conversation state. Make sure the prompt includes the filename.")


def remediation_node(state: MessagesState):
    # Extract information from the conversation
    filename = get_filename_from_state(state)

    # Let the LLM generate the patch
    result = remediation_agent.invoke(state)
    llm_response = result["messages"][-1].content
    
    # The LLM response should be the patched content directly
    patched_content = llm_response.strip()
    
    # Get filename from the conversation state
    base_name = os.path.splitext(filename)[0]
    extension = os.path.splitext(filename)[1]
    patched_filename = f"{base_name}_patched{extension}"
    
    # Save the patched file
    try:
        with open(f"tmp/{patched_filename}", "w") as f:
            f.write(patched_content)
        print(f"Patched file saved as tmp/{patched_filename}")
    except Exception as e:
        print(f"Error saving patched file: {str(e)}")

    # Create a summary message
    summary = f""" Remediation completed:

Original file: {filename}
Patched file: {patched_filename}
"""

    goto = get_next_node(result["messages"][-1], "monitoring")
    result["messages"][-1] = HumanMessage(
        content=summary,
        name="remediation"
    )

    return Command(
        update={"messages": result["messages"]},
        goto=goto,
    )
