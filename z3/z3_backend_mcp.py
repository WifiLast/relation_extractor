from __future__ import annotations

import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from z3 import sat, unsat

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import z3_backend as backend


mcp = FastMCP("z3-backend")


def _extract_variable_names(expression: str) -> set[str]:
    cleaned = expression
    for char in "-+/*=><1234567890, ":
        cleaned = cleaned.replace(char, "")
    return {entry for entry in set(cleaned) if entry}


def _status_payload() -> dict:
    return {
        "status": "active" if backend.solver_context["solver"] else "inactive",
        "constraints_count": len(backend.solver_context["constraints"]),
        "variables_count": len(backend.solver_context["variables"]),
        "constraints": list(backend.solver_context["constraints"]),
    }


@mcp.tool()
def solve_equation(equation: str) -> dict:
    """Solve one or more comma-separated Z3 constraints and return a result string."""
    return {"message": backend.solve_equation(equation)}


@mcp.tool()
def reset_solver() -> dict:
    """Reset the shared solver state used by add_constraint and check_satisfiability."""
    backend.reset_solver_context()
    return {"message": "Solver context reset successfully", **_status_payload()}


@mcp.tool()
def add_constraint(constraint: str) -> dict:
    """Add a constraint to the shared solver context."""
    if not constraint:
        return {"message": "No constraint provided"}

    if not backend.solver_context["solver"]:
        backend.reset_solver_context()

    for entry in _extract_variable_names(constraint):
        if entry not in backend.solver_context["variables"]:
            backend.solver_context["variables"][entry] = backend.Real(entry)

    locals_dict = {**backend.solver_context["variables"]}
    backend.solver_context["solver"].add(eval(constraint.strip(), backend.__dict__, locals_dict))
    backend.solver_context["constraints"].append(constraint)

    return {
        "message": "Constraint added",
        "constraint": constraint,
        "constraints": list(backend.solver_context["constraints"]),
    }


@mcp.tool()
def check_satisfiability() -> dict:
    """Check satisfiability for the shared solver context."""
    if not backend.solver_context["solver"]:
        return {"message": "No constraints have been added yet"}

    result = backend.solver_context["solver"].check()
    payload = {"constraints": list(backend.solver_context["constraints"])}

    if result == sat:
        model = backend.solver_context["solver"].model()
        assignments = {}
        for var_name, var in backend.solver_context["variables"].items():
            if var in model:
                assignments[var_name] = str(model[var])
        return {"message": "Satisfiable", "model": assignments, **payload}

    if result == unsat:
        return {
            "message": "Unsatisfiable - no solution exists for the given constraints",
            **payload,
        }

    return {"message": "Unknown - Z3 could not determine satisfiability", **payload}


@mcp.tool()
def prove_theorem(premises: list[str], conclusion: str) -> dict:
    """Prove a theorem from Z3-formatted premises and conclusion."""
    if not premises:
        return {"message": "No premises provided"}
    if not conclusion:
        return {"message": "No conclusion provided"}
    return {"message": backend.prove_theorem(premises, conclusion)}


@mcp.tool()
def convert_natural_language(premises: list[str], conclusion: str) -> dict:
    """Convert natural-language premises and a conclusion into Z3 declarations and formulas."""
    if not premises:
        return {"message": "No premises provided"}
    if not conclusion:
        return {"message": "No conclusion provided"}
    return backend.natural_language_to_logic(premises, conclusion)


@mcp.tool()
def get_status() -> dict:
    """Return the current shared solver status."""
    return _status_payload()


@mcp.tool()
def extract_relations(sentence: str) -> dict:
    """Extract subject-relation-object triples from a sentence."""
    if not sentence:
        return {"message": "No sentence provided"}

    relations = backend.extract_relations(sentence)
    formatted_relations = [
        {"subject": subj, "relation": rel, "object": obj}
        for subj, rel, obj in relations
    ]
    method = "spaCy" if backend.is_linux() and backend.SPACY_AVAILABLE else "NLTK"

    return {
        "method": method,
        "relations": formatted_relations,
        "sentence": sentence,
    }


@mcp.tool()
def extract_relations_from_pdf(pdf_path: str) -> dict:
    """Extract relations from a local PDF path."""
    if not pdf_path:
        return {"message": "No PDF path provided"}

    try:
        import PyPDF2
    except ImportError:
        return {"message": "PyPDF2 is not installed. Install it to use PDF extraction."}

    path = Path(pdf_path).expanduser().resolve()
    if not path.exists():
        return {"message": f"PDF file not found: {path}"}
    if path.suffix.lower() != ".pdf":
        return {"message": "File must be a PDF"}

    with path.open("rb") as handle:
        pdf_reader = PyPDF2.PdfReader(handle)
        text = ""
        for page in pdf_reader.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception as exc:
                print(f"Warning: Could not extract text from a page in {path.name}: {exc}")

    text = backend.re.sub(r"\[\d+\]", " ", text)
    text = backend.re.sub(r"-\n", "", text)
    text = backend.re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
    text = text.replace("\n", " ")
    text = backend._SUFFIX_PAT.sub(r"\1\2", text)
    if backend._ENGLISH_VOCAB:
        text = backend._repair_word_spaces(text)
    text = backend.re.sub(r"([a-z]{3,})\.([a-zA-Z]{3,})", r"\1. \2", text)
    text = backend.re.sub(r" {2,}", " ", text).strip()

    sentences = backend.sent_tokenize(text)

    def is_meaningful(token: str) -> bool:
        token = token.strip()
        if len(token) <= 2:
            return False
        if backend.re.match(r"^[^a-zA-Z]+$", token):
            return False
        if not token[0].isalpha():
            return False
        if len(token.split()) > 6:
            return False
        words_in_phrase = token.split()
        if len(words_in_phrase) > 1 and any(len(word) <= 2 for word in words_in_phrase):
            return False
        return True

    all_relations = []
    for sentence in sentences:
        if len(sentence.strip()) <= 10:
            continue
        relations = backend.extract_relations(sentence)
        for subj, rel, obj in relations:
            if is_meaningful(subj) and is_meaningful(rel) and is_meaningful(obj):
                all_relations.append(
                    {
                        "subject": subj,
                        "relation": rel,
                        "object": obj,
                        "source_sentence": sentence,
                    }
                )

    method = "spaCy" if backend.is_linux() and backend.SPACY_AVAILABLE else "NLTK"
    return {
        "method": method,
        "sentences_processed": len(sentences),
        "relations": all_relations,
        "filename": path.name,
    }


@mcp.tool()
def save_relations(relations: list[dict]) -> dict:
    """Save extracted relations to MongoDB."""
    if not relations or not isinstance(relations, list):
        return {"error": "Invalid data format. Expected a list of relations."}

    success_count = 0
    failed_relations = []

    for relation in relations:
        try:
            source_node = relation.get("source_node")
            target_node = relation.get("target_node")
            relation_type = relation.get("relation_type")
            properties = relation.get("properties")

            if not source_node or not target_node or not relation_type:
                failed_relations.append(
                    {
                        "relation": relation,
                        "error": "Missing required fields (source_node, target_node, or relation_type)",
                    }
                )
                continue

            saved = backend.mongo_client.save_relation(
                source_node, target_node, relation_type, properties
            )
            if saved:
                success_count += 1
            else:
                failed_relations.append({"relation": relation, "error": "Failed to save relation"})
        except Exception as exc:
            failed_relations.append({"relation": relation, "error": str(exc)})

    return {
        "success": True,
        "message": f"Successfully saved {success_count} relations to MongoDB",
        "success_count": success_count,
        "failed_count": len(failed_relations),
        "failed_relations": failed_relations,
    }


@mcp.tool()
def find_relations(query: str) -> dict:
    """Find saved relations in MongoDB matching a query string."""
    if not query:
        return {"error": "Query parameter is required"}

    relations = backend.mongo_client.find_relations(query)
    return {
        "success": True,
        "query": query,
        "count": len(relations),
        "relations": relations,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
