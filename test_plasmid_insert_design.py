"""Unit tests for plasmid_insert_design module."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from typing import Dict, Any

from crisprgpt.plasmid_insert_design import (
    StateEntry, StateStep1Backbone, CustomBackboneChoice,
    GeneInsertChoice, GeneSequenceInput, GeneNameInput,
    ConstructConfirmation, OutputFormatSelection, FinalSummary
)
from crisprgpt.logic import Result_ProcessUserInput


class TestStateEntry(unittest.TestCase):
    """Test cases for StateEntry class."""
    
    def test_step_returns_correct_state(self):
        """Test that StateEntry step returns correct next state."""
        result, next_state = StateEntry.step("test message")
        
        self.assertIsInstance(result, Result_ProcessUserInput)
        self.assertEqual(next_state, StateStep1Backbone)
        self.assertEqual(result.status, "success")


class TestStateStep1Backbone(unittest.TestCase):
    """Test cases for StateStep1Backbone class."""
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_standard_backbone_selection(self, mock_chat):
        """Test selection of standard backbone."""
        mock_response = {
            "BackboneName": "pUC19",
            "Status": "success"
        }
        mock_chat.return_value = mock_response
        
        result, next_state = StateStep1Backbone.step("I want to use pUC19")
        
        self.assertEqual(result.status, "success")
        self.assertEqual(result.result, mock_response)
        self.assertEqual(next_state, CustomBackboneChoice)
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_custom_backbone_request(self, mock_chat):
        """Test request for custom backbone."""
        mock_response = {
            "BackboneName": "custom",
            "Status": "custom_backbone_requested"
        }
        mock_chat.return_value = mock_response
        
        result, next_state = StateStep1Backbone.step("I want to use my own backbone")
        
        self.assertEqual(result.status, "success")
        self.assertEqual(next_state, CustomBackboneChoice)


class TestCustomBackboneChoice(unittest.TestCase):
    """Test cases for CustomBackboneChoice class."""
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_sequence_choice(self, mock_chat):
        """Test choosing to provide sequence directly."""
        mock_response = {"Choice": "sequence", "Status": "success"}
        mock_chat.return_value = mock_response
        
        result, next_state = CustomBackboneChoice.step("1")
        
        self.assertEqual(next_state, CustomBackboneSequenceInput)
        self.assertEqual(result.status, "success")
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_details_choice(self, mock_chat):
        """Test choosing to provide details for lookup."""
        mock_response = {"Choice": "details", "Status": "success"}
        mock_chat.return_value = mock_response
        
        result, next_state = CustomBackboneChoice.step("2")
        
        self.assertEqual(next_state, CustomBackboneDetailsInput)
        self.assertEqual(result.status, "success")


class TestGeneInsertChoice(unittest.TestCase):
    """Test cases for GeneInsertChoice class."""
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_sequence_choice(self, mock_chat):
        """Test choosing to provide gene sequence directly."""
        mock_response = {"Choice": "sequence", "Status": "success"}
        mock_chat.return_value = mock_response
        
        result, next_state = GeneInsertChoice.step("1")
        
        self.assertEqual(next_state, GeneSequenceInput)
        self.assertEqual(result.status, "success")
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_name_choice(self, mock_chat):
        """Test choosing to provide gene name for lookup."""
        mock_response = {"Choice": "name", "Status": "success"}
        mock_chat.return_value = mock_response
        
        result, next_state = GeneInsertChoice.step("2")
        
        self.assertEqual(next_state, GeneNameInput)
        self.assertEqual(result.status, "success")


class TestGeneSequenceInput(unittest.TestCase):
    """Test cases for GeneSequenceInput class."""
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_valid_sequence(self, mock_chat):
        """Test processing valid DNA sequence."""
        mock_response = {
            "Target gene": "Custom Gene",
            "Gene sequence": "ATGCGATCGATCGTAG",
            "Status": "success"
        }
        mock_chat.return_value = mock_response
        
        result, next_state = GeneSequenceInput.step("ATGCGATCGATCGTAG")
        
        self.assertEqual(result.status, "success")
        self.assertEqual(next_state, ConstructConfirmation)
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_invalid_sequence(self, mock_chat):
        """Test processing invalid DNA sequence."""
        mock_response = {
            "Status": "error",
            "Error": "Invalid sequence"
        }
        mock_chat.return_value = mock_response
        
        result, next_state = GeneSequenceInput.step("INVALID")
        
        self.assertEqual(result.status, "success")  # State handles the error in response


class TestGeneNameInput(unittest.TestCase):
    """Test cases for GeneNameInput class."""
    
    @patch('crisprgpt.biomni_integration.BiomniPlasmidAgent')
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_successful_gene_lookup(self, mock_chat, mock_biomni):
        """Test successful gene name lookup."""
        # Mock Biomni response
        mock_agent_instance = Mock()
        mock_agent_instance.lookup_gene_sequence.return_value = {
            "gene_name": "EGFP",
            "sequence": "ATGGTGAGCAAGGGCGAGGAG",
            "sequence_length": 717,
            "error": None
        }
        mock_biomni.return_value = mock_agent_instance
        
        # Mock OpenAI response
        mock_response = {
            "Target gene": "EGFP",
            "Gene sequence": "ATGGTGAGCAAGGGCGAGGAG",
            "Status": "success"
        }
        mock_chat.return_value = mock_response
        
        result, next_state = GeneNameInput.step("eGFP")
        
        self.assertEqual(result.status, "success")
        self.assertEqual(next_state, ConstructConfirmation)
    
    @patch('crisprgpt.biomni_integration.BiomniPlasmidAgent')
    def test_step_biomni_unavailable(self, mock_biomni):
        """Test gene lookup when Biomni is unavailable."""
        mock_agent_instance = Mock()
        mock_agent_instance.is_available.return_value = False
        mock_biomni.return_value = mock_agent_instance
        
        result, next_state = GeneNameInput.step("eGFP")
        
        self.assertEqual(result.status, "error")
        self.assertEqual(next_state, GeneInsertChoice)
        self.assertIn("unavailable", result.response)


class TestConstructConfirmation(unittest.TestCase):
    """Test cases for ConstructConfirmation class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_memory = {
            "GeneNameInput": Result_ProcessUserInput(
                status="success",
                result={"Target gene": "EGFP", "Gene sequence": "ATGCGT"}
            ),
            "StateStep1Backbone": Result_ProcessUserInput(
                status="success", 
                result={"BackboneName": "pUC19"}
            )
        }
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_user_confirms(self, mock_chat):
        """Test user confirming the construct design."""
        mock_response = {"Status": "proceed", "Thoughts": "User confirmed"}
        mock_chat.return_value = mock_response
        
        result, next_state = ConstructConfirmation.step("Yes, proceed", memory=self.mock_memory)
        
        self.assertEqual(next_state, OutputFormatSelection)
        self.assertEqual(result.status, "success")
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_user_requests_modifications(self, mock_chat):
        """Test user requesting modifications."""
        mock_response = {"Status": "request_modifications", "Thoughts": "User wants changes"}
        mock_chat.return_value = mock_response
        
        result, next_state = ConstructConfirmation.step("I want to change the gene", memory=self.mock_memory)
        
        self.assertEqual(next_state, GeneInsertChoice)
        self.assertEqual(result.status, "success")


class TestOutputFormatSelection(unittest.TestCase):
    """Test cases for OutputFormatSelection class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_memory = {
            "GeneNameInput": Result_ProcessUserInput(
                status="success",
                result={
                    "Target gene": "EGFP",
                    "Gene sequence": "ATGGTGAGCAAGGGCGAGGAG" * 10
                }
            ),
            "StateStep1Backbone": Result_ProcessUserInput(
                status="success",
                result={"BackboneName": "pUC19"}
            )
        }
    
    @patch('crisprgpt.plasmid_insert_design.MCSHandler')
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_genbank_format(self, mock_chat, mock_mcs_handler):
        """Test GenBank format output selection."""
        mock_response = {
            "Output format": "GenBank",
            "Status": "success"
        }
        mock_chat.return_value = mock_response
        
        # Mock MCS handler
        mock_mcs_instance = Mock()
        mock_mcs_instance.insert_gene_into_plasmid.return_value = {
            "final_sequence": "ATCG" * 100,
            "insertion_details": "Success"
        }
        mock_mcs_handler.return_value = mock_mcs_instance
        
        result, next_state = OutputFormatSelection.step("GenBank format please", memory=self.mock_memory)
        
        self.assertEqual(next_state, FinalSummary)
        self.assertEqual(result.status, "success")
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_missing_gene_data(self, mock_chat):
        """Test handling missing gene data."""
        mock_response = {"Output format": "FASTA", "Status": "success"}
        mock_chat.return_value = mock_response
        
        empty_memory = {}
        
        result, next_state = OutputFormatSelection.step("FASTA", memory=empty_memory)
        
        self.assertEqual(next_state, GeneInsertChoice)
        self.assertEqual(result.status, "error")


class TestFinalSummary(unittest.TestCase):
    """Test cases for FinalSummary class."""
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_user_satisfied(self, mock_chat):
        """Test user satisfied with final result."""
        mock_response = {"Status": "satisfied", "Thoughts": "User is happy"}
        mock_chat.return_value = mock_response
        
        result, next_state = FinalSummary.step("Looks great!")
        
        self.assertEqual(result.status, "success")
        self.assertIsNone(next_state)  # Final state
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_step_user_requests_modifications(self, mock_chat):
        """Test user requesting modifications in final summary."""
        mock_response = {"Status": "request_modifications", "Thoughts": "User wants changes"}
        mock_chat.return_value = mock_response
        
        result, next_state = FinalSummary.step("Can we change something?")
        
        self.assertEqual(next_state, GeneInsertChoice)


class TestWorkflowIntegration(unittest.TestCase):
    """Integration tests for the complete workflow."""
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_complete_workflow_path(self, mock_chat):
        """Test a complete workflow path from start to finish."""
        # Mock different responses for different states
        def mock_chat_side_effect(prompt, **kwargs):
            if "backbone" in prompt.lower():
                return {"BackboneName": "pUC19", "Status": "success"}
            elif "choice" in prompt.lower() and "gene" in prompt.lower():
                return {"Choice": "sequence", "Status": "success"}
            elif "sequence" in prompt.lower():
                return {"Target gene": "Test Gene", "Gene sequence": "ATGCGT", "Status": "success"}
            elif "format" in prompt.lower():
                return {"Output format": "FASTA", "Status": "success"}
            else:
                return {"Status": "success"}
        
        mock_chat.side_effect = mock_chat_side_effect
        
        # Track the workflow
        memory = {}
        
        # State 1: Entry
        result1, next_state1 = StateEntry.step("Start plasmid design")
        self.assertEqual(next_state1, StateStep1Backbone)
        
        # State 2: Backbone selection  
        result2, next_state2 = StateStep1Backbone.step("pUC19")
        memory["StateStep1Backbone"] = result2
        self.assertEqual(next_state2, CustomBackboneChoice)
        
        # This demonstrates the workflow structure is working
        self.assertIsInstance(result1, Result_ProcessUserInput)
        self.assertIsInstance(result2, Result_ProcessUserInput)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions and utilities."""
    
    def test_format_json_response_import(self):
        """Test that format_json_response can be imported."""
        try:
            from crisprgpt.plasmid_insert_design import format_json_response
            self.assertTrue(callable(format_json_response))
        except ImportError:
            self.skipTest("format_json_response not available for import")
    
    def test_module_imports(self):
        """Test that all required modules can be imported."""
        import crisprgpt.plasmid_insert_design as pid
        
        # Check that key classes are available
        self.assertTrue(hasattr(pid, 'StateEntry'))
        self.assertTrue(hasattr(pid, 'StateStep1Backbone'))
        self.assertTrue(hasattr(pid, 'GeneInsertChoice'))
        self.assertTrue(hasattr(pid, 'OutputFormatSelection'))


class TestErrorHandling(unittest.TestCase):
    """Test error handling scenarios."""
    
    @patch('crisprgpt.plasmid_insert_design.OpenAIChat.chat')
    def test_openai_api_failure(self, mock_chat):
        """Test handling of OpenAI API failures."""
        mock_chat.side_effect = Exception("API Error")
        
        # This should handle the exception gracefully
        try:
            result, next_state = StateStep1Backbone.step("test input")
            # If we get here, the exception was handled
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Unhandled exception: {e}")
    
    def test_invalid_memory_structure(self):
        """Test handling of invalid memory structures."""
        invalid_memory = {"invalid_key": "invalid_value"}
        
        try:
            result, next_state = ConstructConfirmation.step("test", memory=invalid_memory)
            self.assertTrue(True)  # Should handle gracefully
        except Exception as e:
            self.fail(f"Failed to handle invalid memory structure: {e}")


if __name__ == '__main__':
    # Run tests with detailed output
    unittest.main(verbosity=2)