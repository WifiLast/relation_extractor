# Z3 Backend MCP Functions

This document lists all available MCP tools in the z3_backend.py server.

**Server**: FastMCP HTTP Server running on `http://0.0.0.0:5000`

---

## Z3 Solver Tools

### 1. `solver(equation: str) -> dict`
**Description**: Solve a Z3 equation and return the result.

**Parameters**:
- `equation` (str): The equation to solve

**Returns**: 
```json
{
  "message": "string"
}
```

**Example**:
```
solver("x + 2 = 5")
```

---

### 2. `add_constraint(constraint: str) -> dict`
**Description**: Add a constraint to the Z3 solver context.

**Parameters**:
- `constraint` (str): The constraint expression (e.g., "x > 5")

**Returns**:
```json
{
  "message": "Constraint added",
  "constraint": "string",
  "constraints": ["list of all constraints"]
}
```

**Example**:
```
add_constraint("x > 5")
```

---

### 3. `check_satisfiability() -> dict`
**Description**: Check if the current constraints are satisfiable.

**Parameters**: None

**Returns**:
```json
{
  "message": "Satisfiable|Unsatisfiable|Unknown",
  "model": {"variable": "value"},
  "constraints": ["list of constraints"]
}
```

**Example**:
```
check_satisfiability()
```

---

### 4. `reset_solver() -> dict`
**Description**: Reset the Z3 solver context (clears all constraints and variables).

**Parameters**: None

**Returns**:
```json
{
  "message": "Solver context reset successfully"
}
```

**Example**:
```
reset_solver()
```

---

### 5. `get_status() -> dict`
**Description**: Get the current status of the solver context.

**Parameters**: None

**Returns**:
```json
{
  "status": "active|inactive",
  "constraints_count": 0,
  "variables_count": 0,
  "constraints": ["list of constraints"]
}
```

**Example**:
```
get_status()
```

---

## Theorem Proving Tools

### 6. `prove_theorem_tool(premises: list[str], conclusion: str) -> dict`
**Description**: Prove a theorem given premises and a conclusion using Z3.

**Parameters**:
- `premises` (list[str]): List of premise statements
- `conclusion` (str): The conclusion to prove

**Returns**:
```json
{
  "message": "Theorem proven: ...|Theorem not proven: ...|Error: ..."
}
```

**Example**:
```
prove_theorem_tool(
  ["All humans are mortal", "Socrates is human"],
  "Socrates is mortal"
)
```

---

## Natural Language Processing Tools

### 7. `convert_natural_language(premises: list[str], conclusion: str, use_lemmatization: bool = False) -> dict`
**Description**: Convert natural language premises and conclusion to Z3 logic formulas.

**Parameters**:
- `premises` (list[str]): List of natural language premise statements
- `conclusion` (str): Natural language conclusion statement
- `use_lemmatization` (bool, optional): Enable word lemmatization (default: False)

**Returns**:
```json
{
  "premises": ["z3_formula_1", "z3_formula_2", ...],
  "conclusion": "z3_formula"
}
```

**Example**:
```
convert_natural_language(
  ["All humans are mortal", "Socrates is human"],
  "Socrates is mortal"
)
```

---

### 8. `extract_relations_tool(sentence: str) -> dict`
**Description**: Extract semantic relations from a sentence using spaCy (Linux) or NLTK (fallback).

**Parameters**:
- `sentence` (str): The sentence to analyze

**Returns**:
```json
{
  "method": "spaCy|NLTK",
  "relations": [
    {
      "subject": "string",
      "relation": "string",
      "object": "string"
    }
  ],
  "sentence": "string"
}
```

**Example**:
```
extract_relations_tool("John loves Mary")
```

---

## Relation Storage Tools (DISABLED)

### 9. `save_relations(relations: list[dict]) -> dict`
**Status**: ⚠️ **DISABLED** (MongoDB integration disabled)

**Description**: Save relations to MongoDB (not functional).

**Returns**:
```json
{
  "error": "MongoDB is disabled",
  "message": "Relation storage is not available. MongoDB support has been disabled."
}
```

---

### 10. `find_relations(query: str) -> dict`
**Status**: ⚠️ **DISABLED** (MongoDB integration disabled)

**Description**: Find relations in MongoDB by query (not functional).

**Returns**:
```json
{
  "error": "MongoDB is disabled",
  "message": "Relation queries are not available. MongoDB support has been disabled."
}
```

---

## Usage

To use these MCP tools, make HTTP requests to the server:

```bash
# Example: Call solver tool
curl -X POST http://0.0.0.0:5000/mcp/tools/solver \
  -H "Content-Type: application/json" \
  -d '{"equation": "x + 2 = 5"}'

# Example: Add a constraint
curl -X POST http://0.0.0.0:5000/mcp/tools/add_constraint \
  -H "Content-Type: application/json" \
  -d '{"constraint": "x > 5"}'
```

---

## Implementation Details

- **Framework**: FastMCP (MCP Server)
- **Transport**: HTTP
- **Port**: 5000
- **Host**: 0.0.0.0
- **Z3 Solver**: Used for equation solving and theorem proving
- **NLP**: NLTK for natural language processing
- **Relation Extraction**: spaCy (Linux) or NLTK (fallback)
- **Database**: MongoDB integration disabled

---

## Error Handling

All tools return a dictionary. In case of errors, responses include an `"error"` or `"message"` field with error details.

Example error response:
```json
{
  "message": "Error adding constraint: invalid syntax"
}
```
