# processing.py - Z3 Processing Functions
from z3 import *
import traceback
import re
from typing import List, Dict, Tuple

# Import NLTK for natural language processing
try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.tag import pos_tag
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    print("[Warning] NLTK not available for relation extraction")


def solve_equation(equation: str) -> dict:
    """
    Solve an equation or system of equations using Z3.

    Args:
        equation: String containing equations separated by commas.
                 Example: "x + y == 10, x > 3, y > 2"

    Returns:
        Dictionary with solution status and model if found.
    """
    try:
        # Create a local scope for variables
        locals_dict = {}

        # Parse the equation to extract variable names
        # Remove operators and numbers to find variable names
        b = "-+/*=><1234567890, "
        cache = equation
        for char in b:
            cache = cache.replace(char, "")
        single_cache = set(cache)

        # Create Z3 variables in the local scope
        for entry in single_cache:
            if entry.strip():  # Skip empty strings
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
            result = {}
            for var in locals_dict:
                if var in [decl.name() for decl in model.decls()]:
                    result[var] = str(model[locals_dict[var]])

            return {
                "status": "satisfiable",
                "solution": result,
                "message": "Solution found"
            }
        else:
            return {
                "status": "unsatisfiable",
                "solution": None,
                "message": "No solution exists for the given constraints"
            }
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return {
            "status": "error",
            "solution": None,
            "message": f"Invalid equation: {str(e)}"
        }


def extract_relations(sentence: str) -> List[Tuple[str, str, str]]:
    """
    Extract semantic relations from a sentence using NLTK.

    Args:
        sentence: Natural language sentence to analyze

    Returns:
        List of tuples (subject, relation, object)
    """
    if not NLTK_AVAILABLE:
        return [("error", "nltk_not_available", "Please install NLTK")]

    try:
        # Tokenize and tag the sentence
        tokens = word_tokenize(sentence.lower())
        tagged = pos_tag(tokens)

        relations = []

        # Pattern 1: "X is Y" (identity/equality)
        is_indices = [i for i, (word, _) in enumerate(tagged) if word in ["is", "are"]]
        for idx in is_indices:
            if idx > 0 and idx < len(tagged) - 1:
                # Look for nouns before and after "is"
                subj_candidates = [(i, word) for i, (word, tag) in enumerate(tagged[:idx])
                                 if tag.startswith('NN')]
                obj_candidates = [(i, word) for i, (word, tag) in enumerate(tagged[idx+1:], start=idx+1)
                                if tag.startswith('NN')]

                if subj_candidates and obj_candidates:
                    # Get the closest subject and object
                    subj_idx, subj = max(subj_candidates, key=lambda x: x[0])
                    obj_idx, obj = min(obj_candidates, key=lambda x: x[0])

                    # Check for "not" before the verb
                    negation = False
                    for i in range(max(0, subj_idx), idx):
                        if tagged[i][0] in ["not", "n't", "never"]:
                            negation = True
                            break

                    rel_type = "is_not" if negation else "is"
                    relations.append((subj, rel_type, obj))

        # Pattern 2: "X has Y" (possession)
        has_indices = [i for i, (word, _) in enumerate(tagged)
                      if word in ["has", "have", "owns", "possesses"]]
        for idx in has_indices:
            if idx > 0 and idx < len(tagged) - 1:
                subj_candidates = [(i, word) for i, (word, tag) in enumerate(tagged[:idx])
                                 if tag.startswith('NN')]
                obj_candidates = [(i, word) for i, (word, tag) in enumerate(tagged[idx+1:], start=idx+1)
                                if tag.startswith('NN')]

                if subj_candidates and obj_candidates:
                    subj_idx, subj = max(subj_candidates, key=lambda x: x[0])
                    obj_idx, obj = min(obj_candidates, key=lambda x: x[0])
                    relations.append((subj, "has", obj))

        # Pattern 3: "All X are Y" (subset)
        all_indices = [i for i, (word, _) in enumerate(tagged) if word in ["all", "every"]]
        for idx in all_indices:
            if idx < len(tagged) - 3:
                if (idx+1 < len(tagged) and tagged[idx+1][1].startswith('NN') and
                    idx+2 < len(tagged) and tagged[idx+2][0] in ["is", "are"] and
                    idx+3 < len(tagged) and (tagged[idx+3][1].startswith('NN') or tagged[idx+3][1].startswith('JJ'))):

                    subj = tagged[idx+1][0]
                    obj = tagged[idx+3][0]
                    relations.append((subj, "subset_of", obj))

        # Pattern 4: "X is greater/less than Y" (comparison)
        for i in range(len(tagged) - 4):
            if (tagged[i][1].startswith('NN') and
                tagged[i+1][0] in ["is", "are"] and
                tagged[i+2][0] in ["greater", "less", "bigger", "smaller"] and
                tagged[i+3][0] == "than"):

                # Find the next noun (skip articles like "the")
                obj = None
                for j in range(i+4, min(i+7, len(tagged))):
                    if tagged[j][1].startswith('NN'):
                        obj = tagged[j][0]
                        break

                if obj:
                    subj = tagged[i][0]
                    rel = f"{tagged[i+2][0]}_than"
                    relations.append((subj, rel, obj))

        # Pattern 5: Verb-based relations (X verbs Y)
        for i in range(len(tagged) - 2):
            if (tagged[i][1].startswith('NN') and
                tagged[i+1][1].startswith('VB') and
                tagged[i+2][1].startswith('NN')):

                subj = tagged[i][0]
                verb = tagged[i+1][0]
                obj = tagged[i+2][0]

                # Skip "is/are" as they're handled above
                if verb not in ["is", "are", "was", "were", "be"]:
                    relations.append((subj, verb, obj))

        return relations

    except Exception as e:
        print(f"Error extracting relations: {e}")
        traceback.print_exc()
        return [("error", "extraction_failed", str(e))]


def natural_language_to_logic(premises: List[str], conclusion: str) -> Dict:
    """
    Convert natural language premises and conclusion to Z3 logic.

    Args:
        premises: List of natural language statements
        conclusion: Natural language conclusion

    Returns:
        Dictionary with converted premises and conclusion
    """
    try:
        converted_premises = []
        entities = set()
        predicates = set()

        # Add standard declarations
        converted_premises.append("Object = DeclareSort('Object')")
        converted_premises.append("s = Solver()")

        # Extract relations from all statements
        all_text = ' '.join(premises + [conclusion])
        relations = extract_relations(all_text)

        # Process each relation to build entities and predicates
        for subj, rel, obj in relations:
            if subj != "error":
                entities.add(subj)
                entities.add(obj)
                predicates.add(rel)

        # Define entities as constants
        for entity in entities:
            converted_premises.append(f"{entity} = Const('{entity}', Object)")

        # Define predicates as functions
        for predicate in predicates:
            pred_name = predicate.capitalize().replace("_", "")
            converted_premises.append(
                f"{pred_name} = Function('{pred_name}', Object, Object, BoolSort())"
            )

        # Process premises to add constraints
        for premise in premises:
            rels = extract_relations(premise)
            for subj, rel, obj in rels:
                if subj != "error":
                    rel_name = rel.capitalize().replace("_", "")
                    converted_premises.append(f"s.add({rel_name}({subj}, {obj}))")

        # Process conclusion
        conclusion_rels = extract_relations(conclusion)
        if conclusion_rels and conclusion_rels[0][0] != "error":
            subj, rel, obj = conclusion_rels[0]
            rel_name = rel.capitalize().replace("_", "")
            converted_conclusion = f"{rel_name}({subj}, {obj})"
        else:
            converted_conclusion = "True"

        return {
            "premises": converted_premises,
            "conclusion": converted_conclusion
        }

    except Exception as e:
        print(f"Error in natural language processing: {e}")
        traceback.print_exc()
        raise ValueError(f"Error processing natural language: {str(e)}")
