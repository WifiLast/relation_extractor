from __future__ import annotations

import argparse
import importlib
import os
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
from fastmcp import FastMCP
from scipy import integrate, optimize, stats
import z3

USAGE_EXAMPLES: Dict[str, List[Dict[str, str]]] = {
    "solve_equation": [
        {
            "call": "solve_equation('np.cos(x) - x', bracket_start=0.0, bracket_end=1.0)",
            "expected_result": "0.7390851332151607",
            "description": "Finds the fixed point of cos(x).",
        },
        {
            "call": "solve_equation('np.sin(x)', bracket_start=-1.0, bracket_end=1.0)",
            "expected_result": "0.0",
            "description": "Root of sin(x) closest to the origin.",
        },
        {
            "call": "solve_equation('x**2 - 9', bracket_start=0.0, bracket_end=5.0)",
            "expected_result": "3.0",
            "description": "Positive root of x^2 - 9 using Brent's method.",
        },
    ],
    "differentiate": [
        {
            "call": "differentiate('x**3 + 2*x', point=2.0)",
            "expected_result": "14.0",
            "description": "First derivative of a polynomial at x = 2.",
        },
        {
            "call": "differentiate('np.sin(x)', point=0.0)",
            "expected_result": "1.0",
            "description": "Derivative of sin(x) at the origin equals cos(0).",
        },
        {
            "call": "differentiate('np.exp(-x**2)', point=0.0, n=2)",
            "expected_result": "-2.0",
            "description": "Second derivative of the Gaussian at x = 0.",
        },
    ],
    "integrate_function": [
        {
            "call": "integrate_function('np.exp(-x**2)', lower=0.0, upper=1.0)",
            "expected_result": "{'value': 0.7468241328124271, 'abserr': 8.291413475940725e-15}",
            "description": "Area under a Gaussian bell on [0, 1].",
        },
        {
            "call": "integrate_function('np.sin(x)', lower=0.0, upper=np.pi)",
            "expected_result": "{'value': 2.0, 'abserr': 2.220446049250313e-14}",
            "description": "Integral of sin(x) over one half-period.",
        },
        {
            "call": "integrate_function('x**2', lower=-1.0, upper=1.0)",
            "expected_result": "{'value': 0.6666666666666667, 'abserr': 7.401486830834377e-15}",
            "description": "Definite integral of x^2 symmetric around the origin.",
        },
    ],
    "distribution_pdf": [
        {
            "call": "distribution_pdf('norm', x=0.0)",
            "expected_result": "0.3989422804014327",
            "description": "Standard normal density at the origin.",
        },
        {
            "call": "distribution_pdf('binom', x=3, shape_args=[10, 0.5])",
            "expected_result": "0.1171875",
            "description": "Binomial PMF for 10 trials with p=0.5 at k=3.",
        },
    ],
    "distribution_cdf": [
        {
            "call": "distribution_cdf('norm', x=1.96)",
            "expected_result": "0.9750021048517795",
            "description": "Lower-tail probability for Z <= 1.96.",
        },
        {
            "call": "distribution_cdf('binom', x=4, shape_args=[10, 0.5])",
            "expected_result": "0.376953125",
            "description": "Cumulative probability P(X <= 4) for a binomial(10, 0.5).",
        },
    ],
    "distribution_quantile": [
        {
            "call": "distribution_quantile('norm', probability=0.975)",
            "expected_result": "1.959963984540054",
            "description": "0.975 quantile (two-sided 95%) of the standard normal.",
        },
        {
            "call": "distribution_quantile('chi2', probability=0.95, shape_args=[4])",
            "expected_result": "9.487729036781154",
            "description": "0.95 quantile of a chi-square distribution with 4 degrees of freedom.",
        },
    ],
    "distribution_probability_between": [
        {
            "call": "distribution_probability_between('norm', lower=-1.0, upper=1.0)",
            "expected_result": "0.6826894921370859",
            "description": "Probability mass within one standard deviation of the mean.",
        },
        {
            "call": "distribution_probability_between('binom', lower=0, upper=2, shape_args=[5, 0.5])",
            "expected_result": "0.5",
            "description": "Probability of <=2 successes in 5 fair Bernoulli trials.",
        },
    ],
    "z3_solve_constraints": [
        {
            "call": "z3_solve_constraints(['x > 2', 'x < 5'])",
            "expected_result": "{'status': 'sat', 'model': {'x': '3'}}",
            "description": "Finds a satisfying assignment for a simple interval.",
        },
        {
            "call": "z3_solve_constraints(['x + y == 10', 'x > 3', 'y > 2'])",
            "expected_result": "{'status': 'sat', 'model': {'x': '4', 'y': '6'}}",
            "description": "Solves a small linear constraint system.",
        },
    ],
    "z3_prove_theorem": [
        {
            "call": "z3_prove_theorem([\"Object = DeclareSort('Object')\", \"s = Solver()\", \"Human = Function('Human', Object, BoolSort())\", \"Mortal = Function('Mortal', Object, BoolSort())\", \"socrates = Const('socrates', Object)\", \"x = Const('x', Object)\", \"s.add(ForAll([x], Implies(Human(x), Mortal(x))))\", \"s.add(Human(socrates))\"], 'Mortal(socrates)')",
            "expected_result": "{'proved': true, 'status': 'unsat'}",
            "description": "Proves that Socrates is mortal from the premises.",
        }
    ],
}


mcp = FastMCP("Math MCP 🧮")
SERVER_HOST = os.getenv("MATH_MCP_HOST", "10.0.0.1")
SERVER_PORT = int(os.getenv("MATH_MCP_PORT", "2000"))
SERVER_PATH = os.getenv("MATH_MCP_PATH", "/math")

_SAFE_GLOBALS: Dict[str, object] = {
    "np": np,
    "pi": np.pi,
    "e": np.e,
}

for _name in dir(np):
    if not _name.startswith("_"):
        _SAFE_GLOBALS.setdefault(_name, getattr(np, _name))


def _load_z3_module():
    """Load the external z3-solver package without being shadowed by ./z3."""
    script_dir = Path(__file__).resolve().parent
    removed_paths: list[str] = []

    for candidate in ("", str(script_dir)):
        while candidate in sys.path:
            sys.path.remove(candidate)
            removed_paths.append(candidate)

    sys.modules.pop("z3", None)

    try:
        z3_module = importlib.import_module("z3")
    finally:
        for path_entry in reversed(removed_paths):
            sys.path.insert(0, path_entry)

    if not hasattr(z3_module, "Solver"):
        raise ImportError(
            "Imported module 'z3' does not expose Solver(). "
            "The local ./z3 directory is likely shadowing the z3-solver package."
        )

    return z3_module


_z3 = _load_z3_module()
_Z3_GLOBALS: Dict[str, object] = {
    name: getattr(_z3, name)
    for name in dir(_z3)
    if not name.startswith("_")
}
_Z3_RESERVED_NAMES = set(_Z3_GLOBALS) | {"And", "Or", "Not", "If", "True", "False"}

solver_context: Dict[str, object] = {
    "solver": None,
    "variables": {},
    "constraints": [],
}


def reset_solver_context() -> Dict[str, object]:
    """Reset the persistent Z3 solver context."""
    solver_context["solver"] = _z3.Solver()
    solver_context["variables"] = {}
    solver_context["constraints"] = []
    return solver_context


reset_solver_context()


def numerical_derivative(
    func: Callable[[float], float],
    x0: float,
    dx: float = 1e-6,
    n: int = 1,
    order: int = 5,
) -> float:
    """Numerically approximate the n-th derivative using recursive central differences."""
    if n < 1:
        raise ValueError("n must be a positive integer.")
    if order % 2 == 0:
        raise ValueError("order must be an odd integer for numerical differentiation.")
    if dx <= 0:
        raise ValueError("dx must be positive.")

    if n == 1:
        return float((func(x0 + dx) - func(x0 - dx)) / (2.0 * dx))

    def lower(value: float) -> float:
        return numerical_derivative(func, value, dx=dx, n=n - 1, order=order)

    return float((lower(x0 + dx) - lower(x0 - dx)) / (2.0 * dx))


def _build_callable(expression: str, variable: str) -> Callable[[float], float]:
    """Compile expression into a callable f(x) with a restricted namespace."""
    try:
        compiled = compile(expression, "<expression>", "eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression: {expression}") from exc

    def func(value: float) -> float:
        local_env = {variable: value}
        return float(eval(compiled, _SAFE_GLOBALS, local_env))

    return func


def _normalize_equation_expression(expression: str) -> str:
    """Normalize `lhs = rhs` into `lhs - (rhs)` so the numeric solver can find a root."""
    normalized = expression.strip()
    if "=" in normalized and "==" not in normalized and "<=" not in normalized and ">=" not in normalized:
        left, right = normalized.split("=", 1)
        return f"({left.strip()}) - ({right.strip()})"
    return normalized


def _get_distribution(name: str):
    """Return a SciPy distribution object by name with basic validation."""
    try:
        dist = getattr(stats, name)
    except AttributeError as exc:
        raise ValueError(f"Unknown distribution '{name}'. Refer to scipy.stats for valid names.") from exc
    if not hasattr(dist, "cdf"):
        raise ValueError(f"Distribution '{name}' does not expose the expected SciPy API.")
    return dist


def _distribution_args_kwargs(
    dist,
    shape_args: Optional[Sequence[float]],
    loc: float,
    scale: float,
    extra_params: Optional[Dict[str, float]] = None,
):
    args = tuple(shape_args or [])
    kwargs: Dict[str, float] = dict(extra_params or {})
    if loc != 0.0:
        kwargs.setdefault("loc", loc)
    if scale != 1.0 and hasattr(dist, "pdf"):
        kwargs.setdefault("scale", scale)
    return args, kwargs


def _pmf_or_pdf(dist, x: float, args: Sequence[float], kwargs: Dict[str, float]) -> float:
    if hasattr(dist, "pdf"):
        return float(dist.pdf(x, *args, **kwargs))
    if hasattr(dist, "pmf"):
        return float(dist.pmf(x, *args, **kwargs))
    raise ValueError("Distribution does not provide pdf/pmf evaluation.")


def _try_bracket(func: Callable[[float], float], start: float, end: float) -> tuple[float, float] | None:
    """Return a sign-changing bracket if one exists in [start, end]."""
    if start == end:
        end = start + 1.0

    a, b = (start, end) if start < end else (end, start)
    sample_points = np.linspace(a, b, 25)
    previous_x = float(sample_points[0])
    previous_y = float(func(previous_x))
    if abs(previous_y) < 1e-12:
        return previous_x - 1e-6, previous_x + 1e-6

    for point in sample_points[1:]:
        current_x = float(point)
        current_y = float(func(current_x))
        if abs(current_y) < 1e-12:
            return current_x - 1e-6, current_x + 1e-6
        if previous_y * current_y < 0:
            return previous_x, current_x
        previous_x = current_x
        previous_y = current_y
    return None


def _find_bracket(func: Callable[[float], float], bracket_start: float, bracket_end: float) -> tuple[float, float] | None:
    """Search for a sign-changing bracket near the provided range."""
    direct = _try_bracket(func, bracket_start, bracket_end)
    if direct is not None:
        return direct

    center = (bracket_start + bracket_end) / 2.0
    width = max(abs(bracket_end - bracket_start), 1.0)
    for multiplier in (2.0, 5.0, 10.0, 25.0, 50.0):
        span = width * multiplier
        candidate = _try_bracket(func, center - span, center + span)
        if candidate is not None:
            return candidate

    for candidate_range in [(-10.0, 10.0), (-100.0, 100.0), (-1000.0, 1000.0)]:
        candidate = _try_bracket(func, candidate_range[0], candidate_range[1])
        if candidate is not None:
            return candidate

    return None


def _extract_symbol_names(expression: str) -> list[str]:
    names = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", expression))
    return sorted(name for name in names if name not in _Z3_RESERVED_NAMES)


def _coerce_model_value(value: object) -> str:
    return str(value)


def _build_z3_eval_env(variables: Dict[str, object] | None = None) -> Dict[str, object]:
    env = dict(_Z3_GLOBALS)
    if variables:
        env.update(variables)
    return env


def _ensure_context_variables(expressions: Sequence[str]) -> Dict[str, object]:
    variables = solver_context["variables"]
    assert isinstance(variables, dict)
    for expression in expressions:
        for name in _extract_symbol_names(expression):
            variables.setdefault(name, _z3.Real(name))
    return variables


def _check_solver_result(solver, variables: Dict[str, object], constraints: Sequence[str]) -> Dict[str, object]:
    result = solver.check()
    status = str(result)
    payload: Dict[str, object] = {
        "status": status,
        "constraints": list(constraints),
    }
    if result == _z3.sat:
        model = solver.model()
        assignments: Dict[str, str] = {}
        for var_name, var in variables.items():
            value = model.eval(var, model_completion=True)
            assignments[var_name] = _coerce_model_value(value)
        payload["model"] = assignments
    return payload


def _create_theorem_context() -> Dict[str, object]:
    return {
        "solver": _z3.Solver(),
        "sorts": {"Object": _z3.DeclareSort("Object")},
    }


@mcp.tool
def solve_equation(
    expression: str,
    bracket_start: float = -10.0,
    bracket_end: float = 10.0,
    variable: str = "x",
) -> float:
    """Return x such that the expression evaluates to zero.

    Accepts either a root expression like `x + 6 - 11` or an equation like `x + 6 = 11`.
    If the provided bracket does not contain a sign change, the solver automatically widens
    the search interval and falls back to secant iteration. Examples:
    >>> solve_equation('np.cos(x) - x', bracket_start=0.0, bracket_end=1.0)
    0.7390851332151607
    >>> solve_equation('np.sin(x)', bracket_start=-1.0, bracket_end=1.0)
    0.0
    >>> solve_equation('x + 6 = 11')
    5.0
    """
    normalized_expression = _normalize_equation_expression(expression)
    func = _build_callable(normalized_expression, variable)

    bracket = _find_bracket(func, bracket_start, bracket_end)
    if bracket is not None:
        result = optimize.root_scalar(func, bracket=list(bracket), method="brentq")
    else:
        x0 = bracket_start
        x1 = bracket_end if bracket_end != bracket_start else bracket_start + 1.0
        result = optimize.root_scalar(func, x0=x0, x1=x1, method="secant")

    if not result.converged:
        raise RuntimeError(
            "Failed to find a root. Try a different expression or provide a narrower bracket."
        )
    return float(result.root)


@mcp.tool
def z3_solve_constraints(constraints: List[str]) -> Dict[str, object]:
    """Solve one or more symbolic constraints with Z3 and return a model if satisfiable."""
    if not constraints:
        raise ValueError("constraints must not be empty.")

    solver = _z3.Solver()
    variables = {name: _z3.Real(name) for expr in constraints for name in _extract_symbol_names(expr)}
    eval_env = _build_z3_eval_env(variables)

    for constraint in constraints:
        solver.add(eval(constraint, {"__builtins__": {}}, eval_env))

    return _check_solver_result(solver, variables, constraints)


@mcp.tool
def z3_add_constraint(constraint: str) -> Dict[str, object]:
    """Add a symbolic constraint to the persistent Z3 solver context."""
    if not constraint.strip():
        raise ValueError("constraint must not be empty.")

    solver = solver_context["solver"]
    assert solver is not None
    variables = _ensure_context_variables([constraint])
    eval_env = _build_z3_eval_env(variables)
    solver.add(eval(constraint, {"__builtins__": {}}, eval_env))
    constraints = solver_context["constraints"]
    assert isinstance(constraints, list)
    constraints.append(constraint)
    return {
        "message": "Constraint added",
        "constraint": constraint,
        "constraints": list(constraints),
    }


@mcp.tool
def z3_check_satisfiability() -> Dict[str, object]:
    """Check the persistent Z3 solver context and return its satisfiability status."""
    solver = solver_context["solver"]
    variables = solver_context["variables"]
    constraints = solver_context["constraints"]
    assert solver is not None
    assert isinstance(variables, dict)
    assert isinstance(constraints, list)
    return _check_solver_result(solver, variables, constraints)


@mcp.tool
def z3_reset_solver() -> Dict[str, str]:
    """Reset the persistent Z3 solver context."""
    reset_solver_context()
    return {"message": "Solver context reset successfully"}


@mcp.tool
def z3_solver_status() -> Dict[str, object]:
    """Return the current persistent solver status."""
    variables = solver_context["variables"]
    constraints = solver_context["constraints"]
    solver = solver_context["solver"]
    assert isinstance(variables, dict)
    assert isinstance(constraints, list)
    return {
        "status": "active" if solver is not None else "inactive",
        "constraints_count": len(constraints),
        "variables_count": len(variables),
        "constraints": list(constraints),
    }


@mcp.tool
def z3_prove_theorem(premises: List[str], conclusion: str) -> Dict[str, object]:
    """Prove whether a conclusion follows from the given Z3 premises."""
    if not premises:
        raise ValueError("premises must not be empty.")
    if not conclusion.strip():
        raise ValueError("conclusion must not be empty.")

    context = _create_theorem_context()
    locals_dict: Dict[str, object] = {
        "Object": context["sorts"]["Object"],
        "s": context["solver"],
    }
    exec_globals = {"__builtins__": {}, **_Z3_GLOBALS}

    for premise in premises:
        exec(premise, exec_globals, locals_dict)

    exec(f"s.add(Not({conclusion}))", exec_globals, locals_dict)

    solver = locals_dict["s"]
    result = solver.check()
    response: Dict[str, object] = {
        "proved": result == _z3.unsat,
        "status": str(result),
    }
    if result == _z3.sat:
        model = solver.model()
        response["counterexample"] = {
            decl.name(): _coerce_model_value(model[decl])
            for decl in model.decls()
        }
    return response


@mcp.tool
def differentiate(
    expression: str,
    point: float,
    variable: str = "x",
    dx: float = 1e-6,
    order: int = 5,
    n: int = 1,
) -> float:
    """Evaluate the n-th derivative of the expression at the given point.

    Uses central differences for numerical differentiation. Examples:
    >>> differentiate('x**3 + 2*x', point=2.0)
    14.0
    >>> differentiate('np.sin(x)', point=0.0)
    1.0
    """
    if order % 2 == 0:
        raise ValueError("order must be an odd integer for numerical differentiation.")
    func = _build_callable(expression, variable)
    return float(numerical_derivative(func, point, dx=dx, n=n, order=order))


@mcp.tool
def integrate_function(
    expression: str,
    lower: float,
    upper: float,
    variable: str = "x",
) -> Dict[str, float]:
    """Compute the definite integral of the expression between lower and upper bounds.

    Uses `scipy.integrate.quad`. Examples:
    >>> integrate_function('np.exp(-x**2)', lower=0.0, upper=1.0)
    {'value': 0.7468241328124271, 'abserr': 8.291413475940725e-15}
    >>> integrate_function('np.sin(x)', lower=0.0, upper=np.pi)
    {'value': 2.0, 'abserr': 2.220446049250313e-14}
    """
    func = _build_callable(expression, variable)
    value, error = integrate.quad(func, lower, upper)
    return {"value": float(value), "abserr": float(error)}


@mcp.tool
def distribution_pdf(
    distribution: str,
    x: float,
    shape_args: Optional[List[float]] = None,
    loc: float = 0.0,
    scale: float = 1.0,
    extra_params: Optional[Dict[str, float]] = None,
) -> float:
    """Evaluate the PDF/PMF of a SciPy distribution at x.

    >>> distribution_pdf('norm', x=0.0)
    0.3989422804014327
    >>> distribution_pdf('binom', x=3, shape_args=[10, 0.5])
    0.1171875
    """
    dist = _get_distribution(distribution)
    args, kwargs = _distribution_args_kwargs(dist, shape_args, loc, scale, extra_params)
    return _pmf_or_pdf(dist, x, args, kwargs)


@mcp.tool
def distribution_cdf(
    distribution: str,
    x: float,
    shape_args: Optional[List[float]] = None,
    loc: float = 0.0,
    scale: float = 1.0,
    lower_tail: bool = True,
    extra_params: Optional[Dict[str, float]] = None,
) -> float:
    """Evaluate the CDF (or survival function) of a SciPy distribution at x.

    >>> distribution_cdf('norm', x=1.96)
    0.9750021048517795
    """
    dist = _get_distribution(distribution)
    args, kwargs = _distribution_args_kwargs(dist, shape_args, loc, scale, extra_params)
    if lower_tail:
        return float(dist.cdf(x, *args, **kwargs))
    return float(dist.sf(x, *args, **kwargs))


@mcp.tool
def distribution_quantile(
    distribution: str,
    probability: float,
    shape_args: Optional[List[float]] = None,
    loc: float = 0.0,
    scale: float = 1.0,
    lower_tail: bool = True,
    extra_params: Optional[Dict[str, float]] = None,
) -> float:
    """Return the quantile corresponding to the given cumulative probability.

    >>> distribution_quantile('norm', probability=0.975)
    1.959963984540054
    """
    dist = _get_distribution(distribution)
    args, kwargs = _distribution_args_kwargs(dist, shape_args, loc, scale, extra_params)
    if lower_tail:
        return float(dist.ppf(probability, *args, **kwargs))
    return float(dist.isf(probability, *args, **kwargs))


@mcp.tool
def distribution_probability_between(
    distribution: str,
    lower: float,
    upper: float,
    shape_args: Optional[List[float]] = None,
    loc: float = 0.0,
    scale: float = 1.0,
    extra_params: Optional[Dict[str, float]] = None,
) -> float:
    """Compute P(lower <= X <= upper) for the specified distribution.

    Continuous distributions use CDF differences; discrete ones include the lower PMF.
    >>> distribution_probability_between('norm', lower=-1.0, upper=1.0)
    0.6826894921370859
    """
    if lower > upper:
        raise ValueError("lower must be less than or equal to upper.")
    dist = _get_distribution(distribution)
    args, kwargs = _distribution_args_kwargs(dist, shape_args, loc, scale, extra_params)
    cdf_upper = dist.cdf(upper, *args, **kwargs)
    cdf_lower = dist.cdf(lower, *args, **kwargs)
    probability = cdf_upper - cdf_lower
    if hasattr(dist, "pmf"):
        probability += dist.pmf(lower, *args, **kwargs)
    return float(probability)


@mcp.tool
def usage_examples() -> Dict[str, List[Dict[str, str]]]:
    """Return sample tool invocations with expected numeric results."""
    # Provide serializable copies of the example data for easy display.
    return {
        category: [example.copy() for example in entries]
        for category, entries in USAGE_EXAMPLES.items()
    }


def run_server(transport: str | None = None) -> None:
    """Start the FastMCP server using the selected transport."""
    selected_transport = transport or os.getenv("MATH_MCP_TRANSPORT", "streamable-http")
    if selected_transport in {"streamable-http", "http"}:
        mcp.run(transport="http", path=SERVER_PATH, host=SERVER_HOST, port=SERVER_PORT)
    else:
        mcp.run(transport=selected_transport)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Math MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http"],
        default=os.getenv("MATH_MCP_TRANSPORT", "streamable-http"),
        help="Transport to use for FastMCP (default: streamable-http)",
    )
    args = parser.parse_args(argv)
    run_server(args.transport)


if __name__ == "__main__":
    main()
