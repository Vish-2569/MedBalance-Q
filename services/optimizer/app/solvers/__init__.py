"""Solver tiers behind SolverPort: QpiAI platform → local → neal SA → greedy."""
from .port import SolverPort, Sample, SolveResult
from .chain import solve_chain

__all__ = ["SolverPort", "Sample", "SolveResult", "solve_chain"]
