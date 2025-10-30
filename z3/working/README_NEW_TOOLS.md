# New Z3 MCP Server Tools

This document describes the new tools added to the Z3 MCP server based on `z3_backend.py`.

## Summary

Three new MCP tools have been added to the server:

1. **solve_equations** - Solve algebraic equations and constraint systems
2. **extract_semantic_relations** - Extract semantic relations from natural language
3. **convert_natural_language** - Convert natural language to Z3 logic formulas

## Files Modified

- **[processing.py](processing.py)** - New file containing core processing functions
- **[server.py](server.py)** - Updated with new MCP tool definitions
- **[test_tools.py](test_tools.py)** - Comprehensive test suite for new functionality

## Tool Details

### 1. solve_equations

Solves equations and systems of constraints using Z3.

**Example Usage:**
```python
# Simple equation
solve_equations("x + 5 == 10")
# Returns: {"status": "satisfiable", "solution": {"x": "5"}, "message": "Solution found"}

# System of equations
solve_equations("x + y == 10, x - y == 2")
# Returns: {"status": "satisfiable", "solution": {"x": "6", "y": "4"}, ...}

# With inequalities
solve_equations("x > 0, x < 100, x * 2 == 50")
# Returns: {"status": "satisfiable", "solution": {"x": "25"}, ...}
```

**Parameters:**
- `equation` (str): Comma-separated constraints using Python operators

**Returns:**
- Dictionary with `status`, `solution`, and `message` fields

### 2. extract_semantic_relations

Extracts semantic relations from natural language sentences using NLTK.

**Relation Types Detected:**
- `is` / `is_not` - Identity relations
- `has` - Possession relations
- `subset_of` - Class inclusion ("All X are Y")
- `greater_than` / `less_than` - Comparisons
- Verb-based relations (any verb connecting nouns)

**Example Usage:**
```python
# Identity
extract_semantic_relations("Socrates is a philosopher")
# Returns: {"relations": [{"subject": "socrates", "relation": "is", "object": "philosopher"}], ...}

# Possession
extract_semantic_relations("John has a car")
# Returns: {"relations": [{"subject": "john", "relation": "has", "object": "car"}], ...}

# Subset
extract_semantic_relations("All humans are mortal")
# Returns: {"relations": [{"subject": "humans", "relation": "subset_of", "object": "mortal"}], ...}

# Comparison
extract_semantic_relations("The mountain is greater than the hill")
# Returns: {"relations": [{"subject": "mountain", "relation": "greater_than", "object": "hill"}], ...}
```

**Parameters:**
- `sentence` (str): Natural language sentence to analyze

**Returns:**
- Dictionary with `relations` (list), `count`, and `sentence` fields

### 3. convert_natural_language

Converts natural language premises and conclusions to Z3 logic formulas.

**Example Usage:**
```python
premises = [
    "All humans are mortal",
    "Socrates is a human"
]
conclusion = "Socrates is mortal"

convert_natural_language(premises, conclusion)
# Returns:
# {
#     "premises": [
#         "Object = DeclareSort('Object')",
#         "s = Solver()",
#         "humans = Const('humans', Object)",
#         "mortal = Const('mortal', Object)",
#         "socrates = Const('socrates', Object)",
#         "SubsetOf = Function('SubsetOf', Object, Object, BoolSort())",
#         "Is = Function('Is', Object, Object, BoolSort())",
#         "s.add(SubsetOf(humans, mortal))",
#         "s.add(Is(socrates, humans))"
#     ],
#     "conclusion": "Is(socrates, mortal)"
# }
```

**Parameters:**
- `premises` (List[str]): Natural language premise statements
- `conclusion` (str): Natural language conclusion

**Returns:**
- Dictionary with `premises` (list of Z3 statements) and `conclusion` (Z3 expression)

**Workflow:**
1. Call `convert_natural_language` to get Z3 formulas
2. Pass the result to `prove_logic` tool to verify the conclusion

## Testing

Run the test suite:

```bash
cd working
python test_tools.py
```

All tests should pass with output showing:
- Equation solving tests (4 tests)
- Relation extraction tests (4 tests)
- Natural language conversion tests (1 test)

## Dependencies

- **z3-solver** - Z3 theorem prover
- **nltk** - Natural Language Toolkit (for relation extraction)

Optional NLTK data packages:
- `punkt` - Tokenization
- `averaged_perceptron_tagger` - POS tagging

If NLTK data is not available, relation extraction will return an error message.

## Architecture

The implementation follows a modular design:

1. **processing.py** - Core logic functions (keeps server.py clean)
   - `solve_equation()` - Z3 constraint solving
   - `extract_relations()` - NLTK-based relation extraction
   - `natural_language_to_logic()` - NL to Z3 conversion

2. **server.py** - MCP tool wrappers
   - Thin wrappers that call processing functions
   - Comprehensive documentation for LLM usage
   - Type hints and return value formatting

3. **test_tools.py** - Test suite
   - Unit tests for all major functionality
   - Validates expected behavior
   - Serves as usage examples

## Comparison with z3_backend.py

The new implementation is based on `z3_backend.py` but with improvements:

1. **Modular design** - Separated processing logic from server
2. **Simplified** - Removed Flask/CORS/MongoDB dependencies
3. **MCP native** - Designed specifically for MCP protocol
4. **Better patterns** - Improved relation extraction patterns
5. **Tested** - Comprehensive test suite included

## Future Enhancements

Potential improvements:
- Add spaCy support for more advanced NLP
- Support for more complex logical constructs
- Caching of parsed relations
- Integration with graph databases
- Support for temporal logic
