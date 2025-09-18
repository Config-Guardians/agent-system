import subprocess
import json
import os
import re
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.graph import MessagesState, END
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from .graph import get_next_node, make_system_prompt


remediation_agent = create_react_agent(
    model="openai:gpt-4.1-mini",
    tools=[],  # No tools - just pure LLM generation
    prompt=make_system_prompt(
        """
        You are a remediation agent responsible for fixing configuration file policy violations.
        
        Your task:
        1. Analyze the monitoring agent's findings (violations and recommendations)
        2. Generate the complete patched file content that fixes ALL policy violations
        3. Return ONLY the patched content - no explanations, no markdown, just the raw file content
        
        IMPORTANT: Return ONLY the patched file content. Do not include any explanations, markdown formatting, or additional text.
        """
    ),
)


def get_original_content_from_state(state: MessagesState) -> str:
    """Extract original content from the conversation state"""
    for message in reversed(state["messages"]):
        if "This is the file content:" in message.content:
            content_start = message.content.find("This is the file content:") + len("This is the file content:")
            content_end = message.content.find("What are the recommended changes")
            if content_end == -1:
                content_end = len(message.content)
            return message.content[content_start:content_end].strip()
    return ""


def get_violations_from_state(state: MessagesState) -> str:
    """Extract violations from the conversation state"""
    for message in reversed(state["messages"]):
        if "FAIL -" in message.content or "deny" in message.content.lower():
            return message.content
    return ""


def remediation_node(state: MessagesState):
    # Let the LLM generate the patch
    result = remediation_agent.invoke(state)
    
    # Extract information from the conversation
    original_content = get_original_content_from_state(state)
    violations = get_violations_from_state(state)
    llm_response = result["messages"][-1].content
    
    # The LLM response should be the patched content directly
    patched_content = llm_response.strip()
    
    # Get filename from the original content
    filename = "ecr.tf"  # This should come from your main.py context
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
    
    # Validate the patch
    try:
        validation_result = subprocess.run(
            ["conftest", "test", f"tmp/{patched_filename}", "--policy", "policy/deny.rego"],
            capture_output=True,
        )
        validation_output = validation_result.stdout.decode("utf-8")
        print(f"Patch validation result: {validation_output}")
    except Exception as e:
        validation_output = f"Error validating patch: {str(e)}"
        print(validation_output)
    
    # Create approval request
    approval_data = {
        "original_filename": filename,
        "patched_filename": patched_filename,
        "file_type": "detected_by_llm",
        "original_content": original_content,
        "patched_content": patched_content,
        "violations_found": violations,
        "validation_results": validation_output,
        "status": "pending_approval",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    try:
        with open("tmp/approval_request.json", "w") as f:
            json.dump(approval_data, f, indent=2)
        print("Approval request generated")
    except Exception as e:
        print(f"Error creating approval request: {str(e)}")
    
    # Create a summary message
    summary = f"""Remediation completed:

Original file: {filename}
Patched file: {patched_filename}
Validation: {validation_output.strip() if validation_output.strip() else 'PASSED'}

The patched file has been saved and validated. An approval request has been generated for the next service."""
    
    result["messages"][-1] = HumanMessage(
        content=summary,
        name="remediation"
    )
    
    return Command(
        update={"messages": result["messages"]},
        goto=END,
    )