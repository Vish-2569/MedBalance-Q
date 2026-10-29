# QpiAI QCloud — Package Introspection Notes

Package: `qpiai-quantum==0.7.5` (installed via `uv add qpiai-quantum`)

## Authentication

```python
from qpiai_quantum import QpiAIQuantumAuth as Auth
Auth.login(api_key)       # -> str (success message)
Auth.verify_api_key()     # -> bool
Auth.me(api_key=None)     # -> dict (user info)
Auth.list_compute_resources(display=True)
Auth.logout()             # -> str
```

## Circuit API

```python
from qpiai_quantum import Circuit, QuantumRegister, ClassicalRegister, Backend

qr = QuantumRegister(n_qubits)
cr = ClassicalRegister(n_bits)
circuit = Circuit(qr, cr)

# Gates (selection relevant to QAOA):
circuit.h(qubit)           # Hadamard
circuit.rx(qubit, theta)   # Rx rotation
circuit.rz(qubit, theta)   # Rz rotation
circuit.rzz(q1, q2, theta) # Rzz (ZZ interaction)
circuit.cx(ctrl, target)   # CNOT
circuit.p(qubit, theta)    # Phase gate
circuit.barrier()          # Barrier
circuit.measure(qubit_or_list, clbit_or_list)
circuit.measure_all()

# Run locally (QSV-Local) or cloud:
result = circuit.run(
    shots=1024,
    experiment_name="QAOA MaxCut",
    device_name="QpiAI-QSV-Local",  # or Backend.STATEVECTOR_SIMULATOR_CPU.value
)
```

## Backend Enum

| Value | String |
|---|---|
| `STATEVECTOR_SIMULATOR_CPU` | `"QpiAI-QSV-Simulator"` (cloud) |
| `DENSITY_MATRIX_SIMULATOR_CPU` | `"QpiAI-QDM-Simulator"` (cloud) |
| `LOCAL_SIMULATOR` | `"QpiAI-QSV-Local"` (local, no auth needed for circuit.run) |
| `TENSOR_NETWORK_SIMULATOR_CPU` | `"QpiAI-QTN-Simulator"` (cloud) |
| `INDUS_QPU` | `"QpiAI-Indus-1"` (hardware) |

## JobManager (for cloud submission)

```python
from qpiai_quantum import JobManager
jm = JobManager()
result = jm.submit_and_wait_for_results_qasm(
    circuit,
    experiment_name="QAOA MaxCut",
    shots=1024,
    device_name="QpiAI-QSV-Simulator",
    timeout=300,
)
```

## JobResult

```python
result.get_counts()          # -> dict[str, int] e.g. {"000": 512, "111": 512}
result.get_probabilities()   # -> dict[str, float]
result.execution_time        # -> float (seconds)
result.shots                 # -> int
result.job_id                # -> str
result.job_status            # -> str
```

## Key Findings

1. **Local simulator (`QpiAI-QSV-Local`)** works via `circuit.run()` — no auth needed for local runs.
2. **Cloud simulators** need `QpiAIQuantumAuth.login(api_key)` first; then use `JobManager.submit_and_wait_for_results_qasm()` or `circuit.run(device_name=...)`.
3. **Counts format**: bitstrings like `"01101"` → integer counts. Bit order is MSB-first by default; use `reverse_bits=True` to flip.
4. **QAOA for Max-Cut**: build cost operator via `rzz(q_i, q_j, gamma)` for edges, mixer via `rx(q, 2*beta)` for each qubit. Measure and take highest-count bitstring.

## MaxCut Tiers (as implemented)

| Tier | Method | Needs API key? | Needs network? |
|---|---|---|---|
| 1. qcloud-simulator | `circuit.run(device_name="QpiAI-QSV-Simulator")` | Yes | Yes |
| 2. qsv-local | `circuit.run(device_name="QpiAI-QSV-Local")` | No | No |
| 3. exact-brute-force | Enumerate all 2^n partitions (n ≤ 16) | No | No |
| 4. networkx-greedy | `networkx.approximation.one_exchange` | No | No |
