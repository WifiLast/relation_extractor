# server.py
from mcp.server.fastmcp import FastMCP
from z3 import *
import traceback
from typing import List, Dict
import uvicorn

# Import processing functions
from processing import solve_equation, extract_relations, natural_language_to_logic

# Create an MCP server for Z3 Logic Solving
mcp = FastMCP("Z3 Logic Solver")


@mcp.tool()
def prove_logic(premises: List[str], conclusion: str) -> bool:
    """
    Prove whether a conclusion logically follows from given premises using Z3 solver.

    Returns True if the conclusion is proven, False otherwise.

    SYNTAX INSTRUCTIONS FOR THE LLM:
    ================================

    This tool uses Z3 theorem prover to verify logical conclusions. You MUST follow this syntax exactly.

    IMPORTANT RULES:
    ----------------
    1. Predicates (properties like "Human", "Mortal") are FUNCTIONS that return BoolSort()
    2. Entities (individuals like "socrates", "x") are CONSTANTS of type Object
    3. Predicates are applied TO entities: Human(socrates) means "socrates is human"
    4. NEVER declare the same name as both a Function and a Const
    5. Use capitalized names for predicates (Human, Mortal, Bird)
    6. Use lowercase names for entities (socrates, bird1, x)
    7. Always declare 'Object' sort first
    8. Always declare variable 'x' for universal/existential quantification
    9. Each premise is a separate string in the premises list

    STANDARD DECLARATIONS (always include these first):
    ---------------------------------------------------
    "Object = DeclareSort('Object')"
    "s = Solver()"

    DECLARING PREDICATES (properties/classes):
    ------------------------------------------
    "Human = Function('Human', Object, BoolSort())"
    "Mortal = Function('Mortal', Object, BoolSort())"
    "Bird = Function('Bird', Object, BoolSort())"
    "CanFly = Function('CanFly', Object, BoolSort())"

    DECLARING ENTITIES (individuals):
    ---------------------------------
    "socrates = Const('socrates', Object)"
    "tweety = Const('tweety', Object)"
    "x = Const('x', Object)"  # for variables in quantifiers

    DECLARING BINARY RELATIONS:
    ---------------------------
    "ParentOf = Function('ParentOf', Object, Object, BoolSort())"
    "GreaterThan = Function('GreaterThan', Object, Object, BoolSort())"

    ADDING CONSTRAINTS:
    ------------------
    Universal statements: "All X are Y"
    "s.add(ForAll([x], Implies(Human(x), Mortal(x))))"

    Existential statements: "Some X are Y"
    "s.add(Exists([x], And(Bird(x), CanFly(x))))"

    Specific facts: "Socrates is human"
    "s.add(Human(socrates))"

    Binary relations: "Alice is parent of Bob"
    "s.add(ParentOf(alice, bob))"

    Negations: "X is not Y"
    "s.add(Not(CanFly(penguin)))"

    CONCLUSION FORMAT:
    -----------------
    The conclusion should be a Z3 expression (NOT a premise with s.add):
    "Mortal(socrates)"
    "CanFly(tweety)"
    "ParentOf(alice, charlie)"

    COMPLETE EXAMPLE - Socrates is Mortal:
    --------------------------------------
    premises = [
        "Object = DeclareSort('Object')",
        "s = Solver()",
        "Human = Function('Human', Object, BoolSort())",
        "Mortal = Function('Mortal', Object, BoolSort())",
        "socrates = Const('socrates', Object)",
        "x = Const('x', Object)",
        "s.add(ForAll([x], Implies(Human(x), Mortal(x))))",
        "s.add(Human(socrates))"
    ]
    conclusion = "Mortal(socrates)"

    EXAMPLE - Transitivity:
    -----------------------
    premises = [
        "Object = DeclareSort('Object')",
        "s = Solver()",
        "GreaterThan = Function('GreaterThan', Object, Object, BoolSort())",
        "a = Const('a', Object)",
        "b = Const('b', Object)",
        "c = Const('c', Object)",
        "x = Const('x', Object)",
        "y = Const('y', Object)",
        "z = Const('z', Object)",
        "s.add(GreaterThan(a, b))",
        "s.add(GreaterThan(b, c))",
        "s.add(ForAll([x, y, z], Implies(And(GreaterThan(x, y), GreaterThan(y, z)), GreaterThan(x, z))))"
    ]
    conclusion = "GreaterThan(a, c)"

    EXAMPLE - Bird that doesn't fly:
    ---------------------------------
    premises = [
        "Object = DeclareSort('Object')",
        "s = Solver()",
        "Bird = Function('Bird', Object, BoolSort())",
        "CanFly = Function('CanFly', Object, BoolSort())",
        "penguin = Const('penguin', Object)",
        "x = Const('x', Object)",
        "s.add(ForAll([x], Implies(Bird(x), CanFly(x))))",
        "s.add(Bird(penguin))",
        "s.add(Not(CanFly(penguin)))"
    ]
    conclusion = "False"  # This will return False (contradiction found)

    USAGE GUIDELINES FOR LLM:
    -------------------------
    1. When formulating a solution, first express it as logical premises
    2. Call this tool to verify if your conclusion follows from the premises
    3. If the tool returns False, your logic is incorrect - abort and try another approach
    4. If the tool returns True, your logic is sound - proceed with confidence
    5. Use this for: planning verification, constraint checking, logical reasoning validation

    Args:
        premises: List of Z3 Python statements defining the logical context
        conclusion: Z3 expression to be proven

    Returns:
        True if conclusion is proven, False otherwise
    """
    try:
        # Create a fresh context for this theorem
        context = {
            'solver': None,
            'variables': {},
            'functions': {},
            'sorts': {},
            'constants': {}
        }

        # Create a local scope for variables and initialize the solver
        locals_dict = {}

        # Execute all premises to build the logical context
        for premise in premises:
            try:
                exec(premise, globals(), locals_dict)

                # Store the solver reference if it's created
                if 's' in locals_dict and locals_dict['s'] is not None:
                    context['solver'] = locals_dict['s']

            except Exception as e:
                print(f"[Z3 MCP] Error executing premise '{premise}': {e}")
                traceback.print_exc()
                return False

        # Ensure we have a solver
        if context['solver'] is None:
            print("[Z3 MCP] Error: No solver created. Make sure premises include 's = Solver()'")
            return False

        # Test the conclusion through refutation (proof by contradiction)
        # If premises AND NOT(conclusion) is unsatisfiable, then conclusion is proven
        try:
            negated_conclusion = f"s.add(Not({conclusion}))"
            exec(negated_conclusion, globals(), locals_dict)
        except Exception as e:
            print(f"[Z3 MCP] Error negating conclusion '{conclusion}': {e}")
            traceback.print_exc()
            return False

        # Check if the conclusion follows from the premises
        result = context['solver'].check()

        if result == unsat:
            # Unsatisfiable with negated conclusion = conclusion is proven!
            print(f"[Z3 MCP] PROVEN: {conclusion}")
            return True
        elif result == sat:
            # Satisfiable with negated conclusion = conclusion is NOT proven (counterexample exists)
            model = context['solver'].model()
            counterexample = []
            for decl in model.decls():
                name = decl.name()
                value = model[decl]
                counterexample.append(f"{name}={value}")

            print(f"[Z3 MCP] NOT PROVEN: {conclusion}")
            print(f"[Z3 MCP] Counterexample: {', '.join(counterexample)}")
            return False
        else:
            # Unknown result
            print(f"[Z3 MCP] UNKNOWN: Could not determine if {conclusion} follows")
            return False

    except Exception as e:
        print(f"[Z3 MCP] Error proving theorem: {e}")
        traceback.print_exc()
        return False


@mcp.tool()
def check_satisfiability(constraints: List[str]) -> dict:
    """
    Check if a set of logical constraints is satisfiable and return a model if it exists.

    This tool checks if there exists any assignment of values that satisfies all constraints.
    Unlike prove_logic which proves theorems, this finds solutions to constraint problems.

    SYNTAX: Same as prove_logic premises, but focused on finding solutions rather than proofs.

    EXAMPLE - Find values satisfying constraints:
    ---------------------------------------------
    constraints = [
        "Object = DeclareSort('Object')",
        "s = Solver()",
        "x = Int('x')",
        "y = Int('y')",
        "s.add(x + y == 10)",
        "s.add(x > 3)",
        "s.add(y > 2)"
    ]

    Returns:
        {
            "satisfiable": True/False,
            "model": {"x": "4", "y": "6"} or None
        }
    """
    try:
        locals_dict = {}
        solver = None

        # Execute all constraints
        for constraint in constraints:
            try:
                exec(constraint, globals(), locals_dict)
                if 's' in locals_dict:
                    solver = locals_dict['s']
            except Exception as e:
                return {
                    "satisfiable": False,
                    "error": f"Error in constraint '{constraint}': {str(e)}"
                }

        if solver is None:
            return {
                "satisfiable": False,
                "error": "No solver created. Include 's = Solver()' in constraints."
            }

        # Check satisfiability
        result = solver.check()

        if result == sat:
            model = solver.model()
            model_dict = {}
            for decl in model.decls():
                model_dict[decl.name()] = str(model[decl])

            return {
                "satisfiable": True,
                "model": model_dict
            }
        elif result == unsat:
            return {
                "satisfiable": False,
                "model": None
            }
        else:
            return {
                "satisfiable": False,
                "model": None,
                "error": "Unknown result from solver"
            }

    except Exception as e:
        return {
            "satisfiable": False,
            "error": f"Error checking satisfiability: {str(e)}"
        }


@mcp.tool()
def solve_equations(equation: str) -> dict:
    """
    Solve equations or systems of equations using Z3 solver.

    This tool can solve algebraic equations, inequalities, and systems of constraints.
    Variables are automatically detected from the equation string.

    SYNTAX:
    -------
    - Separate multiple constraints with commas
    - Use standard Python operators: +, -, *, /, ==, !=, <, >, <=, >=
    - Variables are automatically detected (any letters not in operators/numbers)

    EXAMPLES:
    ---------
    Simple equation:
        "x + 5 == 10"
        Returns: {"x": "5"}

    System of equations:
        "x + y == 10, x - y == 2"
        Returns: {"x": "6", "y": "4"}

    Inequalities:
        "x > 0, x < 100, x * 2 == 50"
        Returns: {"x": "25"}

    Complex constraints:
        "x + y == 10, x > 3, y > 2, x * y == 21"
        Returns: {"x": "7", "y": "3"} or {"x": "3", "y": "7"}

    Args:
        equation: String containing equations/constraints separated by commas

    Returns:
        Dictionary with:
        - status: "satisfiable", "unsatisfiable", or "error"
        - solution: Dict mapping variables to values (if satisfiable)
        - message: Human-readable description
    """
    return solve_equation(equation)


@mcp.tool()
def extract_semantic_relations(sentence: str) -> dict:
    """
    Extract semantic relations from natural language sentences.

    This tool analyzes sentences to identify relationships between entities.
    Uses NLTK for natural language processing.

    RELATION TYPES DETECTED:
    ------------------------
    - "is" / "is_not": Identity relations (X is Y, X is not Y)
    - "has": Possession relations (X has Y)
    - "subset_of": Class inclusion (All X are Y)
    - "greater_than" / "less_than": Comparisons
    - Verb-based: Any verb connecting two nouns (X loves Y, X contains Y)

    EXAMPLES:
    ---------
    Identity:
        "Socrates is a philosopher"
        Returns: [{"subject": "socrates", "relation": "is", "object": "philosopher"}]

    Possession:
        "John has a car"
        Returns: [{"subject": "john", "relation": "has", "object": "car"}]

    Comparison:
        "The mountain is greater than the hill"
        Returns: [{"subject": "mountain", "relation": "greater_than", "object": "hill"}]

    Subset:
        "All humans are mortal"
        Returns: [{"subject": "humans", "relation": "subset_of", "object": "mortal"}]

    Custom verb:
        "Alice loves Bob"
        Returns: [{"subject": "alice", "relation": "loves", "object": "bob"}]

    Args:
        sentence: Natural language sentence to analyze

    Returns:
        Dictionary with:
        - relations: List of {"subject": str, "relation": str, "object": str}
        - count: Number of relations found
        - sentence: Original sentence
    """
    try:
        relations_list = extract_relations(sentence)

        formatted_relations = []
        for subj, rel, obj in relations_list:
            formatted_relations.append({
                "subject": subj,
                "relation": rel,
                "object": obj
            })

        return {
            "relations": formatted_relations,
            "count": len(formatted_relations),
            "sentence": sentence
        }
    except Exception as e:
        return {
            "relations": [],
            "count": 0,
            "sentence": sentence,
            "error": str(e)
        }


@mcp.tool()
def convert_natural_language(premises: List[str], conclusion: str) -> dict:
    """
    Convert natural language statements to Z3 logic formulas.

    This tool bridges natural language and formal logic by converting
    English statements into Z3 theorem prover syntax. The output can be
    used directly with the prove_logic tool.

    WORKFLOW:
    ---------
    1. Extract entities and relations from natural language
    2. Define Z3 sorts, constants, and functions
    3. Generate Z3 constraints
    4. Format conclusion as Z3 expression

    EXAMPLE - Socrates Syllogism:
    ------------------------------
    premises = [
        "All humans are mortal",
        "Socrates is a human"
    ]
    conclusion = "Socrates is mortal"

    Returns:
    {
        "premises": [
            "Object = DeclareSort('Object')",
            "s = Solver()",
            "humans = Const('humans', Object)",
            "mortal = Const('mortal', Object)",
            "socrates = Const('socrates', Object)",
            "SubsetOf = Function('SubsetOf', Object, Object, BoolSort())",
            "Is = Function('Is', Object, Object, BoolSort())",
            "s.add(SubsetOf(humans, mortal))",
            "s.add(Is(socrates, humans))"
        ],
        "conclusion": "Is(socrates, mortal)"
    }

    USAGE WITH prove_logic:
    -----------------------
    1. Call convert_natural_language to get Z3 formulas
    2. Pass the result to prove_logic to verify the conclusion

    Args:
        premises: List of natural language statements (assumptions)
        conclusion: Natural language conclusion to prove

    Returns:
        Dictionary with:
        - premises: List of Z3 statements (strings)
        - conclusion: Z3 expression (string)
    """
    try:
        return natural_language_to_logic(premises, conclusion)
    except Exception as e:
        return {
            "error": str(e),
            "premises": [],
            "conclusion": ""
        }


# Run the server
if __name__ == "__main__":
    import sys

    # Default configuration
    host = "0.0.0.0"  # Change to "0.0.0.0" to accept connections from any IP
    port = 8000
    path = "/mcp"

    # Allow command-line overrides
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    if len(sys.argv) > 3:
        path = sys.argv[3]

    print("="*70)
    print("Z3 Logic Solver MCP Server")
    print("="*70)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Path: {path}")
    print(f"URL:  http://{host}:{port}{path}")
    print("="*70)
    print("\nServer is starting...")
    print("Press Ctrl+C to stop the server\n")

    # Run the server with HTTP transport
    #uvicorn.run(
    #    mcp, 
    #    host=host, 
    #    port=port
    #)
    #mcp.run(transport="http", host="0.0.0.0", port=8000)
    mcp.run(transport="streamable-http")