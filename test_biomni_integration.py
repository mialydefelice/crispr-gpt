"""Unit tests for biomni_integration module."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from typing import Dict, Any

from crisprgpt.biomni_integration import BiomniPlasmidAgent


class TestBiomniPlasmidAgent(unittest.TestCase):
    """Test cases for BiomniPlasmidAgent class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the biomni import to avoid dependency issues
        with patch('crisprgpt.biomni_integration.BIOMNI_AVAILABLE', True):
            with patch('crisprgpt.biomni_integration.A1') as mock_a1:
                self.mock_agent = Mock()
                mock_a1.return_value = self.mock_agent
                self.agent = BiomniPlasmidAgent()
    
    def test_init_with_biomni_available(self):
        """Test initialization when Biomni is available."""
        with patch('crisprgpt.biomni_integration.BIOMNI_AVAILABLE', True):
            with patch('crisprgpt.biomni_integration.A1') as mock_a1:
                mock_agent_instance = Mock()
                mock_a1.return_value = mock_agent_instance
                
                agent = BiomniPlasmidAgent(llm="gpt-4", data_path="./test_data")
                
                self.assertEqual(agent.llm, "gpt-4")
                self.assertEqual(agent.data_path, "./test_data")
                self.assertEqual(agent.agent, mock_agent_instance)
                mock_a1.assert_called_once_with(
                    path="./test_data",
                    llm="gpt-4",
                    expected_data_lake_files=[]
                )
    
    def test_init_with_biomni_unavailable(self):
        """Test initialization when Biomni is not available."""
        with patch('crisprgpt.biomni_integration.BIOMNI_AVAILABLE', False):
            agent = BiomniPlasmidAgent()
            self.assertIsNone(agent.agent)
    
    def test_init_with_exception(self):
        """Test initialization when A1 constructor raises exception."""
        with patch('crisprgpt.biomni_integration.BIOMNI_AVAILABLE', True):
            with patch('crisprgpt.biomni_integration.A1', side_effect=Exception("Init failed")):
                agent = BiomniPlasmidAgent()
                self.assertIsNone(agent.agent)
    
    def test_is_available_true(self):
        """Test is_available when agent is properly initialized."""
        self.assertTrue(self.agent.is_available())
    
    def test_is_available_false(self):
        """Test is_available when agent is None."""
        self.agent.agent = None
        self.assertFalse(self.agent.is_available())
    
    def test_find_mcs_in_plasmid_success(self):
        """Test successful MCS finding."""
        mock_response = {
            "mcs_location": {"start": 100, "end": 150},
            "recognition_sites": ["EcoRI", "BamHI", "HindIII"],
            "confidence": 0.95
        }
        self.mock_agent.go.return_value = mock_response
        
        result = self.agent.find_mcs_in_plasmid("ATCGATCGATCG", "pUC19")
        
        self.assertEqual(result, mock_response)
        self.mock_agent.go.assert_called_once()
    
    def test_find_mcs_in_plasmid_agent_unavailable(self):
        """Test MCS finding when agent is unavailable."""
        self.agent.agent = None
        
        result = self.agent.find_mcs_in_plasmid("ATCGATCGATCG", "pUC19")
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Biomni agent not available")
    
    def test_find_mcs_in_plasmid_exception(self):
        """Test MCS finding when agent raises exception."""
        self.mock_agent.go.side_effect = Exception("Network error")
        
        result = self.agent.find_mcs_in_plasmid("ATCGATCGATCG", "pUC19")
        
        self.assertIn("error", result)
        self.assertIn("Network error", result["error"])
    
    def test_lookup_gene_sequence_success(self):
        """Test successful gene sequence lookup."""
        mock_response = {
            "gene_name": "EGFP",
            "species": "Aequorea victoria",
            "sequence": "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCC",
            "sequence_length": 717,
            "accession": "U55762",
            "error": None
        }
        self.mock_agent.go.return_value = mock_response
        
        result = self.agent.lookup_gene_sequence("eGFP")
        
        self.assertEqual(result, mock_response)
        self.mock_agent.go.assert_called_once()
    
    def test_lookup_gene_sequence_agent_unavailable(self):
        """Test gene lookup when agent is unavailable."""
        self.agent.agent = None
        
        result = self.agent.lookup_gene_sequence("eGFP")
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Biomni agent not available")
        self.assertIsNone(result["sequence"])
    
    def test_lookup_gene_sequence_empty_response(self):
        """Test gene lookup with empty response."""
        self.mock_agent.go.return_value = ""
        
        result = self.agent.lookup_gene_sequence("eGFP")
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Empty response from Biomni")
    
    def test_lookup_gene_sequence_exception(self):
        """Test gene lookup when agent raises exception."""
        self.mock_agent.go.side_effect = Exception("API timeout")
        
        result = self.agent.lookup_gene_sequence("eGFP")
        
        self.assertIn("error", result)
        self.assertIn("API timeout", result["error"])
        self.assertEqual(result["source"], "biomni")
    
    def test_design_construct_success(self):
        """Test successful construct design."""
        mock_response = {
            "strategy": "PCR amplification with restriction sites",
            "primers": {
                "forward": "GAATTCATGGTGAGCAAGGGC",
                "reverse": "AAGCTTTTTGTATAGTTCATCC"
            },
            "restriction_sites": ["EcoRI", "HindIII"],
            "success": True
        }
        self.mock_agent.go.return_value = mock_response
        
        backbone_seq = "ATCGATCGATCG" * 100
        gene_seq = "ATGGTGAGCAAGGGC" * 20
        
        result = self.agent.design_construct(backbone_seq, gene_seq, "EGFP")
        
        self.assertEqual(result, mock_response)
        self.mock_agent.go.assert_called_once()
    
    def test_design_construct_agent_unavailable(self):
        """Test construct design when agent is unavailable."""
        self.agent.agent = None
        
        result = self.agent.design_construct("ATCG", "GCTA", "test_gene")
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Biomni agent not available")
    
    def test_design_construct_exception(self):
        """Test construct design when agent raises exception."""
        self.mock_agent.go.side_effect = Exception("Design failed")
        
        result = self.agent.design_construct("ATCG", "GCTA", "test_gene")
        
        self.assertIn("error", result)
        self.assertIn("Design failed", result["error"])
    
    def test_insert_gene_into_plasmid_success(self):
        """Test successful gene insertion."""
        mock_response = {
            "final_sequence": "ATCGATCG" + "ATGGTGAGC" + "GCTAGCTA",
            "insertion_site": 8,
            "method": "restriction_cloning",
            "success": True
        }
        self.mock_agent.go.return_value = mock_response
        
        result = self.agent.insert_gene_into_plasmid("ATCGATCGGCTAGCTA", "ATGGTGAGC", "EGFP")
        
        self.assertEqual(result, mock_response)
        self.mock_agent.go.assert_called_once()
    
    def test_insert_gene_into_plasmid_agent_unavailable(self):
        """Test gene insertion when agent is unavailable."""
        self.agent.agent = None
        
        result = self.agent.insert_gene_into_plasmid("ATCG", "GCTA", "test_gene")
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Biomni agent not available")
    
    def test_analyze_plasmid_features_success(self):
        """Test successful plasmid feature analysis."""
        mock_response = {
            "features": [
                {"type": "gene", "name": "EGFP", "start": 100, "end": 816},
                {"type": "promoter", "name": "CMV", "start": 50, "end": 99},
                {"type": "origin", "name": "ColE1", "start": 1000, "end": 1500}
            ],
            "annotations": {"total_length": 2000, "gc_content": 0.52}
        }
        self.mock_agent.go.return_value = mock_response
        
        result = self.agent.analyze_plasmid_features("ATCG" * 500, "test_plasmid")
        
        self.assertEqual(result, mock_response)
        self.mock_agent.go.assert_called_once()
    
    def test_analyze_plasmid_features_agent_unavailable(self):
        """Test feature analysis when agent is unavailable."""
        self.agent.agent = None
        
        result = self.agent.analyze_plasmid_features("ATCG", "test_plasmid")
        
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Biomni agent not available")


class TestBiomniIntegrationHelpers(unittest.TestCase):
    """Test helper functions in biomni_integration module."""
    
    def test_module_imports(self):
        """Test that required modules can be imported."""
        try:
            import crisprgpt.biomni_integration
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import biomni_integration: {e}")
    
    def test_logger_creation(self):
        """Test that logger is properly created."""
        from crisprgpt.biomni_integration import logger
        self.assertIsNotNone(logger)
    
    def test_biomni_availability_flag(self):
        """Test that BIOMNI_AVAILABLE flag is properly set."""
        from crisprgpt.biomni_integration import BIOMNI_AVAILABLE
        self.assertIsInstance(BIOMNI_AVAILABLE, bool)


if __name__ == '__main__':
    # Run tests with detailed output
    unittest.main(verbosity=2)