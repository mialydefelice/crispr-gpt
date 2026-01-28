"""Test runner and configuration for CRISPR-GPT unit tests."""

import unittest
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_tests():
    """Run all unit tests with proper configuration."""
    # Discover and run tests
    loader = unittest.TestLoader()
    
    # Load tests from both test files
    suite = unittest.TestSuite()
    
    # Add biomni integration tests
    try:
        from test_biomni_integration import TestBiomniPlasmidAgent
        biomni_tests = loader.loadTestsFromName('test_biomni_integration')
        suite.addTests(biomni_tests)
        print("✓ Loaded biomni_integration tests")
    except ImportError as e:
        print(f"⚠ Could not load biomni_integration tests: {e}")
    
    # Add plasmid design tests  
    try:
        from test_plasmid_insert_design import TestStateEntry, TestStateStep1Backbone, TestCustomBackboneChoice, TestGeneInsertChoice, TestGeneSequenceInput, TestGeneNameInput, TestConstructConfirmation
        design_tests = loader.loadTestsFromName('test_plasmid_insert_design')
        suite.addTests(design_tests)
        print("✓ Loaded plasmid_insert_design tests")
    except ImportError as e:
        print(f"⚠ Could not load plasmid_insert_design tests: {e}")
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    print(f"{'='*60}")
    
    # Return success status
    return len(result.failures) == 0 and len(result.errors) == 0

def run_specific_test(test_name):
    """Run a specific test module or test case."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(test_name)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        print(f"Running specific test: {test_name}")
        run_specific_test(test_name)
    else:
        # Run all tests
        print("Running all CRISPR-GPT unit tests...")
        success = run_tests()
        sys.exit(0 if success else 1)