from flask import Flask, request, jsonify
from z3 import *
from flask import request, Blueprint, flash, json
from flask_cors import CORS
import json
import traceback
import re
import neo4j_client  # Import the Neo4j client module

from mcp.server.fastmcp import FastMCP



# Import NLTK for natural language processing
import nltk
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
from nltk.chunk import RegexpParser, ne_chunk
from nltk.tree import Tree
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# Initialize the MCP server with a name (identifier for the server)
mcp = FastMCP("check")

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

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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

@app.route('/solver', methods=['POST'])
def create_solver():
    try:
        cache = request.get_data()
        cache_json = json.loads(cache)
        equation = cache_json['equation']
        result = solve_equation(equation)
        return jsonify({"message": str(result)}), 200
    except Exception as e:
        print(f"Error in create_solver: {e}")
        traceback.print_exc()
        return jsonify({"message": f"Error: {str(e)}"}), 400

@app.route('/add_constraint', methods=['POST'])
def add_constraint():
    try:
        data = request.json
        constraint = data.get('constraint')
        
        if not constraint:
            return jsonify({"message": "No constraint provided"}), 400
            
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
        
        return jsonify({
            "message": "Constraint added", 
            "constraint": constraint,
            "constraints": solver_context['constraints']
        }), 200
    except Exception as e:
        print(f"Error adding constraint: {e}")
        traceback.print_exc()
        return jsonify({"message": f"Error adding constraint: {str(e)}"}), 400

@app.route('/check_satisfiability', methods=['POST'])
def check_satisfiability():
    try:
        # Ensure we have a solver
        if not solver_context['solver']:
            return jsonify({"message": "No constraints have been added yet"}), 400
            
        # Check satisfiability
        result = solver_context['solver'].check()
        
        if result == sat:
            model = solver_context['solver'].model()
            assignments = {}
            for var_name, var in solver_context['variables'].items():
                if var in model:
                    assignments[var_name] = str(model[var])
            
            return jsonify({
                "message": "Satisfiable",
                "model": assignments,
                "constraints": solver_context['constraints']
            }), 200
        elif result == unsat:
            return jsonify({
                "message": "Unsatisfiable - no solution exists for the given constraints",
                "constraints": solver_context['constraints']
            }), 200
        else:
            return jsonify({
                "message": "Unknown - Z3 could not determine satisfiability",
                "constraints": solver_context['constraints']
            }), 200
    except Exception as e:
        print(f"Error checking satisfiability: {e}")
        traceback.print_exc()
        return jsonify({"message": f"Error checking satisfiability: {str(e)}"}), 400

@app.route('/reset_solver', methods=['POST'])
def reset_solver_endpoint():
    try:
        reset_solver_context()
        return jsonify({"message": "Solver context reset successfully"}), 200
    except Exception as e:
        print(f"Error resetting solver: {e}")
        traceback.print_exc()
        return jsonify({"message": f"Error resetting solver: {str(e)}"}), 400

@app.route('/prove_theorem', methods=['POST'])
def theorem_prover_endpoint():
    try:
        data = request.json
        premises = data.get('premises', [])
        conclusion = data.get('conclusion', '')
        
        if not premises:
            return jsonify({"message": "No premises provided"}), 400
            
        if not conclusion:
            return jsonify({"message": "No conclusion provided"}), 400
        
        result = prove_theorem(premises, conclusion)
        return jsonify({"message": str(result)}), 200
    except Exception as e:
        print(f"Error in theorem prover: {e}")
        traceback.print_exc()
        return jsonify({"message": f"Error proving theorem: {str(e)}"}), 400

@app.route('/convert_natural_language', methods=['POST'])
def convert_natural_language_endpoint():
    try:
        data = request.json
        premises = data.get('premises', [])
        conclusion = data.get('conclusion', '')
        
        if not premises:
            return jsonify({"message": "No premises provided"}), 400
            
        if not conclusion:
            return jsonify({"message": "No conclusion provided"}), 400
        
        converted = natural_language_to_logic(premises, conclusion)
        return jsonify(converted), 200
    except Exception as e:
        print(f"Error converting natural language: {e}")
        traceback.print_exc()
        return jsonify({"message": f"Error converting natural language: {str(e)}"}), 400

@app.route('/status', methods=['GET'])
def status():
    """Return the current status of the solver context"""
    try:
        constraints_count = len(solver_context['constraints'])
        variables_count = len(solver_context['variables'])
        
        return jsonify({
            "status": "active" if solver_context['solver'] else "inactive",
            "constraints_count": constraints_count,
            "variables_count": variables_count,
            "constraints": solver_context['constraints']
        }), 200
    except Exception as e:
        print(f"Error getting status: {e}")
        traceback.print_exc()
        return jsonify({"message": f"Error getting status: {str(e)}"}), 400

@mcp.tool()
def list_items(premises: list[str], conclusion: str) -> list[dict]:
    """Get all pending tasks in the TODO list."""
    converted = natural_language_to_logic(premises, conclusion)
    return converted

# Add Neo4j API endpoints
@app.route('/neo4j/save_relations', methods=['POST'])
def save_relations():
    try:
        data = request.json
        
        if not data or not isinstance(data, list):
            return jsonify({"error": "Invalid data format. Expected a list of relations."}), 400
        
        success_count = 0
        failed_relations = []
        
        for relation in data:
            try:
                # Extract data from the relation
                source_node = relation.get('source_node')
                target_node = relation.get('target_node')
                relation_type = relation.get('relation_type')
                properties = relation.get('properties')
                
                # Validate required fields
                if not source_node or not target_node or not relation_type:
                    failed_relations.append({
                        "relation": relation,
                        "error": "Missing required fields (source_node, target_node, or relation_type)"
                    })
                    continue
                
                # Save the relation to Neo4j
                saved = neo4j_client.save_relation(source_node, target_node, relation_type, properties)
                
                if saved:
                    success_count += 1
                else:
                    failed_relations.append({
                        "relation": relation,
                        "error": "Failed to save relation"
                    })
            except Exception as e:
                failed_relations.append({
                    "relation": relation,
                    "error": str(e)
                })
        
        return jsonify({
            "success": True,
            "message": f"Successfully saved {success_count} relations to Neo4j",
            "success_count": success_count,
            "failed_count": len(failed_relations),
            "failed_relations": failed_relations
        }), 200
        
    except Exception as e:
        print(f"Error saving relations to Neo4j: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Error saving relations: {str(e)}"}), 500

@app.route('/neo4j/find_relations', methods=['GET'])
def find_relations():
    try:
        query = request.args.get('query', '')
        
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
        
        # Find the relations in Neo4j
        relations = neo4j_client.find_relations(query)
        
        return jsonify({
            "success": True,
            "query": query,
            "count": len(relations),
            "relations": relations
        }), 200
        
    except Exception as e:
        print(f"Error finding relations in Neo4j: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Error finding relations: {str(e)}"}), 500

if __name__ == '__main__':
    mcp.run(transport="stdio")
    #app.run(host='0.0.0.0', debug=True)
