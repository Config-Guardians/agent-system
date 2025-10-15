import os
import re
import requests

from datetime import datetime
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import MessagesState

def analyze_changes(original_filename: str, patched_filename: str) -> dict:
    """Analyze changes between original and patched content"""

    with open(f"tmp/{original_filename}", "r") as f:
         original_content = f.read()
    with open(f"tmp/{patched_filename}", "r") as f:
         patched_content = f.read()

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

def generate_report(remediation_start: datetime, messages: list[MessagesState], remote_filename: str):

    ai_messages = []
    tool_messages = []

    for message in messages:
        if isinstance(message, AIMessage):
            ai_messages.append(message)
        elif isinstance(message, ToolMessage):
            tool_messages.append(message)

    first_tool_call = ai_messages[0].tool_calls[0]
    filename = first_tool_call["args"]["filename"]
    policy_path = first_tool_call["args"]["policy_path"]

    base_name = os.path.splitext(filename)[0]
    extension = os.path.splitext(filename)[1]
    patched_filename = f"{base_name}_patched{extension}"


    patched_content = None
    with open(f"tmp/{patched_filename}", "r") as f:
         patched_content = f.read()

    # Analyze changes between original and patched content
    changes_summary = analyze_changes(filename, patched_filename)

    # Find first and last tool call message
    original_validation_output = str(tool_messages[0].content)
    validation_output = str(tool_messages[-1].content)

    original_test_summary = parse_validation_output(original_validation_output)
    patched_test_summary = parse_validation_output(validation_output)

    violations_detected = original_validation_output.count("FAIL") if "FAIL" in original_validation_output else 0
    violated_policies = [line.split("-")[-1] for line in original_validation_output.split("\n")[:-3]]

    # Track timing
    remediation_end = datetime.now()
    total_duration = (remediation_end - remediation_start).total_seconds()

    # Create approval request
    approval_data = {
        "original_filename": filename,
        "patched_content": patched_content,
        "policy_compliance": {
            "violations_detected": violations_detected,
            "validation_status": "FAILED" if violations_detected > 0 else "PASSED",
            "policy_file_used": policy_path
        },
        "changes_summary": changes_summary,
        "violations_analysis": {
            "raw_violations": original_validation_output.replace(filename, remote_filename)
        },
        "validation_details": {
            "original_file_validation": original_validation_output.replace(filename, remote_filename),
            "patched_file_validation": validation_output,
            "original_tests_summary": original_test_summary,
            "patched_tests_summary": patched_test_summary
        },
        "policy_details": {
            "policy_file": policy_path,
            "specific_rules": violated_policies
        },
        "timing": {
            "remediation_start_time": remediation_start.isoformat() + "Z", #TODO: change to time of commit/change time
            "remediation_end_time": remediation_end.isoformat() + "Z",
            "total_duration_seconds": round(total_duration, 2)
        }
    }

    hachiware_endpoint = os.getenv("HACHIWARE_ENDPOINT")
    if not hachiware_endpoint:
        raise ValueError("Missing HACHIWARE_ENDPOINT env var")

    res = requests.post(f'{hachiware_endpoint}/api/report', 
        json={ "data": { "attributes": approval_data }}, 
        headers={"Content-Type": "application/vnd.api+json"}
    )
    if res.status_code >= 400:
        print(res.json())

    # try:
    #     with open("tmp/approval_request.json", "w") as f:
    #         json.dump(approval_data, f, indent=2)
    #     print("Approval request generated")
    # except Exception as e:
    #     print(f"Error creating approval request: {str(e)}")
