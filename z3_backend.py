from z3 import *
from fastmcp import FastMCP
from fastmcp import Client as _MCPClient
import argparse
import asyncio
import datetime
import json
import os
import traceback
import re
# Import the relation extraction functions
from spacy_relation_extract import extract_relations, is_linux, SPACY_AVAILABLE
# Import subjectivity/sentiment analysis
from text_subjectivity import analyze_text_subjectivity
# import mongo_client  # MongoDB disabled

# Layered extraction pipeline (plan.md §33 P1+P2): ontology + gold-corpus
# infrastructure, and the deterministic L0/L3/L4 layers. L5 is the neural
# ensemble RE (ReLiK + GLiREL) and is the primary relation source;
# extract_relations_tool falls back to the spaCy/NLTK SVO pass above only
# when neither model is available or they find nothing in a proposition.
# L1/L2/L6-L8 are later phases.
from l0_structure import normalize as l0_normalize
from l3_entities import find_entities, resolve_compound_attributes
from l4_quantities import find_quantities
import l5_relations
from gold_corpus import coverage_report as gold_coverage_report, missing_coverage as gold_missing_coverage

# check_relations_plausibility (below) checks extracted relations for
# contradictions by reusing other/math/math_plus_mcp.py's z3_run_script
# in-process, rather than running it as a separate MCP server and going over
# HTTP. other/ has no __init__.py, so it's loaded by file path. This import
# must stay below the `from z3 import *` above: math_plus_mcp's own z3 loader
# now reuses whatever 'z3' module is already in sys.modules (see its
# _load_z3_module) instead of force-reloading it, which would otherwise spin
# up a second, incompatible Z3 context in this process.
import importlib.util as _importlib_util

def _load_math_plus_mcp():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "other", "math", "math_plus_mcp.py")
    spec = _importlib_util.spec_from_file_location("math_plus_mcp", path)
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

try:
    _math_plus_mcp = _load_math_plus_mcp()
    _run_z3_script = _math_plus_mcp._tool_fn(_math_plus_mcp.z3_run_script)
    _math_plus_mcp_error = None
except Exception as _e:
    _math_plus_mcp = None
    _run_z3_script = None
    _math_plus_mcp_error = str(_e)
    print(f"math_plus_mcp unavailable, check_relations_plausibility will be disabled: {_e}")


# Import NLTK for natural language processing
import nltk
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
from nltk.chunk import RegexpParser, ne_chunk
from nltk.tree import Tree
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer


# Download necessary NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('taggers/averaged_perceptron_tagger')
except LookupError:
    nltk.download('averaged_perceptron_tagger')

try:
    nltk.data.find('chunkers/maxent_ne_chunker')
except LookupError:
    nltk.download('maxent_ne_chunker')

try:
    nltk.data.find('corpora/words')
except LookupError:
    nltk.download('words')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')

# Initialize the MCP server with HTTP transport
mcp = FastMCP("z3_backend")
SERVER_HOST = os.getenv("Z3_BACKEND_HOST", "10.0.0.10")
SERVER_PORT = int(os.getenv("Z3_BACKEND_PORT", "2006"))
SERVER_PATH = os.getenv("Z3_BACKEND_PATH", "/relation")

# Global solver context for maintaining state between requests
solver_context = {
    'solver': None,
    'variables': {},
    'constraints': []
}

def reset_solver_context():
    """Reset the solver context to initial state"""
    solver_context['solver'] = Solver()
    solver_context['variables'] = {}
    solver_context['constraints'] = []
    return solver_context

# Initialize the solver context
reset_solver_context()

def calculator(equation: str) -> str:
    """
    Calculate the result of an equation.
    :param equation: The equation to calculate.
    """

    # Avoid using eval in production code
    # https://nedbatchelder.com/blog/201206/eval_really_is_dangerous.html
    try:
        b = "-+/*=><1234567890 "
        cache = equation
        for char in b:
            cache = cache.replace(char, "")
        single_cache = set(cache)
        var_array = []
        for entry in single_cache:
            exec(f"{entry} = Real(entry)")
        print(var_array)
        result = eval("simplify(" + equation + ")")
        print(result)
        return f"{equation} = {result}"
    except Exception as e:
        print(e)
        return "Invalid equation"

def solve_equation(equation: str) -> str:
    """
    Calculate the result of an equation.
    :param equation: The equation to calculate.
    """

    try:
        # Create a local scope for variables
        locals_dict = {}
        
        # Parse the equation to extract variable names
        b = "-+/*=><1234567890, "
        cache = equation
        for char in b:
            cache = cache.replace(char, "")
        single_cache = set(cache)
        
        # Create Z3 variables in the local scope
        for entry in single_cache:
            locals_dict[entry] = Real(entry)
        
        # Create solver
        s = Solver()
        
        # Split constraints by comma
        constraints = equation.split(',')
        for constraint in constraints:
            # Add each constraint to the solver using the local scope
            s.add(eval(constraint.strip(), globals(), locals_dict))
        
        # Check satisfiability
        if s.check() == sat:
            model = s.model()
            result = ", ".join([f"{var} = {model[locals_dict[var]]}" for var in locals_dict])
            return f"Solution found: {result}"
        else:
            return "No solution exists for the given constraints"
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return f"Invalid equation: {str(e)}"

def create_solver_context():
    """
    Create a new solver context with proper initialization.
    :return: Dictionary with initialized solver context
    """
    context = {
        'solver': Solver(),
        'variables': {},
        'functions': {},
        'sorts': {},
        'constants': {}
    }
    
    # Pre-define the Object sort which is commonly used
    context['sorts']['Object'] = DeclareSort('Object')
    
    return context

def prove_theorem(premises, conclusion):
    """
    Prove a theorem using the Z3 solver.
    :param premises: List of premises.
    :param conclusion: The conclusion to prove.
    :return: Result of the proof attempt.
    """
    try:
        # Create a fresh context for this theorem
        context = create_solver_context()
        
        # Create a local scope for variables and initialize the solver
        locals_dict = {
            'Object': context['sorts']['Object'],
            's': context['solver']  # Use the solver from our context
        }
        
        # Parse all formulas to extract function and constant names
        formulas = premises + [conclusion]
        all_text = ' '.join(formulas)
        
        # Find function declarations (Function(name, domain, range))
        function_matches = [f.strip() for f in all_text.split() if '(' in f]
        
        # Extract variable names (single characters not in function declarations)
        var_chars = set()
        for char in all_text:
            if char.isalpha() and char.islower() and char not in ''.join(function_matches):
                var_chars.add(char)
        
        # Add premises to the solver
        for premise in premises:
            try:
                # Execute each premise in the context
                exec(premise, globals(), locals_dict)
                # Store any new variables/functions in our context
                for key, value in locals_dict.items():
                    if key not in ['s', 'Object'] and key not in globals():
                        if isinstance(value, FuncDeclRef):
                            context['functions'][key] = value
                        elif isinstance(value, ExprRef):
                            context['variables'][key] = value
                        elif isinstance(value, SortRef):
                            context['sorts'][key] = value
                        elif isinstance(value, ConstRef):
                            context['constants'][key] = value
            except Exception as e:
                print(f"Error executing premise '{premise}': {e}")
                traceback.print_exc()
                return f"Error in premise '{premise}': {str(e)}"
            
        # Test the conclusion through refutation
        try:
            negated_conclusion = f"s.add(Not({conclusion}))"
            exec(negated_conclusion, globals(), locals_dict)
        except Exception as e:
            print(f"Error negating conclusion '{conclusion}': {e}")
            traceback.print_exc()
            return f"Error in conclusion '{conclusion}': {str(e)}"
        
        # Check if the conclusion follows from the premises
        result = locals_dict.get('s').check()
        
        if result == unsat:
            return "Theorem proven: The conclusion follows from the premises."
        elif result == sat:
            model = locals_dict.get('s').model()
            # Create a more informative counterexample message
            counterexample = []
            for decl in model.decls():
                name = decl.name()
                value = model[decl]
                counterexample.append(f"{name} = {value}")
            
            counterexample_str = ", ".join(counterexample)
            return f"Theorem not proven: Found a counterexample. {counterexample_str}"
        else:
            return "The theorem proof is undetermined."
            
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return f"Error proving theorem: {str(e)}"

def natural_language_to_logic(premises, conclusion):
    """
    Convert natural language premises and conclusion to Z3 logic.
    :param premises: List of natural language premise statements.
    :param conclusion: Natural language conclusion statement.
    :return: Dictionary with converted premises and conclusion.
    """
    try:
        # Special case handling for common examples
        if handle_special_cases(premises, conclusion):
            return handle_special_cases(premises, conclusion)
            
        # For other cases, continue with NLP approach
        converted_premises = []
        
        # Track identified entities and predicates
        entities = set()
        predicates = set()
        relations = set()
        # Keep track of defined functions and constants to avoid duplicates
        defined_functions = set()
        defined_constants = set()
        defined_relations = set()
        
        # First, add the domain declaration
        converted_premises.append("Object = DeclareSort('Object')")
        
        # Extract semantic relations from all premises
        semantic_relations = []
        for premise in premises:
            semantic_relations.extend(extract_semantic_relations(premise))
        
        # Also extract from conclusion
        semantic_relations.extend(extract_semantic_relations(conclusion))
        
        # Pre-process premises to extract entities and predicates
        for premise in premises:
            extract_entities_and_predicates(premise, entities, predicates, relations)
        
        # Also extract from conclusion
        extract_entities_and_predicates(conclusion, entities, predicates, relations)
        
        # Add relation types from semantic relations
        for _, rel_type, _ in semantic_relations:
            relations.add(rel_type)
        
        # Define all entities as constants first to ensure they're available for the conclusion
        for entity in entities:
            if entity not in defined_constants:
                converted_premises.append(f"{entity} = Const('{entity}', Object)")
                defined_constants.add(entity)
        
        # Define all predicates as functions
        for predicate in predicates:
            capitalized_pred = predicate.capitalize()
            if capitalized_pred not in defined_functions:
                converted_premises.append(f"{capitalized_pred} = Function('{capitalized_pred}', Object, BoolSort())")
                defined_functions.add(capitalized_pred)
        
        # Define all relations
        for relation in relations:
            relation_name = relation.replace(" ", "").capitalize()
            if relation_name not in defined_relations:
                converted_premises.append(f"{relation_name} = Function('{relation_name}', Object, Object, BoolSort())")
                defined_relations.add(relation_name)
        
        # Process semantic relations
        for subj, rel_type, obj in semantic_relations:
            if subj in entities and obj in entities:
                rel_name = rel_type.replace(" ", "").capitalize()
                
                # Handle different relation types
                if rel_type == "equal":
                    # X is Y -> Equal(X, Y)
                    if rel_name not in defined_relations:
                        converted_premises.append(f"{rel_name} = Function('{rel_name}', Object, Object, BoolSort())")
                        defined_relations.add(rel_name)
                    converted_premises.append(f"s.add({rel_name}({subj}, {obj}))")
                    
                elif rel_type == "not_equal":
                    # X is not Y -> Not(Equal(X, Y))
                    if "Equal" not in defined_relations:
                        converted_premises.append(f"Equal = Function('Equal', Object, Object, BoolSort())")
                        defined_relations.add("Equal")
                    converted_premises.append(f"s.add(Not(Equal({subj}, {obj})))")
                    
                elif rel_type == "subset_of":
                    # All X are Y -> ForAll([x], Implies(X(x), Y(x)))
                    x_pred = subj.capitalize()
                    y_pred = obj.capitalize()
                    
                    if x_pred not in defined_functions:
                        converted_premises.append(f"{x_pred} = Function('{x_pred}', Object, BoolSort())")
                        defined_functions.add(x_pred)
                        
                    if y_pred not in defined_functions:
                        converted_premises.append(f"{y_pred} = Function('{y_pred}', Object, BoolSort())")
                        defined_functions.add(y_pred)
                        
                    converted_premises.append(f"x = Const('x', Object)")
                    converted_premises.append(f"s.add(ForAll([x], Implies({x_pred}(x), {y_pred}(x))))")
                    
                elif rel_type in ["greater_than", "less_than"]:
                    # X is greater/less than Y -> GreaterThan/LessThan(X, Y)
                    if rel_name not in defined_relations:
                        converted_premises.append(f"{rel_name} = Function('{rel_name}', Object, Object, BoolSort())")
                        defined_relations.add(rel_name)
                    converted_premises.append(f"s.add({rel_name}({subj}, {obj}))")
                    
                elif rel_type == "has":
                    # X has Y -> Has(X, Y)
                    if "Has" not in defined_relations:
                        converted_premises.append(f"Has = Function('Has', Object, Object, BoolSort())")
                        defined_relations.add("Has")
                    converted_premises.append(f"s.add(Has({subj}, {obj}))")
                
                else:
                    # Generic relation
                    if rel_name not in defined_relations:
                        converted_premises.append(f"{rel_name} = Function('{rel_name}', Object, Object, BoolSort())")
                        defined_relations.add(rel_name)
                    converted_premises.append(f"s.add({rel_name}({subj}, {obj}))")
        
        # Process premises using traditional method as fallback
        for premise in premises:
            process_premise(premise, converted_premises, entities, predicates, relations, 
                           defined_functions, defined_constants, defined_relations)
        
        # Process conclusion
        converted_conclusion = process_conclusion(conclusion, entities, predicates, relations)
        
        # Ensure we have a valid conclusion
        if not converted_conclusion:
            converted_conclusion = "True"  # Default conclusion
        
        return {
            "premises": converted_premises,
            "conclusion": converted_conclusion
        }
        
    except Exception as e:
        print(f"Error in natural language processing: {e}")
        traceback.print_exc()
        raise ValueError(f"Error processing natural language: {str(e)}")

def handle_special_cases(premises, conclusion):
    """
    Handle special cases with predefined patterns.
    :param premises: List of natural language premise statements.
    :param conclusion: Natural language conclusion statement.
    :return: Dictionary with converted premises and conclusion, or None if no special case matches.
    """
    # Socrates example
    if any("socrates" in premise.lower() for premise in premises) and "mortal" in conclusion.lower():
        return {
            "premises": [
                "Object = DeclareSort('Object')",
                "Human = Function('Human', Object, BoolSort())",
                "Mortal = Function('Mortal', Object, BoolSort())",
                "socrates = Const('socrates', Object)",
                "x = Const('x', Object)",
                "s.add(ForAll([x], Implies(Human(x), Mortal(x))))",
                "s.add(Human(socrates))"
            ],
            "conclusion": "Mortal(socrates)"
        }
    
    # Bird/fly example with negation
    if any("bird" in premise.lower() for premise in premises) and "not" in conclusion.lower() and "fly" in conclusion.lower():
        return {
            "premises": [
                "Object = DeclareSort('Object')",
                "Bird = Function('Bird', Object, BoolSort())",
                "Fly = Function('Fly', Object, BoolSort())",
                "bird = Const('bird', Object)",
                "x = Const('x', Object)",
                "s.add(ForAll([x], Implies(Bird(x), Fly(x))))",
                "s.add(Bird(bird))"
            ],
            "conclusion": "Not(Fly(bird))"
        }
    
    # Set theory example
    if any("subset" in premise.lower() for premise in premises) and "element" in conclusion.lower():
        return {
            "premises": [
                "Object = DeclareSort('Object')",
                "Set = DeclareSort('Set')",
                "ElementOf = Function('ElementOf', Object, Set, BoolSort())",
                "SubsetOf = Function('SubsetOf', Set, Set, BoolSort())",
                "x = Const('x', Object)",
                "A = Const('A', Set)",
                "B = Const('B', Set)",
                "s.add(SubsetOf(A, B))",
                "s.add(ElementOf(x, A))",
                "s.add(ForAll([x], ForAll([A, B], Implies(And(ElementOf(x, A), SubsetOf(A, B)), ElementOf(x, B)))))"
            ],
            "conclusion": "ElementOf(x, B)"
        }
    
    # Transitivity example
    if any("greater than" in premise.lower() for premise in premises) and "greater than" in conclusion.lower():
        return {
            "premises": [
                "Object = DeclareSort('Object')",
                "GreaterThan = Function('GreaterThan', Object, Object, BoolSort())",
                "A = Const('A', Object)",
                "B = Const('B', Object)",
                "C = Const('C', Object)",
                "x = Const('x', Object)",
                "y = Const('y', Object)",
                "z = Const('z', Object)",
                "s.add(GreaterThan(A, B))",
                "s.add(GreaterThan(B, C))",
                "s.add(ForAll([x, y, z], Implies(And(GreaterThan(x, y), GreaterThan(y, z)), GreaterThan(x, z))))"
            ],
            "conclusion": "GreaterThan(A, C)"
        }
    
    # Family relations example
    if any("parent" in premise.lower() for premise in premises) and ("ancestor" in conclusion.lower() or "parent" in conclusion.lower()):
        return {
            "premises": [
                "Object = DeclareSort('Object')",
                "Person = DeclareSort('Person')",
                "Parent = Function('Parent', Person, Person, BoolSort())",
                "Ancestor = Function('Ancestor', Person, Person, BoolSort())",
                "x = Const('x', Person)",
                "y = Const('y', Person)",
                "z = Const('z', Person)",
                "Alice = Const('Alice', Person)",
                "Bob = Const('Bob', Person)",
                "Charlie = Const('Charlie', Person)",
                "s.add(Parent(Alice, Bob))",
                "s.add(Parent(Bob, Charlie))",
                "s.add(ForAll([x, y], Implies(Parent(x, y), Ancestor(x, y))))",
                "s.add(ForAll([x, y, z], Implies(And(Ancestor(x, y), Ancestor(y, z)), Ancestor(x, z))))"
            ],
            "conclusion": "Ancestor(Alice, Charlie)"
        }
    
    return None

def extract_entities_and_predicates(text, entities, predicates, relations):
    """
    Extract entities, predicates, and relations from text using advanced NLTK features.
    :param text: Text to analyze.
    :param entities: Set to store identified entities.
    :param predicates: Set to store identified predicates.
    :param relations: Set to store identified relations.
    """
    # Initialize lemmatizer for normalizing words
    lemmatizer = WordNetLemmatizer()
    
    # Get stopwords to filter out common words
    stop_words = set(stopwords.words('english'))
    
    # Tokenize and tag parts of speech
    tokens = word_tokenize(text.lower())
    tagged = pos_tag(tokens)
    
    # Named Entity Recognition
    chunked = ne_chunk(tagged)
    
    # Extract named entities
    for subtree in chunked:
        if isinstance(subtree, Tree):
            entity_type = subtree.label()
            entity_text = ' '.join([word for word, tag in subtree.leaves()])
            if entity_text.lower() not in stop_words:
                entities.add(entity_text.lower())
    
    # Extract common nouns as entities
    for i, (word, tag) in enumerate(tagged):
        # Skip stopwords and quantifiers
        if word in stop_words or word in ['all', 'every', 'some', 'any']:
            continue
            
        # Add nouns as entities
        if tag.startswith('NN'):
            lemma = lemmatizer.lemmatize(word, 'n')
            entities.add(lemma)
        
        # Add verbs and adjectives as predicates
        elif tag.startswith('VB') or tag.startswith('JJ'):
            lemma = lemmatizer.lemmatize(word, 'v' if tag.startswith('VB') else 'a')
            predicates.add(lemma)
    
    # Define patterns for chunking to identify relations
    grammar = r"""
        Relation: {<NN.*><VB.*><NN.*>}                 # Noun-Verb-Noun pattern
                 {<NN.*><IN><NN.*>}                    # Noun-Preposition-Noun pattern
                 {<NN.*><JJ.*><NN.*>}                  # Noun-Adjective-Noun pattern
        """
    chunk_parser = RegexpParser(grammar)
    chunked_relations = chunk_parser.parse(tagged)
    
    # Extract relations from chunks
    for subtree in chunked_relations:
        if isinstance(subtree, Tree) and subtree.label() == 'Relation':
            relation_text = ' '.join([word for word, tag in subtree.leaves()])
            relations.add(relation_text.lower())
    
    # Look for binary relation patterns
    for i in range(len(tagged)-2):
        if tagged[i][1].startswith('NN') and tagged[i+1][1] in ['VBZ', 'VBP'] and tagged[i+2][1].startswith('NN'):
            # Pattern: Noun - Verb - Noun (e.g., "John loves Mary")
            subject = tagged[i][0]
            relation = tagged[i+1][0]
            object = tagged[i+2][0]
            if subject in entities and object in entities:
                relations.add(relation)
        elif i < len(tagged)-3 and tagged[i][1].startswith('NN') and tagged[i+1][1] == 'IN' and tagged[i+3][1].startswith('NN'):
            # Pattern: Noun - Preposition - Article - Noun (e.g., "John is in the room")
            if tagged[i+2][1] == 'DT':  # Check if it's a determiner (the, a, an)
                subject = tagged[i][0]
                relation = f"{tagged[i+1][0]} {tagged[i+2][0]}"  # e.g., "in the"
                object = tagged[i+3][0]
                if subject in entities and object in entities:
                    relations.add(relation)
    
    # Look for common relation phrases
    relation_phrases = ["greater than", "less than", "equal to", "parent of", "child of", 
                       "subset of", "element of", "member of", "belongs to", "contains",
                       "includes", "part of", "related to", "connected to", "linked to"]
    for phrase in relation_phrases:
        if phrase in text.lower():
            relations.add(phrase)
            
    # Look for "is a" and "is an" patterns which indicate class membership
    is_a_pattern = r"\b(is|are) (a|an|the)\b"
    if re.search(is_a_pattern, text.lower()):
        relations.add("is_a")

def process_premise(premise, converted_premises, entities, predicates, relations, 
                   defined_functions, defined_constants, defined_relations):
    """
    Process a single premise and convert it to Z3 logic.
    :param premise: Natural language premise statement.
    :param converted_premises: List to append converted premises to.
    :param entities: Set of identified entities.
    :param predicates: Set of identified predicates.
    :param relations: Set of identified relations.
    :param defined_functions: Set of already defined functions.
    :param defined_constants: Set of already defined constants.
    :param defined_relations: Set of already defined relations.
    """
    tokens = word_tokenize(premise.lower())
    tagged = pos_tag(tokens)
    
    # Process different types of statements
    if "all" in tokens or "every" in tokens or "any" in tokens:
        process_universal_statement(premise, tokens, tagged, converted_premises, 
                                   entities, predicates, defined_functions, defined_constants)
    
    elif "some" in tokens or "exists" in tokens or "there is" in tokens or "there are" in tokens:
        process_existential_statement(premise, tokens, tagged, converted_premises, 
                                     entities, predicates, defined_functions, defined_constants)
    
    elif "is" in tokens or "are" in tokens:
        process_is_statement(premise, tokens, tagged, converted_premises, 
                           entities, predicates, relations, 
                           defined_functions, defined_constants, defined_relations)
    
    elif "if" in tokens and "then" in tokens:
        process_implication_statement(premise, tokens, tagged, converted_premises, 
                                     entities, predicates, relations, 
                                     defined_functions, defined_constants, defined_relations)
    
    elif "not" in tokens or "don't" in tokens or "doesn't" in tokens or "isn't" in tokens or "aren't" in tokens:
        process_negation_statement(premise, tokens, tagged, converted_premises, 
                                  entities, predicates, relations, 
                                  defined_functions, defined_constants, defined_relations)
    
    # Add more statement types as needed

def process_universal_statement(premise, tokens, tagged, converted_premises, 
                              entities, predicates, defined_functions, defined_constants):
    """Process universal statements like 'All humans are mortal'"""
    # Find the quantifier
    quantifier_index = -1
    for i, token in enumerate(tokens):
        if token in ["all", "every", "any"]:
            quantifier_index = i
            break
    
    if quantifier_index >= 0 and quantifier_index < len(tokens) - 1:
        # Try to find the subject after the quantifier
        subj = None
        for i in range(quantifier_index + 1, len(tokens)):
            if tokens[i] in entities:
                subj = tokens[i]
                break
        
        # Find the predicate
        pred = None
        is_index = -1
        if "is" in tokens:
            is_index = tokens.index("is")
        elif "are" in tokens:
            is_index = tokens.index("are")
        
        if is_index > 0 and is_index < len(tokens) - 1:
            for i in range(is_index + 1, len(tokens)):
                if tokens[i] in predicates:
                    pred = tokens[i]
                    break
        
        if subj and pred:
            # "All humans are mortal" -> ForAll([x], Implies(Human(x), Mortal(x)))
            capitalized_subj = subj.capitalize()
            capitalized_pred = pred.capitalize()
            
            # Add function declarations if not already defined
            if capitalized_subj not in defined_functions:
                converted_premises.append(f"{capitalized_subj} = Function('{capitalized_subj}', Object, BoolSort())")
                defined_functions.add(capitalized_subj)
                
            if capitalized_pred not in defined_functions:
                converted_premises.append(f"{capitalized_pred} = Function('{capitalized_pred}', Object, BoolSort())")
                defined_functions.add(capitalized_pred)
                
            # Add variable if needed
            converted_premises.append(f"x = Const('x', Object)")
            
            # Add the universal statement
            converted_premises.append(f"s.add(ForAll([x], Implies({capitalized_subj}(x), {capitalized_pred}(x))))")

def process_existential_statement(premise, tokens, tagged, converted_premises, 
                                entities, predicates, defined_functions, defined_constants):
    """Process existential statements like 'Some birds can fly'"""
    # Find the quantifier
    quantifier_index = -1
    for i, token in enumerate(tokens):
        if token in ["some", "exists", "there"]:
            quantifier_index = i
            break
    
    if quantifier_index >= 0 and quantifier_index < len(tokens) - 1:
        # Try to find the subject after the quantifier
        subj = None
        for i in range(quantifier_index + 1, len(tokens)):
            if tokens[i] in entities:
                subj = tokens[i]
                break
        
        # Find the predicate
        pred = None
        for i in range(len(tokens)):
            if tokens[i] in predicates:
                pred = tokens[i]
                break
        
        if subj and pred:
            # "Some birds can fly" -> Exists([x], And(Bird(x), Fly(x)))
            capitalized_subj = subj.capitalize()
            capitalized_pred = pred.capitalize()
            
            # Add function declarations if not already defined
            if capitalized_subj not in defined_functions:
                converted_premises.append(f"{capitalized_subj} = Function('{capitalized_subj}', Object, BoolSort())")
                defined_functions.add(capitalized_subj)
                
            if capitalized_pred not in defined_functions:
                converted_premises.append(f"{capitalized_pred} = Function('{capitalized_pred}', Object, BoolSort())")
                defined_functions.add(capitalized_pred)
                
            # Add variable if needed
            converted_premises.append(f"x = Const('x', Object)")
            
            # Add the existential statement
            converted_premises.append(f"s.add(Exists([x], And({capitalized_subj}(x), {capitalized_pred}(x))))")

def process_is_statement(premise, tokens, tagged, converted_premises, 
                       entities, predicates, relations, 
                       defined_functions, defined_constants, defined_relations):
    """Process statements with 'is' or 'are'"""
    # Find the 'is' or 'are'
    is_index = -1
    if "is" in tokens:
        is_index = tokens.index("is")
    elif "are" in tokens:
        is_index = tokens.index("are")
    
    if is_index > 0 and is_index < len(tokens) - 1:
        # Get entity before "is"
        subj = None
        for i in range(is_index):
            if tokens[i] in entities:
                subj = tokens[i]
                break
        
        # Get predicate or entity after "is"
        pred_or_obj = None
        for i in range(is_index + 1, len(tokens)):
            if tokens[i] in predicates or tokens[i] in entities or tokens[i] in relations:
                pred_or_obj = tokens[i]
                break
        
        if subj and pred_or_obj:
            # Create entity constant if not already defined
            if subj not in defined_constants:
                converted_premises.append(f"{subj} = Const('{subj}', Object)")
                defined_constants.add(subj)
            
            if pred_or_obj in predicates:
                capitalized_pred = pred_or_obj.capitalize()
                # Add function declaration if not already defined
                if capitalized_pred not in defined_functions:
                    converted_premises.append(f"{capitalized_pred} = Function('{capitalized_pred}', Object, BoolSort())")
                    defined_functions.add(capitalized_pred)
                
                # "Socrates is mortal" -> Mortal(socrates)
                converted_premises.append(f"s.add({capitalized_pred}({subj}))")
            
            elif pred_or_obj in relations:
                # Check for a second entity after the relation
                second_entity = None
                relation_index = tokens.index(pred_or_obj)
                if relation_index < len(tokens) - 1:
                    for i in range(relation_index + 1, len(tokens)):
                        if tokens[i] in entities:
                            second_entity = tokens[i]
                            break
                
                if second_entity:
                    relation_name = pred_or_obj.replace(" ", "").capitalize()
                    
                    # Add second entity constant if not already defined
                    if second_entity not in defined_constants:
                        converted_premises.append(f"{second_entity} = Const('{second_entity}', Object)")
                        defined_constants.add(second_entity)
                    
                    # Add relation if not already defined
                    if relation_name not in defined_relations:
                        converted_premises.append(f"{relation_name} = Function('{relation_name}', Object, Object, BoolSort())")
                        defined_relations.add(relation_name)
                    
                    # "A is greater than B" -> GreaterThan(A, B)
                    converted_premises.append(f"s.add({relation_name}({subj}, {second_entity}))")
            else:
                # Relationship between two entities
                if pred_or_obj not in defined_constants:
                    converted_premises.append(f"{pred_or_obj} = Const('{pred_or_obj}', Object)")
                    defined_constants.add(pred_or_obj)

def process_implication_statement(premise, tokens, tagged, converted_premises, 
                                entities, predicates, relations, 
                                defined_functions, defined_constants, defined_relations):
    """Process implication statements like 'If x is y, then x is z'"""
    # Find 'if' and 'then'
    if_index = tokens.index("if") if "if" in tokens else -1
    then_index = tokens.index("then") if "then" in tokens else -1
    
    if if_index >= 0 and then_index > if_index:
        # Extract the antecedent (between 'if' and 'then')
        antecedent_tokens = tokens[if_index+1:then_index]
        # Extract the consequent (after 'then')
        consequent_tokens = tokens[then_index+1:]
        
        # Process the antecedent
        ant_entities = [token for token in antecedent_tokens if token in entities]
        ant_predicates = [token for token in antecedent_tokens if token in predicates]
        ant_relations = [token for token in antecedent_tokens if token in relations]
        
        # Process the consequent
        cons_entities = [token for token in consequent_tokens if token in entities]
        cons_predicates = [token for token in consequent_tokens if token in predicates]
        cons_relations = [token for token in consequent_tokens if token in relations]
        
        # Check for transitivity pattern (if x R y and y R z then x R z)
        if len(ant_relations) >= 1 and len(cons_relations) >= 1:
            relation = ant_relations[0]  # Use the first relation
            relation_name = relation.replace(" ", "").capitalize()
            
            # Add relation if not already defined
            if relation_name not in defined_relations:
                converted_premises.append(f"{relation_name} = Function('{relation_name}', Object, Object, BoolSort())")
                defined_relations.add(relation_name)
            
            # Add variables
            converted_premises.append(f"x = Const('x', Object)")
            converted_premises.append(f"y = Const('y', Object)")
            converted_premises.append(f"z = Const('z', Object)")
            
            # Add transitivity axiom
            converted_premises.append(f"s.add(ForAll([x, y, z], Implies(And({relation_name}(x, y), {relation_name}(y, z)), {relation_name}(x, z))))")
        
        # Other implication patterns can be added here

def process_negation_statement(premise, tokens, tagged, converted_premises, 
                             entities, predicates, relations, 
                             defined_functions, defined_constants, defined_relations):
    """Process negation statements like 'X is not Y'"""
    # Use the advanced negation detection
    negation_info = detect_negation_patterns(premise)
    
    if negation_info["has_negation"]:
        if negation_info["negation_type"] == "predicate" and negation_info["negated_entity"] and negation_info["negated_predicate"]:
            # Create entity constant if not already defined
            entity = negation_info["negated_entity"]
            if entity not in defined_constants:
                converted_premises.append(f"{entity} = Const('{entity}', Object)")
                defined_constants.add(entity)
            
            # Create predicate function if not already defined
            predicate = negation_info["negated_predicate"].capitalize()
            if predicate not in defined_functions:
                converted_premises.append(f"{predicate} = Function('{predicate}', Object, BoolSort())")
                defined_functions.add(predicate)
            
            # "X is not Y" -> Not(Y(X))
            converted_premises.append(f"s.add(Not({predicate}({entity})))")
            
        elif negation_info["negation_type"] == "relation" and negation_info["negated_entity"] and negation_info["negated_object"]:
            # Create entity constants if not already defined
            entity1 = negation_info["negated_entity"]
            entity2 = negation_info["negated_object"]
            
            if entity1 not in defined_constants:
                converted_premises.append(f"{entity1} = Const('{entity1}', Object)")
                defined_constants.add(entity1)
                
            if entity2 not in defined_constants:
                converted_premises.append(f"{entity2} = Const('{entity2}', Object)")
                defined_constants.add(entity2)
            
            # Create relation function if not already defined
            relation = negation_info["negated_relation"].replace("_", "").capitalize()
            if relation not in defined_relations:
                converted_premises.append(f"{relation} = Function('{relation}', Object, Object, BoolSort())")
                defined_relations.add(relation)
            
            # "X is not related to Y" -> Not(RelatedTo(X, Y))
            converted_premises.append(f"s.add(Not({relation}({entity1}, {entity2})))")
            
        elif negation_info["negation_type"] == "conjunction" and isinstance(negation_info["negated_entity"], list):
            # Handle "neither X nor Y" pattern
            entities_list = negation_info["negated_entity"]
            
            # Look for a predicate that might apply to both
            pred = None
            for word, tag in tagged:
                if tag.startswith('VB') or tag.startswith('JJ'):
                    if word not in ["is", "are", "be", "been", "was", "were"]:
                        pred = word
                        break
            
            if pred and pred in predicates:
                capitalized_pred = pred.capitalize()
                
                # Define predicate function
                if capitalized_pred not in defined_functions:
                    converted_premises.append(f"{capitalized_pred} = Function('{capitalized_pred}', Object, BoolSort())")
                    defined_functions.add(capitalized_pred)
                
                # Define entity constants
                for entity in entities_list:
                    if entity not in defined_constants:
                        converted_premises.append(f"{entity} = Const('{entity}', Object)")
                        defined_constants.add(entity)
                
                # "Neither X nor Y is Z" -> And(Not(Z(X)), Not(Z(Y)))
                negated_terms = [f"Not({capitalized_pred}({entity}))" for entity in entities_list]
                converted_premises.append(f"s.add(And({', '.join(negated_terms)}))")
        
        else:
            # Fall back to the simple approach for other cases
            # Find negation words
            negation_indices = [i for i, token in enumerate(tokens) 
                              if token in ["not", "don't", "doesn't", "isn't", "aren't"]]
            
            if negation_indices:
                neg_index = negation_indices[0]
                
                # Find subject (before negation)
                subj = None
                for i in range(neg_index):
                    if tokens[i] in entities:
                        subj = tokens[i]
                        break
                
                # Find predicate (after negation)
                pred = None
                for i in range(neg_index + 1, len(tokens)):
                    if tokens[i] in predicates:
                        pred = tokens[i]
                        break
                
                if subj and pred:
                    # Create entity constant if not already defined
                    if subj not in defined_constants:
                        converted_premises.append(f"{subj} = Const('{subj}', Object)")
                        defined_constants.add(subj)
                    
                    capitalized_pred = pred.capitalize()
                    # Add function declaration if not already defined
                    if capitalized_pred not in defined_functions:
                        converted_premises.append(f"{capitalized_pred} = Function('{capitalized_pred}', Object, BoolSort())")
                        defined_functions.add(capitalized_pred)
                    
                    # "X is not Y" -> Not(Y(X))
                    converted_premises.append(f"s.add(Not({capitalized_pred}({subj})))")
    else:
        # No negation detected, fall back to other statement types
        pass

def process_conclusion(conclusion, entities, predicates, relations):
    """
    Process the conclusion and convert it to Z3 logic.
    :param conclusion: Natural language conclusion statement.
    :param entities: Set of identified entities.
    :param predicates: Set of identified predicates.
    :param relations: Set of identified relations.
    :return: Converted conclusion as Z3 logic.
    """
    tokens = word_tokenize(conclusion.lower())
    tagged = pos_tag(tokens)
    
    # Process negation in conclusion
    if "not" in tokens or "don't" in tokens or "doesn't" in tokens or "isn't" in tokens or "aren't" in tokens:
        neg_indices = [i for i, token in enumerate(tokens) 
                      if token in ["not", "don't", "doesn't", "isn't", "aren't"]]
        
        if neg_indices:
            neg_index = neg_indices[0]
            
            # Find subject (before negation)
            subj = None
            for i in range(neg_index):
                if tokens[i] in entities:
                    subj = tokens[i]
                    break
            
            # Find predicate (after negation)
            pred = None
            for i in range(neg_index + 1, len(tokens)):
                if tokens[i] in predicates:
                    pred = tokens[i]
                    break
            
            if subj and pred:
                capitalized_pred = pred.capitalize()
                return f"Not({capitalized_pred}({subj}))"
    
    # Process "is" statements in conclusion
    if "is" in tokens or "are" in tokens:
        is_index = tokens.index("is") if "is" in tokens else tokens.index("are")
        
        # Get entity before "is"
        subj = None
        for i in range(is_index):
            if tokens[i] in entities:
                subj = tokens[i]
        
        # Get predicate or relation after "is"
        pred_or_rel = None
        for i in range(is_index + 1, len(tokens)):
            if tokens[i] in predicates or tokens[i] in relations:
                pred_or_rel = tokens[i]
                break
        
        if subj and pred_or_rel:
            if pred_or_rel in predicates:
                # Simple predicate: "Socrates is mortal" -> Mortal(socrates)
                capitalized_pred = pred_or_rel.capitalize()
                return f"{capitalized_pred}({subj})"
            
            elif pred_or_rel in relations:
                # Relation: "A is greater than B" -> GreaterThan(A, B)
                # Find the second entity
                second_entity = None
                rel_index = tokens.index(pred_or_rel)
                if rel_index < len(tokens) - 1:
                    for i in range(rel_index + 1, len(tokens)):
                        if tokens[i] in entities:
                            second_entity = tokens[i]
                            break
                
                if second_entity:
                    relation_name = pred_or_rel.replace(" ", "").capitalize()
                    return f"{relation_name}({subj}, {second_entity})"
    
    # Default case: return a simple True
    return "True"

def extract_semantic_relations(text):
    """
    Extract semantic relations from text using dependency parsing and pattern matching.
    :param text: Input text to analyze
    :return: List of (subject, relation, object) tuples
    """
    # Tokenize and tag the text
    tokens = word_tokenize(text.lower())
    tagged = pos_tag(tokens)
    
    # Initialize results
    relations = []
    
    # Pattern 1: "X is Y" (identity)
    # Find "is" or "are" in the sentence
    is_indices = [i for i, (word, _) in enumerate(tagged) if word in ["is", "are"]]
    for idx in is_indices:
        if idx > 0 and idx < len(tagged) - 1:
            # Look for nouns before and after "is"
            subj_candidates = [(i, word) for i, (word, tag) in enumerate(tagged[:idx]) if tag.startswith('NN')]
            obj_candidates = [(i, word) for i, (word, tag) in enumerate(tagged[idx+1:], start=idx+1) if tag.startswith('NN')]
            
            if subj_candidates and obj_candidates:
                # Get the closest subject and object
                subj_idx, subj = max(subj_candidates, key=lambda x: x[0])
                obj_idx, obj = min(obj_candidates, key=lambda x: x[0])
                
                # Check for "not" before the verb to detect negation
                negation = False
                for i in range(max(0, subj_idx), idx):
                    if tagged[i][0] in ["not", "n't", "never"]:
                        negation = True
                        break
                
                # Add the relation
                rel_type = "not_equal" if negation else "equal"
                relations.append((subj, rel_type, obj))
    
    # Pattern 2: "X has Y" (possession)
    has_indices = [i for i, (word, _) in enumerate(tagged) if word in ["has", "have", "owns", "possesses"]]
    for idx in has_indices:
        if idx > 0 and idx < len(tagged) - 1:
            subj_candidates = [(i, word) for i, (word, tag) in enumerate(tagged[:idx]) if tag.startswith('NN')]
            obj_candidates = [(i, word) for i, (word, tag) in enumerate(tagged[idx+1:], start=idx+1) if tag.startswith('NN')]
            
            if subj_candidates and obj_candidates:
                subj_idx, subj = max(subj_candidates, key=lambda x: x[0])
                obj_idx, obj = min(obj_candidates, key=lambda x: x[0])
                relations.append((subj, "has", obj))
    
    # Pattern 3: "All X are Y" (subset)
    all_indices = [i for i, (word, _) in enumerate(tagged) if word in ["all", "every"]]
    for idx in all_indices:
        if idx < len(tagged) - 3:  # Need at least 3 more tokens
            # Look for pattern: all/every + noun + is/are + noun
            if (idx+1 < len(tagged) and tagged[idx+1][1].startswith('NN') and 
                idx+2 < len(tagged) and tagged[idx+2][0] in ["is", "are"] and
                idx+3 < len(tagged) and tagged[idx+3][1].startswith('NN')):
                
                subj = tagged[idx+1][0]
                obj = tagged[idx+3][0]
                relations.append((subj, "subset_of", obj))
    
    # Pattern 4: "X is greater/less than Y" (comparison)
    for i in range(len(tagged) - 3):
        if (tagged[i][1].startswith('NN') and 
            tagged[i+1][0] in ["is", "are"] and
            tagged[i+2][0] in ["greater", "less", "bigger", "smaller"] and
            tagged[i+3][0] == "than" and
            i+4 < len(tagged) and tagged[i+4][1].startswith('NN')):
            
            subj = tagged[i][0]
            rel = f"{tagged[i+2][0]}_than"
            obj = tagged[i+4][0]
            relations.append((subj, rel, obj))
    
    return relations

def detect_negation_patterns(text):
    """
    Detect complex negation patterns in natural language.
    :param text: Input text to analyze
    :return: Dictionary with negation information
    """
    # Tokenize and tag the text
    tokens = word_tokenize(text.lower())
    tagged = pos_tag(tokens)
    
    # Initialize results
    result = {
        "has_negation": False,
        "negation_type": None,
        "negated_entity": None,
        "negated_predicate": None,
        "negated_relation": None
    }
    
    # Direct negation words
    negation_words = ["not", "no", "never", "none", "neither", "nor", "nothing", "nowhere"]
    
    # Negative verbs and contractions
    negative_verbs = ["isn't", "aren't", "wasn't", "weren't", "don't", "doesn't", 
                     "didn't", "won't", "wouldn't", "can't", "cannot", "couldn't"]
    
    # Check for direct negation words
    for i, (word, tag) in enumerate(tagged):
        if word in negation_words or word in negative_verbs:
            result["has_negation"] = True
            
            # Determine negation type and what's being negated
            if i > 0 and i < len(tagged) - 1:
                # Check if negating a predicate (verb/adjective)
                if tagged[i+1][1].startswith('VB') or tagged[i+1][1].startswith('JJ'):
                    result["negation_type"] = "predicate"
                    result["negated_predicate"] = tagged[i+1][0]
                    
                    # Look for the subject being negated
                    for j in range(i-1, -1, -1):
                        if tagged[j][1].startswith('NN'):
                            result["negated_entity"] = tagged[j][0]
                            break
                
                # Check if negating an entity (noun)
                elif tagged[i+1][1].startswith('NN'):
                    result["negation_type"] = "entity"
                    result["negated_entity"] = tagged[i+1][0]
                
                # Check for relation negation (X is not related to Y)
                elif i > 1 and i+2 < len(tagged):
                    if (tagged[i-2][1].startswith('NN') and 
                        tagged[i-1][0] in ["is", "are"] and
                        tagged[i+1][0] in ["related", "connected", "linked"] and
                        tagged[i+2][0] == "to" and
                        i+3 < len(tagged) and tagged[i+3][1].startswith('NN')):
                        
                        result["negation_type"] = "relation"
                        result["negated_relation"] = f"{tagged[i+1][0]}_to"
                        result["negated_entity"] = tagged[i-2][0]
                        result["negated_object"] = tagged[i+3][0]
    
    # Check for "neither X nor Y" pattern
    if "neither" in tokens and "nor" in tokens:
        neither_idx = tokens.index("neither")
        nor_idx = tokens.index("nor")
        
        if neither_idx < nor_idx and neither_idx + 1 < len(tokens) and nor_idx + 1 < len(tokens):
            result["has_negation"] = True
            result["negation_type"] = "conjunction"
            
            # Get entities being negated
            entity1 = None
            entity2 = None
            
            for i in range(neither_idx + 1, nor_idx):
                if tagged[i][1].startswith('NN'):
                    entity1 = tagged[i][0]
                    break
                    
            for i in range(nor_idx + 1, len(tokens)):
                if tagged[i][1].startswith('NN'):
                    entity2 = tagged[i][0]
                    break
            
            if entity1 and entity2:
                result["negated_entity"] = [entity1, entity2]
    
    return result

@mcp.tool
def solver(equation: str) -> dict:
    """Solve a Z3 equation and return the result."""
    try:
        result = solve_equation(equation)
        return {"message": str(result)}
    except Exception as e:
        print(f"Error in create_solver: {e}")
        traceback.print_exc()
        return {"message": f"Error: {str(e)}"}

@mcp.tool
def add_constraint(constraint: str) -> dict:
    """Add a constraint to the Z3 solver."""
    try:
        if not constraint:
            return {"message": "No constraint provided"}

        # Get or create the solver context
        if not solver_context['solver']:
            reset_solver_context()

        # Parse the constraint to extract variable names
        b = "-+/*=><1234567890, "
        cache = constraint
        for char in b:
            cache = cache.replace(char, "")
        single_cache = set(cache)

        # Create Z3 variables in the context
        for entry in single_cache:
            if entry not in solver_context['variables']:
                solver_context['variables'][entry] = Real(entry)

        # Add the constraint to the solver
        locals_dict = {**solver_context['variables']}
        solver_context['solver'].add(eval(constraint.strip(), globals(), locals_dict))
        solver_context['constraints'].append(constraint)

        return {
            "message": "Constraint added",
            "constraint": constraint,
            "constraints": solver_context['constraints']
        }
    except Exception as e:
        print(f"Error adding constraint: {e}")
        traceback.print_exc()
        return {"message": f"Error adding constraint: {str(e)}"}

@mcp.tool
def check_satisfiability() -> dict:
    """Check the satisfiability of the current constraints."""
    try:
        # Ensure we have a solver
        if not solver_context['solver']:
            return {"message": "No constraints have been added yet"}

        # Check satisfiability
        result = solver_context['solver'].check()

        if result == sat:
            model = solver_context['solver'].model()
            assignments = {}
            for var_name, var in solver_context['variables'].items():
                if var in model:
                    assignments[var_name] = str(model[var])

            return {
                "message": "Satisfiable",
                "model": assignments,
                "constraints": solver_context['constraints']
            }
        elif result == unsat:
            return {
                "message": "Unsatisfiable - no solution exists for the given constraints",
                "constraints": solver_context['constraints']
            }
        else:
            return {
                "message": "Unknown - Z3 could not determine satisfiability",
                "constraints": solver_context['constraints']
            }
    except Exception as e:
        print(f"Error checking satisfiability: {e}")
        traceback.print_exc()
        return {"message": f"Error checking satisfiability: {str(e)}"}

@mcp.tool
def reset_solver() -> dict:
    """Reset the Z3 solver context."""
    try:
        reset_solver_context()
        return {"message": "Solver context reset successfully"}
    except Exception as e:
        print(f"Error resetting solver: {e}")
        traceback.print_exc()
        return {"message": f"Error resetting solver: {str(e)}"}

@mcp.tool
def prove_theorem_tool(premises: list[str], conclusion: str) -> dict:
    """Prove a theorem given premises and a conclusion."""
    try:
        if not premises:
            return {"message": "No premises provided"}

        if not conclusion:
            return {"message": "No conclusion provided"}

        result = prove_theorem(premises, conclusion)
        return {"message": str(result)}
    except Exception as e:
        print(f"Error in theorem prover: {e}")
        traceback.print_exc()
        return {"message": f"Error proving theorem: {str(e)}"}

@mcp.tool
def convert_natural_language(premises: list[str], conclusion: str, use_lemmatization: bool = False) -> dict:
    """Convert natural language premises and conclusion to Z3 logic."""
    try:
        if not premises:
            return {"message": "No premises provided"}

        if not conclusion:
            return {"message": "No conclusion provided"}

        # Log the received data with lemmatization info
        print(f"Received natural language with lemmatization={use_lemmatization}")
        print(f"Premises: {premises}")
        print(f"Conclusion: {conclusion}")

        converted = natural_language_to_logic(premises, conclusion)
        return converted
    except Exception as e:
        print(f"Error converting natural language: {e}")
        traceback.print_exc()
        return {"message": f"Error converting natural language: {str(e)}"}

@mcp.tool
def get_status() -> dict:
    """Return the current status of the solver context."""
    try:
        constraints_count = len(solver_context['constraints'])
        variables_count = len(solver_context['variables'])

        return {
            "status": "active" if solver_context['solver'] else "inactive",
            "constraints_count": constraints_count,
            "variables_count": variables_count,
            "constraints": solver_context['constraints']
        }
    except Exception as e:
        print(f"Error getting status: {e}")
        traceback.print_exc()
        return {"message": f"Error getting status: {str(e)}"}

def _spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]

# --- check_relations_plausibility helpers -----------------------------------
#
# Extracted (subject, relation, object) triples are turned into Z3 Boolean
# predicates Relation(subject, object) over a shared uninterpreted Object
# sort, then checked for contradictions via other/math/math_plus_mcp.py's
# z3_run_script (loaded above as `_run_z3_script`). A small taxonomy of
# relation labels gets real Z3 semantics (equality, strict order,
# transitivity) instead of being independent, unrelated predicates - mirrors
# the taxonomy natural_language_to_logic() already uses above for the
# premises/conclusion theorem-proving workflow.

_RELATION_LABEL_ALIASES = {
    "equals": "equal", "is_equal_to": "equal", "same_as": "equal", "identical_to": "equal",
    "not_equal_to": "not_equal", "different_from": "not_equal", "not_same_as": "not_equal",
    "greater_than": "greater_than", "more_than": "greater_than", "bigger_than": "greater_than",
    "larger_than": "greater_than", "exceeds": "greater_than",
    "less_than": "less_than", "smaller_than": "less_than", "fewer_than": "less_than",
    "subset_of": "subset_of", "part_of": "subset_of", "contained_in": "subset_of",
}
# (label_a, label_b) pairs that are irreflexive, asymmetric, transitive, and
# mutually exclusive with each other - strict orderings.
_STRICT_ORDER_PAIRS = (("greater_than", "less_than"), ("before", "after"))
# Labels that are transitive but not a strict order (e.g. subset_of is
# reflexive: SubsetOf(x, x) is true, not forbidden).
_TRANSITIVE_ONLY_LABELS = ("subset_of",)
# Minimal default antonym set for the generic (non-taxonomy) predicates;
# callers should pass `antonym_pairs` for domain-specific mutual exclusivity
# (e.g. ["alive", "dead"]) since open-domain relation labels have no general
# way to know their own antonyms.
_DEFAULT_ANTONYM_PAIRS = (("true", "false"),)


def _canonical_relation_label(text: str) -> str:
    """Best-effort normalization of a free-text relation label (e.g. ReLiK/
    GLiREL open relation extraction output) onto the small taxonomy above.
    Anything that doesn't match keeps its own normalized form as an
    independent uninterpreted predicate - this is a heuristic alias table,
    not general relation-label synonymy resolution."""
    normalized = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return _RELATION_LABEL_ALIASES.get(normalized, normalized)


def _build_plausibility_script(
    relations: list[dict],
    antonym_pairs: list[tuple[str, str]],
) -> tuple[list[str], dict[int, str]]:
    """Build a z3_run_script statement list asserting each relation as a
    tracked Boolean fact, plus axioms for the taxonomy/antonym labels that
    actually appear. Returns (statements, {relation_index: tracked_literal}).
    """
    statements = [
        "Object = DeclareSort('Object')",
        "solver = Solver()",
        "__x = Const('__x', Object)",
        "__y = Const('__y', Object)",
        "__z = Const('__z', Object)",
    ]
    entity_var: dict[str, str] = {}
    relation_fn_var: dict[str, str] = {}
    canonical_present: set[str] = set()
    tracked: dict[int, str] = {}
    fact_statements: list[str] = []

    def entity(text: str) -> str:
        key = text.strip().lower()
        if key not in entity_var:
            entity_var[key] = f"e{len(entity_var)}"
            statements.append(f"{entity_var[key]} = Const({text!r}, Object)")
        return entity_var[key]

    def relation_fn(label: str) -> str:
        if label not in relation_fn_var:
            relation_fn_var[label] = f"R{len(relation_fn_var)}"
            statements.append(f"{relation_fn_var[label]} = Function({label!r}, Object, Object, BoolSort())")
        return relation_fn_var[label]

    for index, rel in enumerate(relations):
        subject = str(rel.get("subject", "")).strip()
        obj = str(rel.get("object", "")).strip()
        label = str(rel.get("relation", "")).strip()
        if not subject or not obj or not label:
            continue

        canon = _canonical_relation_label(label)
        canonical_present.add(canon)
        subj_var, obj_var = entity(subject), entity(obj)
        literal_name = f"rel_{index}"
        tracked[index] = literal_name

        if canon == "equal":
            fact_statements.append(f"solver.assert_and_track({subj_var} == {obj_var}, {literal_name!r})")
        elif canon == "not_equal":
            fact_statements.append(f"solver.assert_and_track({subj_var} != {obj_var}, {literal_name!r})")
        else:
            fn_var = relation_fn(canon)
            fact_statements.append(f"solver.assert_and_track({fn_var}({subj_var}, {obj_var}), {literal_name!r})")

    for label_a, label_b in _STRICT_ORDER_PAIRS:
        for label in (label_a, label_b):
            if label in canonical_present:
                fn_var = relation_fn(label)
                statements.append(f"solver.add(ForAll([__x], Not({fn_var}(__x, __x))))")
                statements.append(
                    f"solver.add(ForAll([__x, __y], Implies({fn_var}(__x, __y), Not({fn_var}(__y, __x)))))"
                )
                statements.append(
                    f"solver.add(ForAll([__x, __y, __z], "
                    f"Implies(And({fn_var}(__x, __y), {fn_var}(__y, __z)), {fn_var}(__x, __z))))"
                )
        if label_a in canonical_present and label_b in canonical_present:
            fn_a, fn_b = relation_fn(label_a), relation_fn(label_b)
            statements.append(f"solver.add(ForAll([__x, __y], Not(And({fn_a}(__x, __y), {fn_b}(__x, __y)))))")

    for label in _TRANSITIVE_ONLY_LABELS:
        if label in canonical_present:
            fn_var = relation_fn(label)
            statements.append(
                f"solver.add(ForAll([__x, __y, __z], "
                f"Implies(And({fn_var}(__x, __y), {fn_var}(__y, __z)), {fn_var}(__x, __z))))"
            )

    for label_a, label_b in (*_DEFAULT_ANTONYM_PAIRS, *antonym_pairs):
        canon_a, canon_b = _canonical_relation_label(label_a), _canonical_relation_label(label_b)
        if (
            canon_a in canonical_present and canon_b in canonical_present
            and canon_a not in ("equal", "not_equal") and canon_b not in ("equal", "not_equal")
        ):
            fn_a, fn_b = relation_fn(canon_a), relation_fn(canon_b)
            statements.append(f"solver.add(ForAll([__x, __y], Not(And({fn_a}(__x, __y), {fn_b}(__x, __y)))))")

    statements.extend(fact_statements)
    return statements, tracked


def _tool_fn(tool):
    """Underlying plain callable for an `@mcp.tool`-decorated function - see
    math_plus_mcp._tool_fn's docstring for why `.fn` may or may not exist."""
    return getattr(tool, "fn", tool)


# --- kb_* / verify_answer / explain_conflict helpers -------------------------
#
# The knowledge base is the separately-running mcp-memory server
# (other/mcp_memory), reached over MCP like any other client would - NOT an
# in-process import like math_plus_mcp. mcp-memory owns its own MongoDB
# connection, embeddings, and request lifecycle; importing its server module
# here would start a second instance of all of that instead of talking to
# the one already deployed (its own run_server() defaults to
# http://10.0.0.10:8082/memory, overridable below).
#
# This is the lightweight stand-in for base Extension A's persistent,
# belief-revising knowledge base: mcp-memory gives us durable storage with a
# soft-delete flag, but no fact versioning, no functional-key supersession,
# and (per other/mcp_memory/schemas.py's EventPatch/EventRecord/Snippet
# models) no metadata round-trip through its `retrieve` tool - only
# `text`/`stichwort` survive the trip. So the full structured fact record is
# encoded as a JSON comment appended to `text` and decoded back out of it,
# rather than relying on `metadata`.

_MCP_MEMORY_URL = os.getenv(
    "MCP_MEMORY_URL",
    f"http://{os.getenv('MCP_MEMORY_HOST', '10.0.0.10')}:{os.getenv('MCP_MEMORY_PORT', '8082')}/memory",
)
_KB_MARKER_RE = re.compile(r"<!--kb:(.*?)-->", re.DOTALL)


def _call_memory_tool(name: str, arguments: dict) -> dict:
    """Call a tool on the mcp-memory server and return its structured result."""
    async def _run():
        async with _MCPClient(_MCP_MEMORY_URL) as client:
            result = await client.call_tool(name, arguments)
            return result.data if result.data is not None else (result.structured_content or {})
    return asyncio.run(_run())


def _encode_kb_fact(subject, relation, canon, obj, confidence, source, verdict, extra=None):
    payload = {
        "subject": subject,
        "relation": relation,
        "canonical_relation": canon,
        "object": obj,
        "confidence": confidence,
        "source": source,
        "verdict": verdict,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    sentence = f"{subject} {relation.replace('_', ' ')} {obj}."
    text = sentence + "\n<!--kb:" + json.dumps(payload, ensure_ascii=False) + "-->"
    return text, payload


def _decode_kb_fact(text: str) -> dict | None:
    match = _KB_MARKER_RE.search(text or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except (json.JSONDecodeError, TypeError):
        return None

@mcp.tool
def extract_relations_tool(
    sentence: str,
    locale: str = "en",
    relation_labels: list[str] | None = None,
    threshold: float | None = None,
) -> dict:
    """
    Extract structured facts from text via the layered pipeline (plan.md §33):
    L0 structure normalization (Markdown/table/list/code handling), L3
    deterministic entities, L4 quantity intervals, and L5 neural relation
    extraction - ReLiK (end-to-end, NYT relation inventory) plus GLiREL
    (zero-shot over spaCy/ReLiK/L3 entities and noun chunks). The L5 triples
    are the primary result ("relations"); the legacy spaCy/NLTK
    subject-verb-object pass only fills in ("legacy_relations") for
    propositions where L5 is unavailable or finds nothing.

    :param locale: "en" or "de" - controls number-format parsing in L4
        (§24: "1.000" means 1000 in German, 1.0 in English).
    :param relation_labels: zero-shot relation labels for GLiREL (e.g.
        ["controls", "part of", "located in"]); omit for the default set.
    :param threshold: GLiREL score cutoff (default 0.5, env GLIREL_THRESHOLD).
    """
    try:
        if not sentence:
            return {"message": "No sentence provided"}

        print(f"Extracting relations from: '{sentence}'")

        doc = l0_normalize(sentence)

        re_props = [p for p in doc.propositions if p.kind != "parenthetical"]
        prop_entities = [find_entities(p.text) for p in doc.propositions]
        re_entities = [e for p, e in zip(doc.propositions, prop_entities) if p.kind != "parenthetical"]
        try:
            neural = l5_relations.extract(
                [p.text for p in re_props], re_entities,
                labels=relation_labels, threshold=threshold,
            )
        except Exception as e:
            print(f"L5 relation extraction failed, using legacy SVO: {e}")
            traceback.print_exc()
            neural = None
        neural_by_prop = dict(zip(map(id, re_props), neural)) if neural is not None else {}

        propositions = []
        relations = []
        legacy_relations = []
        for index, (prop, entities) in enumerate(zip(doc.propositions, prop_entities)):
            quantities = find_quantities(prop.text, locale=locale)
            # L3 identifiers (article numbers, versions, IPs...) are more
            # specific than a generic numeric range/point guess, so an
            # entity span wins over an overlapping quantity span - e.g. the
            # article number "750-8212" must not also read as a numeric
            # range 750-8212 (§23's "regex span wins" conflict rule, applied
            # across layers since L4 has no identifier awareness of its own).
            quantities = [
                q for q in quantities
                if not any(_spans_overlap((q.start, q.end), (e.start, e.end)) for e in entities)
            ]
            compounds = resolve_compound_attributes(prop.text)

            prop_relations = [r.as_dict() for r in neural_by_prop.get(id(prop), [])]
            for r in prop_relations:
                relations.append({**r, "proposition_index": index})

            propositions.append({
                "text": prop.text,
                "span": list(prop.span),
                "kind": prop.kind,
                "context_entity": prop.context_entity,
                "parent_index": prop.parent_index,
                "entities": [
                    {"text": e.text, "label": e.label, "span": [e.start, e.end]}
                    for e in entities
                ],
                "quantities": [
                    {"text": q.text, "lo": q.lo, "hi": q.hi, "unit": q.unit,
                     "form": q.form, "confidence": q.confidence, "ambiguous": q.ambiguous}
                    for q in quantities
                ],
                "compound_attributes": [
                    {"entity": ent, "predicate": pred} for ent, pred in compounds
                ],
                "relations": prop_relations,
            })

            if prop.kind != "parenthetical" and not prop_relations:
                for subj, rel, obj in extract_relations(prop.text):
                    legacy_relations.append({"subject": subj, "relation": rel, "object": obj,
                                             "proposition_index": index})

        legacy_method = "spaCy" if is_linux() and SPACY_AVAILABLE else "NLTK"
        re_status = l5_relations.status()
        neural_method = "+".join(
            name for name, loaded in (("ReLiK", re_status["relik_loaded"]),
                                      ("GLiREL", re_status["glirel_loaded"])) if loaded
        )
        if neural_method and legacy_relations:
            method = f"{neural_method} (legacy {legacy_method} fallback for some propositions)"
        elif neural_method:
            method = neural_method
        else:
            method = f"{legacy_method} (L5 unavailable: {re_status['errors'] or 'not loaded'})"
        print(f"Method used: {method}")
        print(f"Found {len(propositions)} proposition(s), {len(doc.facts)} table fact(s), "
              f"{len(relations)} L5 relation(s), {len(legacy_relations)} legacy relation(s)")

        return {
            "method": method,
            "relations": relations,
            "propositions": propositions,
            "table_facts": [
                {"subject": f.subject, "predicate": f.predicate, "value": f.value,
                 "source": f.source, "span": list(f.span)}
                for f in doc.facts
            ],
            "code_blocks": [
                {"content": content, "span": list(span)} for content, span in doc.code_blocks
            ],
            "placeholders": doc.placeholders,
            "legacy_relations": legacy_relations,
            "sentence": sentence,
        }
    except Exception as e:
        print(f"Error extracting relations: {e}")
        traceback.print_exc()
        return {"message": f"Error extracting relations: {str(e)}"}

@mcp.tool
def check_relations_plausibility(
    relations: list[dict],
    antonym_pairs: list[list[str]] | None = None,
) -> dict:
    """
    Check extracted relation triples - e.g. the "relations"/"legacy_relations"
    lists from extract_relations_tool - for logical contradictions using Z3,
    reusing other/math/math_plus_mcp.py's z3_run_script in-process (no
    network hop between the two MCP servers).

    Each {"subject", "relation", "object"} triple becomes a Boolean predicate
    Relation(subject, object) over a shared Object sort; entities with the
    same text (case-insensitive) share one constant - there is no
    coreference resolution beyond that. A small taxonomy of relation labels
    gets real Z3 semantics instead of being independent uninterpreted
    predicates:
      - "equal" / "not_equal" -> Object-sort equality/inequality.
      - "greater_than" / "less_than", "before" / "after" -> irreflexive,
        asymmetric, transitive, and mutually exclusive with their
        counterpart.
      - "subset_of" -> transitive.
    Labels are matched after light normalization (lowercase, common synonyms
    like "more_than" -> "greater_than"); anything else keeps its own
    predicate, so most open-domain relation labels (e.g. ReLiK/GLiREL output
    like "ceo of", "located in") are only caught as contradictory if the
    exact same predicate is both asserted and negated (via equal/not_equal),
    or if you supply `antonym_pairs`.

    :param relations: list of {"subject": str, "relation": str, "object":
        str, ...}; extra keys (score, proposition_index, sources, ...) are
        ignored. Entries missing subject, relation, or object are skipped.
    :param antonym_pairs: extra [labelA, labelB] pairs (beyond the built-in
        taxonomy and a tiny ["true", "false"] default) that can never both
        hold for the same (subject, object) - e.g. domain knowledge like
        ["alive", "dead"] or ["part_of", "disjoint_from"].
    """
    if _run_z3_script is None:
        return {"message": f"math_plus_mcp unavailable: {_math_plus_mcp_error}"}

    if not relations:
        return {"message": "No relations provided"}

    try:
        pairs = [(str(a), str(b)) for a, b in (antonym_pairs or [])]
        statements, tracked = _build_plausibility_script(relations, pairs)

        if not tracked:
            return {"message": "No relations had both a subject, relation, and object to check"}

        result = _run_z3_script(statements)
        if not result.get("ok"):
            return {
                "message": f"Z3 script failed: {result.get('reason', 'unknown error')}",
                "z3_script": statements,
            }

        value = result.get("value", {})
        status = value.get("status")
        skipped_relations = [i for i in range(len(relations)) if i not in tracked]

        if status == "unsat":
            core = set(value.get("unsat_core", []))
            contradicting_indices = sorted(
                index for index, literal in tracked.items() if literal in core
            ) or sorted(tracked)  # empty core (no assumptions tracked) -> report all as implicated
            return {
                "status": "contradiction",
                "contradicting_relations": [relations[i] for i in contradicting_indices],
                "skipped_relations": skipped_relations,
            }

        if status == "sat":
            return {
                "status": "consistent",
                "checked_relations": len(tracked),
                "skipped_relations": skipped_relations,
            }

        return {
            "status": "unknown",
            "message": "Z3 could not determine consistency (status 'unknown').",
            "skipped_relations": skipped_relations,
        }
    except Exception as e:
        print(f"Error checking relation plausibility: {e}")
        traceback.print_exc()
        return {"message": f"Error checking relation plausibility: {str(e)}"}

@mcp.tool
def explain_conflict(
    relations: list[dict],
    antonym_pairs: list[list[str]] | None = None,
) -> dict:
    """
    Classify why a relation set is contradictory and surface the source
    spans involved, instead of just check_relations_plausibility's keep/drop
    verdict. Re-runs that same Z3 check internally.

    `type` is a best-effort classification of the taxonomy rule that fired,
    not a literal trace of the Z3 proof:
      - "direct_negation": the contradicting set is exactly an equal/
        not_equal pair on the same (subject, object).
      - "antonym_pair": the contradicting set's canonical labels match a
        built-in or caller-supplied antonym pair (and aren't equal/not_equal).
      - "strict_order_violation": every contradicting relation shares one
        canonical label from the greater_than/less_than/before/after/
        subset_of taxonomy (irreflexivity, asymmetry, or transitivity
        broken - e.g. a greater_than cycle).
      - "unclassified": Z3 found it unsat, but the contradicting set doesn't
        match any of the above patterns.
    `source_spans` passes through whatever span info each relation dict
    already carries (`subject_span`/`object_span` from L5, or
    `proposition_index` from extract_relations_tool) - fields that aren't
    present are simply omitted, since legacy_relations has no spans.

    :param relations: same shape as check_relations_plausibility's input.
    :param antonym_pairs: same as check_relations_plausibility.
    """
    try:
        result = _tool_fn(check_relations_plausibility)(relations, antonym_pairs)
        if result.get("status") != "contradiction":
            return {"status": result.get("status"), "conflicts": [], "detail": result}

        contradicting = result["contradicting_relations"]
        canon_labels = sorted({_canonical_relation_label(str(r.get("relation", ""))) for r in contradicting})
        label_set = frozenset(canon_labels)

        antonym_set = {frozenset(("equal", "not_equal"))}
        antonym_set.update(frozenset((a, b)) for a, b in _STRICT_ORDER_PAIRS)
        antonym_set.update(
            frozenset((_canonical_relation_label(a), _canonical_relation_label(b)))
            for a, b in (antonym_pairs or [])
        )
        order_labels = {a for a, _ in _STRICT_ORDER_PAIRS} | {b for _, b in _STRICT_ORDER_PAIRS}
        order_labels |= set(_TRANSITIVE_ONLY_LABELS)

        if label_set == frozenset(("equal", "not_equal")):
            conflict_type = "direct_negation"
        elif label_set in antonym_set:
            conflict_type = "antonym_pair"
        elif len(canon_labels) == 1 and canon_labels[0] in order_labels:
            conflict_type = "strict_order_violation"
        else:
            conflict_type = "unclassified"

        source_spans = [
            {
                "subject": r.get("subject"),
                "relation": r.get("relation"),
                "object": r.get("object"),
                **{k: r[k] for k in ("subject_span", "object_span", "proposition_index") if k in r},
            }
            for r in contradicting
        ]

        return {
            "status": "contradiction",
            "conflicts": [{
                "type": conflict_type,
                "canonical_labels": canon_labels,
                "relations": contradicting,
                "source_spans": source_spans,
            }],
            "skipped_relations": result.get("skipped_relations", []),
        }
    except Exception as e:
        print(f"Error explaining conflict: {e}")
        traceback.print_exc()
        return {"message": f"Error explaining conflict: {str(e)}"}

@mcp.tool
def relation_models_status(load: bool = False) -> dict:
    """Status of the L5 relation-extraction models (ReLiK, GLiREL): which are
    loaded, load errors, model ids and device. With load=True, load them now
    (blocking) instead of waiting for the first extraction request."""
    return l5_relations.load_models() if load else l5_relations.status()

@mcp.tool
def gold_corpus_status() -> dict:
    """Coverage of the plan.md §30 edge-case categories in the seed gold
    corpus (plan.md §33 P1 exit criterion: >= 10 examples per category).
    The seed corpus only has illustrative examples, not the full annotated
    set - this reports exactly how far it still is from that criterion."""
    return {
        "counts": gold_coverage_report(),
        "still_needed": gold_missing_coverage(),
        "min_examples_per_category": 10,
    }

@mcp.tool
def analyze_subjectivity(text: str, use_ml_classifier: bool = False, include_sentences: bool = True) -> dict:
    """
    Analyze text for objectivity vs. subjectivity and emotional tone.

    Uses POS/lexicon-based heuristics plus NLTK's VADER sentiment analyzer to determine
    how subjective, opinionated, or emotional a piece of text is, per sentence and overall.

    :param text: The text to analyze (one or more sentences).
    :param use_ml_classifier: If True, also run a Naive Bayes classifier trained on NLTK's
        subjectivity corpus for a second opinion (slower on first call, best-effort).
    :param include_sentences: If True, include a per-sentence breakdown in the response.
    """
    try:
        if not text or not text.strip():
            return {"message": "No text provided"}

        return analyze_text_subjectivity(
            text,
            use_ml_classifier=use_ml_classifier,
            include_sentences=include_sentences,
        )
    except Exception as e:
        print(f"Error analyzing subjectivity: {e}")
        traceback.print_exc()
        return {"message": f"Error analyzing subjectivity: {str(e)}"}

@mcp.tool
def kb_add(
    subject: str,
    relation: str,
    object: str,
    confidence: float = 1.0,
    source: str = "unspecified",
    user_id: str = "default",
) -> dict:
    """
    Persist a (subject, relation, object) fact in the long-term knowledge
    base (the mcp-memory server) so it outlives this single response and
    can be cross-checked against in later turns.

    This is the lightweight stand-in for base Extension A's full belief-
    revision knowledge base: it stores the triple plus a verdict field
    ("asserted") but has no fact versioning or functional-key supersession,
    and no cross-source trust weighting (Extension B) - `source` is stored
    as-is, not weighted. kb_retract marks a fact inactive rather than
    deleting it, so past verdicts stay reproducible.

    :param subject/relation/object: the triple to store, as produced by
        extract_relations_tool / check_relations_plausibility.
    :param confidence: extraction/verification confidence in [0, 1].
    :param source: provenance tag, e.g. "user", "retrieved_document",
        "model_output" (see Extension B's source-trust classes - no trust
        weighting is applied yet, it's just recorded).
    :param user_id: mcp-memory tenant/user scope.
    """
    if not subject.strip() or not relation.strip() or not str(object).strip():
        return {"message": "subject, relation, and object must all be non-empty"}

    canon = _canonical_relation_label(relation)
    text, payload = _encode_kb_fact(subject, relation, canon, object, confidence, source, "asserted")
    stichwort = f"{subject} {relation} {object}"[:128]
    try:
        result = _call_memory_tool("remember", {
            "text": text,
            "stichwort": stichwort,
            "user_id": user_id,
            "type": "kb_fact",
            "source": source,
            "metadata": payload,
        })
    except Exception as e:
        return {"message": f"Error reaching mcp-memory at {_MCP_MEMORY_URL}: {e}"}

    return {"event_id": result.get("id"), "fact": payload, "memory_response": result}

@mcp.tool
def kb_query(
    subject: str | None = None,
    relation: str | None = None,
    object: str | None = None,
    query: str | None = None,
    include_retracted: bool = False,
    k: int = 20,
    user_id: str = "default",
) -> dict:
    """
    Query stored knowledge-base facts. Runs a semantic `retrieve` against
    mcp-memory, then filters exactly on subject/relation(canonicalized)/
    object (case-insensitive) client-side - mcp-memory's retrieve ranking is
    fuzzy/embedding-based, so results are over-fetched before the exact
    filter is applied.

    :param query: free-text semantic search instead of (or alongside) exact
        subject/relation/object fields.
    :param include_retracted: also return facts kb_retract marked inactive.
    """
    search_text = query or " ".join(str(p) for p in (subject, relation, object) if p) or "fact"
    try:
        result = _call_memory_tool("retrieve", {
            "query": search_text,
            "k": max(k, 20),  # over-fetch: exact filtering below discards fuzzy non-matches
            "filters": {"user_id": user_id, "types": ["kb_fact"], "include_deleted": include_retracted},
            "min_score": 0.0,
        })
    except Exception as e:
        return {"message": f"Error reaching mcp-memory at {_MCP_MEMORY_URL}: {e}"}

    canon_relation = _canonical_relation_label(relation) if relation else None
    facts = []
    for snippet in result.get("snippets", []):
        decoded = _decode_kb_fact(snippet.get("text", ""))
        if decoded is None:
            continue
        if subject and decoded.get("subject", "").strip().lower() != subject.strip().lower():
            continue
        if canon_relation and decoded.get("canonical_relation") != canon_relation:
            continue
        if object and str(decoded.get("object", "")).strip().lower() != str(object).strip().lower():
            continue
        if not include_retracted and decoded.get("verdict") == "retracted":
            continue
        decoded["event_id"] = snippet.get("event_id")
        decoded["score"] = snippet.get("score")
        facts.append(decoded)
        if len(facts) >= k:
            break

    return {"facts": facts, "count": len(facts)}

@mcp.tool
def kb_retract(
    event_id: int,
    subject: str,
    relation: str,
    object: str,
    reason: str | None = None,
    confidence: float | None = None,
    source: str | None = None,
    user_id: str = "default",
) -> dict:
    """
    Mark a kb_add-ed fact inactive instead of deleting it, so past verdicts
    that relied on it stay reproducible (base Extension A).

    mcp-memory has no "get fact by id" tool and its EventPatch schema
    (other/mcp_memory/schemas.py) has no metadata field - only `text`
    round-trips - so there is no way to look up and rewrite the stored
    triple from `event_id` alone. The triple being retracted must be
    supplied here; callers always have it already, since it came from the
    kb_add or kb_query call that produced this `event_id`. `confidence`/
    `source` are optional purely to preserve the original fact's values in
    the rewritten record if the caller has them.

    Implemented as an mcp-memory `update`: rewrites the fact's encoded text
    with verdict="retracted" plus a timestamp/reason, and soft-deletes the
    record (deleted=true) so kb_query skips it by default - pass
    include_retracted=true there to see it again.
    """
    canon = _canonical_relation_label(relation)
    text, payload = _encode_kb_fact(
        subject, relation, canon, object,
        confidence=confidence, source=source, verdict="retracted",
        extra={"reason": reason} if reason else None,
    )
    try:
        result = _call_memory_tool("update", {
            "event_id": event_id,
            "user_id": user_id,
            "patch": {"text": text, "deleted": True},
        })
    except Exception as e:
        return {"message": f"Error reaching mcp-memory at {_MCP_MEMORY_URL}: {e}"}

    return {"event_id": event_id, "status": "retracted", "fact": payload, "memory_response": result}

@mcp.tool
def ontology_status(relations: list[dict] | None = None) -> dict:
    """
    Report which domain pack(s) are loaded and, if a sample of relations is
    passed, what fraction of their labels that pack has an opinion about.

    Exactly one pack exists today: the built-in ontology.py (plan.md
    §5/§23) - Extension I's loadable per-request domain packs aren't
    implemented, so this always reports that single pack.

    Two different "coverage" numbers are reported:
      - `taxonomy_coverage`: fraction of ontology.PREDICATES that
        check_relations_plausibility's small taxonomy gives real Z3
        semantics (equal/strict-order/transitive) instead of treating as an
        independent uninterpreted predicate.
      - `relation_coverage` (only if `relations` is passed): fraction of the
        given relations' labels that match an ontology predicate, an
        attribute-lexicon entry, or the plausibility taxonomy.
    """
    try:
        import ontology as _ontology
    except Exception as e:
        return {"message": f"ontology.py unavailable: {e}"}

    taxonomy_labels = (
        set(_RELATION_LABEL_ALIASES) | set(_RELATION_LABEL_ALIASES.values())
        | {a for a, _ in _STRICT_ORDER_PAIRS} | {b for _, b in _STRICT_ORDER_PAIRS}
        | set(_TRANSITIVE_ONLY_LABELS)
    )
    ontology_predicates = set(_ontology.PREDICATES)
    predicates_with_z3_semantics = sorted(ontology_predicates & taxonomy_labels)

    pack = {
        "name": "ontology_v1 (builtin)",
        "classes": list(_ontology.CLASSES),
        "predicate_count": len(ontology_predicates),
        "attribute_lexicon_count": len(_ontology.ATTRIBUTE_LEXICON),
        "predicates_with_z3_semantics": predicates_with_z3_semantics,
        "taxonomy_coverage": (
            round(len(predicates_with_z3_semantics) / len(ontology_predicates), 4)
            if ontology_predicates else 0.0
        ),
    }
    response = {"packs": [pack]}
    if relations is None:
        return response

    covered, uncovered_labels = 0, []
    for rel in relations:
        label = str(rel.get("relation", "")).strip().lower()
        if not label:
            continue
        canon = _canonical_relation_label(label)
        head = label.split()[-1]
        if canon in ontology_predicates or canon in taxonomy_labels or _ontology.resolve_attribute(head):
            covered += 1
        else:
            uncovered_labels.append(label)

    total = covered + len(uncovered_labels)
    response["relation_coverage"] = {
        "total": total,
        "covered": covered,
        "coverage_ratio": round(covered / total, 4) if total else None,
        "uncovered_labels": sorted(set(uncovered_labels)),
    }
    return response

@mcp.tool
def verify_answer(
    text: str,
    locale: str = "en",
    check_against_kb: bool = False,
    user_id: str = "default",
    antonym_pairs: list[list[str]] | None = None,
) -> dict:
    """
    End-to-end verification loop for a single model answer, for the Open
    WebUI side to call as one tool instead of orchestrating several:
    extract relations (extract_relations_tool), check them for internal
    contradictions (check_relations_plausibility), and optionally cross-
    check each relation against stored knowledge-base facts (kb_query) for
    contradictions with earlier turns.

    This is a thin orchestrator, not base [9]'s full tiered MaxSAT verifier
    loop - there is no weighted drop-set or trust-weighted scoring here,
    just the same Z3 SAT/UNSAT check_relations_plausibility already does,
    plus an exact-match KB lookup.

    :param check_against_kb: if true, kb_query each extracted relation's
        (subject, relation) and flag any stored, non-retracted fact whose
        object differs from the one just extracted.
    """
    try:
        extraction = _tool_fn(extract_relations_tool)(text, locale=locale)
        if "relations" not in extraction:
            return {"status": "error", "extraction": extraction}

        all_relations = list(extraction.get("relations", [])) + list(extraction.get("legacy_relations", []))
        if all_relations:
            plausibility = _tool_fn(check_relations_plausibility)(all_relations, antonym_pairs)
        else:
            plausibility = {"status": "consistent", "checked_relations": 0, "skipped_relations": []}

        cross_turn_conflicts = []
        if check_against_kb:
            for rel in all_relations:
                subject, relation, obj = rel.get("subject"), rel.get("relation"), rel.get("object")
                if not (subject and relation and obj):
                    continue
                kb_result = _tool_fn(kb_query)(subject=subject, relation=relation, k=5, user_id=user_id)
                for fact in kb_result.get("facts", []):
                    if str(fact.get("object", "")).strip().lower() != str(obj).strip().lower():
                        cross_turn_conflicts.append({"claimed": rel, "stored_fact": fact})

        verdict = (
            "contradiction" if plausibility.get("status") == "contradiction" or cross_turn_conflicts
            else plausibility.get("status", "unknown")
        )
        return {
            "verdict": verdict,
            "extraction": extraction,
            "plausibility": plausibility,
            "cross_turn_conflicts": cross_turn_conflicts,
        }
    except Exception as e:
        print(f"Error verifying answer: {e}")
        traceback.print_exc()
        return {"message": f"Error verifying answer: {str(e)}"}

def run_server(transport: str | None = None) -> None:
    """Start the FastMCP server using the selected transport."""
    selected_transport = transport or os.getenv("Z3_BACKEND_TRANSPORT", "streamable-http")
    if selected_transport in {"streamable-http", "http"}:
        mcp.run(transport="http", path=SERVER_PATH, host=SERVER_HOST, port=SERVER_PORT)
    else:
        mcp.run(transport=selected_transport)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Z3 backend MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http"],
        default=os.getenv("Z3_BACKEND_TRANSPORT", "streamable-http"),
        help="Transport to use for FastMCP (default: streamable-http)",
    )
    args = parser.parse_args(argv)
    # Warm the L5 models in the background so the first extraction request
    # doesn't block on loading two DeBERTa-large encoders.
    if os.getenv("RE_PRELOAD", "1") != "0":
        l5_relations.preload_async()
    run_server(args.transport)


if __name__ == '__main__':
    main()
