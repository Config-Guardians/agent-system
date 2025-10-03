import pytest
import os
from unittest.mock import patch, mock_open

# mock api key
os.environ["OPENAI_API_KEY"] = "test-key"

from agents.reporting import analyze_changes, parse_validation_output


class TestFileAnalysis:
    """Test file analysis and change detection functions"""
    
    @patch('builtins.open', new_callable=mock_open)
    def test_analyze_changes_added_lines(self, mock_file):
        """Test analyze_changes with added lines"""
        original_content = "line1\nline2"
        patched_content = "line1\nline2\nline3"
        
        mock_file.side_effect = [
            mock_open(read_data=original_content).return_value,
            mock_open(read_data=patched_content).return_value
        ]
        
        result = analyze_changes("original.txt", "patched.txt")
        
        assert result["total_changes"] == 1
        assert len(result["changes_detail"]) == 1
        assert result["changes_detail"][0]["type"] == "ADDED"
        assert result["changes_detail"][0]["content"] == "line3"
    
    @patch('builtins.open', new_callable=mock_open)
    def test_analyze_changes_removed_lines(self, mock_file):
        """Test analyze_changes with removed lines"""
        original_content = "line1\nline2\nline3"
        patched_content = "line1\nline3"
        
        mock_file.side_effect = [
            mock_open(read_data=original_content).return_value,
            mock_open(read_data=patched_content).return_value
        ]
        
        result = analyze_changes("original.txt", "patched.txt")
        
        assert result["total_changes"] == 1
        assert len(result["changes_detail"]) == 1
        assert result["changes_detail"][0]["type"] == "REMOVED"
        assert result["changes_detail"][0]["content"] == "line2"
    
    @patch('builtins.open', new_callable=mock_open)
    def test_analyze_changes_no_changes(self, mock_file):
        """Test analyze_changes when no changes are made"""
        content = "line1\nline2"
        
        mock_file.side_effect = [
            mock_open(read_data=content).return_value,
            mock_open(read_data=content).return_value
        ]
        
        result = analyze_changes("original.txt", "patched.txt")
        
        assert result["total_changes"] == 0
        assert len(result["changes_detail"]) == 0


class TestConftestParsing:
    """Test conftest output parsing functions"""
    
    def test_parse_validation_output_success(self):
        """Test parsing conftest output"""
        output = "4 tests, 3 passed, 0 warnings, 1 failure, 0 exceptions"
        result = parse_validation_output(output)
        
        expected = {
            "total_tests": 4,
            "passed": 3,
            "warnings": 0,
            "failures": 1,
            "exceptions": 0
        }
        assert result == expected
    
    def test_parse_validation_output_with_ansi(self):
        """Test parsing conftest output with ANSI codes"""
        output = "\x1b[32m4 tests, 3 passed, 0 warnings, 1 failure, 0 exceptions\x1b[0m"
        result = parse_validation_output(output)
        
        expected = {
            "total_tests": 4,
            "passed": 3,
            "warnings": 0,
            "failures": 1,
            "exceptions": 0
        }
        assert result == expected
    
    def test_parse_validation_output_no_match(self):
        """Test parsing when no test summary found"""
        output = "Some other output"
        result = parse_validation_output(output)
        
        expected = {
            "total_tests": 0,
            "passed": 0,
            "warnings": 0,
            "failures": 0,
            "exceptions": 0
        }
        assert result == expected
    
    def test_parse_validation_output_different_numbers(self):
        """Test parsing with different test numbers"""
        test_cases = [
            ("10 tests, 8 passed, 2 warnings, 0 failures, 0 exceptions", {
                "total_tests": 10, "passed": 8, "warnings": 2, "failures": 0, "exceptions": 0
            }),
            ("1 tests, 0 passed, 0 warnings, 1 failure, 0 exceptions", {
                "total_tests": 1, "passed": 0, "warnings": 0, "failures": 1, "exceptions": 0
            }),
            ("0 tests, 0 passed, 0 warnings, 0 failures, 0 exceptions", {
                "total_tests": 0, "passed": 0, "warnings": 0, "failures": 0, "exceptions": 0
            })
        ]
        
        for output, expected in test_cases:
            result = parse_validation_output(output)
            assert result == expected


class TestPolicyViolationDetection:
    """Test policy violation detection and status determination"""
    
    def test_violation_detection(self):
        """Test violation detection logic"""
        conftest_output = """FAIL - policy/deny-s3.rego - deny-s3-bucket-public-read
FAIL - policy/deny-s3.rego - deny-s3-bucket-public-write
4 tests, 3 passed, 0 warnings, 1 failure, 0 exceptions"""
        
        violations_detected = conftest_output.count("FAIL")
        lines = conftest_output.split("\n")
        violated_policies = []
        for line in lines:
            if line.startswith("FAIL -"):
                parts = line.split(" - ")
                if len(parts) >= 3:
                    policy_name = parts[-1].strip()
                    violated_policies.append(policy_name)
        
        assert violations_detected == 2
        assert len(violated_policies) == 2
        assert "deny-s3-bucket-public-read" in violated_policies
        assert "deny-s3-bucket-public-write" in violated_policies
    
    def test_validation_status_determination(self):
        """Test validation status determination"""
        test_cases = [
            (0, "PASSED"),
            (1, "FAILED"),
            (5, "FAILED")
        ]
        
        for violations, expected_status in test_cases:
            status = "FAILED" if violations > 0 else "PASSED"
            assert status == expected_status


class TestFileOperations:
    """Test file operation utilities"""
    
    def test_patched_filename_generation(self):
        """Test patched filename generation logic"""
        test_cases = [
            ("ecr.tf", "ecr_patched.tf"),
            ("config.yaml", "config_patched.yaml"),
            ("policy.json", "policy_patched.json"),
            ("infrastructure.tf", "infrastructure_patched.tf")
        ]
        
        for original, expected in test_cases:
            base_name = os.path.splitext(original)[0]
            extension = os.path.splitext(original)[1]
            patched = f"{base_name}_patched{extension}"
            assert patched == expected
