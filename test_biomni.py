#!/usr/bin/env python3
"""Test script to verify Biomni installation and functionality."""

import sys

print("=" * 60)
print("BIOMNI CONNECTIVITY TEST")
print("=" * 60)

# Test 1: Check if biomni package is installed
print("\n[1] Checking if biomni package is installed...")
try:
    import biomni
    print("✓ biomni package found")
    print(f"  Location: {biomni.__file__}")
except ImportError as e:
    print(f"✗ biomni package NOT installed")
    print(f"  Error: {e}")
    print("\n  To install, run: pip install biomni")
    sys.exit(1)

# Test 2: Check if A1 agent can be imported
print("\n[2] Checking if biomni.agent.A1 can be imported...")
try:
    from biomni.agent import A1
    print("✓ biomni.agent.A1 imported successfully")
except ImportError as e:
    print(f"✗ Failed to import biomni.agent.A1")
    print(f"  Error: {e}")
    sys.exit(1)

# Test 3: Try to initialize A1 agent (this may require API keys)
print("\n[3] Attempting to initialize Biomni A1 agent...")
try:
    agent = A1(
        path="./biomni_test_data",
        llm="gpt-4o",
        expected_data_lake_files=[]
    )
    print("✓ Biomni A1 agent initialized successfully")
    print(f"  Agent type: {type(agent)}")
except Exception as e:
    print(f"✗ Failed to initialize Biomni A1 agent")
    print(f"  Error type: {type(e).__name__}")
    print(f"  Error: {e}")
    print("\n  Note: This may fail due to missing API keys or configuration")
    print("  But at least the package is installed.")

# Test 4: Check integration in crispr-gpt
print("\n[4] Testing crispr-gpt biomni_integration module...")
try:
    from crisprgpt.biomni_integration import get_biomni_agent, BIOMNI_AVAILABLE
    print(f"✓ biomni_integration module imported successfully")
    print(f"  BIOMNI_AVAILABLE: {BIOMNI_AVAILABLE}")
    
    agent = get_biomni_agent()
    if agent:
        print(f"✓ get_biomni_agent() returned an agent instance")
    else:
        print(f"✗ get_biomni_agent() returned None")
except Exception as e:
    print(f"✗ Failed to test biomni_integration")
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
