#!/usr/bin/env python3
"""Test script for the new Z3 MCP tools"""

from processing import solve_equation, extract_relations, natural_language_to_logic

def test_solve_equations():
    print("=" * 70)
    print("Testing solve_equation")
    print("=" * 70)

    # Test 1: Simple equation
    print("\nTest 1: x + 5 == 10")
    result = solve_equation("x + 5 == 10")
    print(f"Result: {result}")
    assert result['status'] == 'satisfiable'
    assert result['solution']['x'] == '5'
    print("[PASSED]")

    # Test 2: System of equations
    print("\nTest 2: x + y == 10, x - y == 2")
    result = solve_equation("x + y == 10, x - y == 2")
    print(f"Result: {result}")
    assert result['status'] == 'satisfiable'
    print("[PASSED]")

    # Test 3: Inequalities
    print("\nTest 3: x > 5, x < 10")
    result = solve_equation("x > 5, x < 10")
    print(f"Result: {result}")
    assert result['status'] == 'satisfiable'
    print("[PASSED]")

    # Test 4: Unsatisfiable
    print("\nTest 4: x > 10, x < 5")
    result = solve_equation("x > 10, x < 5")
    print(f"Result: {result}")
    assert result['status'] == 'unsatisfiable'
    print("[PASSED]")

def test_extract_relations():
    print("\n" + "=" * 70)
    print("Testing extract_relations")
    print("=" * 70)

    # Test 1: Possession
    print("\nTest 1: John has a car")
    result = extract_relations("John has a car")
    print(f"Result: {result}")
    assert len(result) > 0
    assert result[0][1] == 'has'
    print("[PASSED]")

    # Test 2: Identity
    print("\nTest 2: Socrates is a philosopher")
    result = extract_relations("Socrates is a philosopher")
    print(f"Result: {result}")
    assert len(result) > 0
    assert result[0][1] == 'is'
    print("[PASSED]")

    # Test 3: Subset
    print("\nTest 3: All humans are mortal")
    result = extract_relations("All humans are mortal")
    print(f"Result: {result}")
    assert len(result) > 0
    print("[PASSED]")

    # Test 4: Comparison
    print("\nTest 4: The mountain is greater than the hill")
    result = extract_relations("The mountain is greater than the hill")
    print(f"Result: {result}")
    assert len(result) > 0
    # Check that at least one relation is 'greater_than'
    assert any(rel[1] == 'greater_than' for rel in result), f"Expected 'greater_than' relation, got {result}"
    print("[PASSED]")

def test_natural_language_to_logic():
    print("\n" + "=" * 70)
    print("Testing natural_language_to_logic")
    print("=" * 70)

    # Test: Socrates syllogism
    print("\nTest: Socrates syllogism")
    premises = ["All humans are mortal", "Socrates is a human"]
    conclusion = "Socrates is mortal"
    result = natural_language_to_logic(premises, conclusion)
    print(f"Premises ({len(result['premises'])} statements):")
    for p in result['premises'][:5]:  # Show first 5
        print(f"  {p}")
    print(f"  ...")
    print(f"Conclusion: {result['conclusion']}")
    assert 'premises' in result
    assert 'conclusion' in result
    assert len(result['premises']) > 0
    print("[PASSED]")

if __name__ == "__main__":
    try:
        test_solve_equations()
        test_extract_relations()
        test_natural_language_to_logic()

        print("\n" + "=" * 70)
        print("All tests passed!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n[FAILED] Test failed: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
