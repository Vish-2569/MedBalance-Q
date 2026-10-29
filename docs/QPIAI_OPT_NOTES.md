# QpiAI Opt — Package Introspection Notes

Package: `qpiai-opt==0.0.9` (installed via `uv add qpiai-opt`)

## Key Classes

### `Client`
```python
from qpiai_opt import Client
client = Client(api_key="...", base_url="https://...")
```
- `api_key` (str): Required for both platform and local solving.
- `base_url` (str): Platform API URL. Default from package internals.

### `LocalProvider`
```python
from qpiai_opt import LocalProvider
provider = LocalProvider(client=client)
result = provider.solve(problem, problem_class="QUBO", num_reads=200, num_sweeps=1000)
```
- Requires `client=Client(api_key=...)` — even local solving needs a valid API key for authentication.
- `problem`: A `QUBOProblem` instance.
- `problem_class`: Literal `"QUBO"`.
- `num_reads`, `num_sweeps`: Solver parameters.
- Returns a `QUBOSolveResult`.

### `QUBOProblem` (Pydantic model)
```python
from qpiai_opt import QUBOProblem
problem = QUBOProblem(
    Q={("x0", "x1"): 1.5, ("x0", "x0"): -2.0, ...},
    offset=0.0,
    num_variables=3
)
```
- `Q` (dict): Keys are `(str, str)` tuples like `("x0", "x1")`.
- `offset` (float): Constant energy offset.
- `num_variables` (int): Number of binary variables.

### `QUBOSolveResult`
```python
result.variable_assignment  # Dict[str, int|float], e.g. {"x0": 1, "x1": 0, ...}
```
- `variable_assignment`: Solution as string-keyed dict.

## Key Findings

1. **API key required everywhere**: Even `LocalProvider` needs `Client(api_key=...)`. Without a key, `AuthenticationError` is raised.
2. **String-keyed variables**: Q matrix keys and solution assignments use `"x0"`, `"x1"`, etc. Our code converts `int` keys ↔ `"xN"` strings at the boundary.
3. **Single solution per call**: `QUBOSolveResult` returns one `variable_assignment`, not a list of samples. Multiple reads may be aggregated internally.

## Solver Tiers (as implemented)

| Tier | Class | Needs API key? | Needs network? |
|---|---|---|---|
| 1. qpiai-platform | `Client.create_problem` → submit → wait | Yes | Yes |
| 2. qpiai-local | `LocalProvider.solve` | Yes | No |
| 3. neal-sa | `dwave-neal.SimulatedAnnealingSampler` | No | No |
| 4. greedy-descent | Custom bit-flip descent (50 restarts) | No | No |

Chain falls through on any exception. Every attempt is logged to `evidence/qpiai_runs/`.
