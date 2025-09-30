import subprocess
import json
import os
import re
from datetime import datetime
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.graph import MessagesState, END
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from .graph import get_next_node, make_system_prompt


@tool
def read_policy_file(policy_path: str) -> str:
    """Reads a policy file and returns its content"""
    try:
        with open(policy_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading policy file: {str(e)}"


remediation_agent = create_react_agent(
    model="openai:gpt-4.1-mini",
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


def get_filename_from_state(state: MessagesState) -> str:
    """Extract filename from the conversation state"""
    for message in reversed(state["messages"]):
        if "What are the recommended changes for this file" in message.content:
            # Extract filename from the prompt
            import re
            match = re.search(r'for this file "([^"]+)"', message.content)
            if match:
                return match.group(1)
    raise ValueError("Could not extract filename from conversation state. Make sure the prompt includes the filename.")


def parse_validation_output(validation_output: str) -> dict:
    """Parse conftest validation output to extract test statistics"""
    lines = validation_output.strip().split('\n')
    test_summary = None
    
    for line in lines:
        if "tests," in line and "passed" in line:
            clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
            # Extract numbers from clean line like "4 tests, 3 passed, 0 warnings, 1 failure, 0 exceptions"
            numbers = re.findall(r'\d+', clean_line)
            
            if len(numbers) >= 5:
                test_summary = {
                    "total_tests": int(numbers[0]),
                    "passed": int(numbers[1]),
                    "warnings": int(numbers[2]),
                    "failures": int(numbers[3]),
                    "exceptions": int(numbers[4])
                }
            break
    
    return test_summary or {"total_tests": 0, "passed": 0, "warnings": 0, "failures": 0, "exceptions": 0}


def analyze_changes(original_content: str, patched_content: str) -> dict:
    """Analyze changes between original and patched content"""
    changes_detail = []
    
    original_lines = [line.strip() for line in original_content.split('\n') if line.strip()]
    patched_lines = [line.strip() for line in patched_content.split('\n') if line.strip()]
    
    # Find lines that are in patched but not in original (ADDED)
    for line in patched_lines:
        if line not in original_lines:
            changes_detail.append({
                "type": "ADDED",
                "content": line,
                "description": f"Added: {line}"
            })
    
    # Find lines that are in original but not in patched (REMOVED)
    for line in original_lines:
        if line not in patched_lines:
            changes_detail.append({
                "type": "REMOVED",
                "content": line,
                "description": f"Removed: {line}"
            })
    
    return {
        "total_changes": len(changes_detail),
        "changes_detail": changes_detail
    }


def remediation_node(state: MessagesState):
    remediation_start = datetime.now()
    
    # Extract information from the conversation
    original_content = get_original_content_from_state(state)
    violations = get_violations_from_state(state)
    filename = get_filename_from_state(state)
    
    # Validate the original file to get actual violations count
    # try:
    #     original_validation = subprocess.run(
    #         ["conftest", "test", f"tmp/{filename}", "--policy", "policy/deny-s3.rego"],
    #         capture_output=True,
    #     )
    #     original_validation_output = original_validation.stdout.decode("utf-8")
    #     violations_detected = original_validation_output.count("FAIL") if "FAIL" in original_validation_output else 0
    #     print(f"Original file validation result: {original_validation_output}")
    #
    #     # Count violations in original file
    #     violations_detected = original_validation_output.count("FAIL") if "FAIL" in original_validation_output else 0
    #     original_test_summary = parse_validation_output(original_validation_output)
    # except Exception as e:
    #     original_validation_output = f"Error validating original file: {str(e)}"
    #     violations_detected = 0
    #     original_test_summary = {"total_tests": 0, "passed": 0, "warnings": 0, "failures": 0, "exceptions": 0}
    #     print(original_validation_output)
    
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
    
    # Validate the patch
    # try:
    #     validation_result = subprocess.run(
    #         ["conftest", "test", f"tmp/{patched_filename}", "--policy", "policy/deny-s3.rego"],
    #         capture_output=True,
    #     )
    #     validation_output = validation_result.stdout.decode("utf-8")
    #     print(f"Patch validation result: {validation_output}")
    #     patched_test_summary = parse_validation_output(validation_output)
    # except Exception as e:
    #     validation_output = f"Error validating patch: {str(e)}"
    #     patched_test_summary = {"total_tests": 0, "passed": 0, "warnings": 0, "failures": 0, "exceptions": 0}
    #     print(validation_output)
    
    # Analyze changes between original and patched content
    changes_summary = analyze_changes(original_content, patched_content)
    
    # Track timing
    remediation_end = datetime.now()
    total_duration = (remediation_end - remediation_start).total_seconds()
    
    # Create approval request
    approval_data = {
        "original_filename": filename,
        "patched_content": patched_content,
        "policy_compliance": {
            # "violations_detected": violations_detected,
            # "validation_status": "FAILED" if violations_detected > 0 else "PASSED",
            "policy_file_used": "policy/deny.rego" # TODO: remove hardcode
        },
        "changes_summary": changes_summary,
        "violations_analysis": {
            "raw_violations": violations
        },
        "validation_details": {
            # "original_file_validation": original_validation_output,
            # "patched_file_validation": validation_output,
            # "original_tests_summary": original_test_summary,
            # "patched_tests_summary": patched_test_summary
        },
        "policy_details": {
            "policy_file": "policy/deny.rego", # TODO: remove hardcode
            "specific_rule": "ECR repository must have image tag mutability set", # TODO: remove hardcode
            "required_value": "IMMUTABLE"
        },
        "timing": {
            "remediation_start_time": remediation_start.isoformat() + "Z",
            "remediation_end_time": remediation_end.isoformat() + "Z",
            "total_duration_seconds": round(total_duration, 2)
        }
    }
    
    try:
        with open("tmp/approval_request.json", "w") as f:
            json.dump(approval_data, f, indent=2)
        print("Approval request generated")
    except Exception as e:
        print(f"Error creating approval request: {str(e)}")
    
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
