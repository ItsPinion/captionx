"""Structured output generation (plan.md §13 / §19 / §20)."""

from .json_writer import build_results_payload, write_results_json
from .csv_writer import write_results_csv

__all__ = [
    "build_results_payload",
    "write_results_csv",
    "write_results_json",
]
