# Z3 Solver Frontend

A web interface for the Z3 theorem prover, built with Angular and Flask.

## Prerequisites

- Python 3.6+
- Node.js and npm
- Angular CLI

## Installation

### Backend Setup

1. Install the required Python packages:

```bash
pip install flask flask-cors z3-solver PyPDF2 mcp
```

2. Run the Flask backend:

```bash
python z3_backend.py
```

The backend will be available at http://localhost:5000

### MCP Setup

Run the FastMCP server over stdio:

```bash
python z3_backend_mcp.py
```

Example MCP client config:

```json
{
  "mcpServers": {
    "z3-backend": {
      "command": "python",
      "args": [
        "/mnt/c/Users/MartinStark/Documents/GitHub/PLS/relation_extractor/z3/z3_backend_mcp.py"
      ]
    }
  }
}
```

The MCP server exposes tools for solving equations, managing shared solver constraints, proving theorems, converting natural language to logic, extracting relations, extracting relations from a local PDF path, and saving/finding relations in MongoDB.

### Frontend Setup

1. Navigate to the Angular project directory:

```bash
cd z3
```

2. Install dependencies:

```bash
npm install
```

3. Run the Angular development server:

```bash
ng serve
```

The frontend will be available at http://localhost:4200

## Usage

The interface allows you to:

1. Solve equations and constraints using Z3
2. Add constraints to the solver
3. Check satisfiability of the constraints

### Example Inputs

- Solve equation: `x + y > 5, x > 1, y > 1`
- Add constraint: `x < 10`

## License

MIT
