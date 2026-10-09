"""YAML adapter for weekly eating logs (``logs/*.yaml``).

Logs are gitignored personal data, not authored repo content — but they go
through the same deserialization + shape-validation pipeline as every other
DTO. No cross-validation against prepared recipes happens here; that is
enrichment, and lives in a service.
"""

from pathlib import Path

from meal_prep.adapters._yaml import read_yaml
from meal_prep.dtos.log import LogWeekDTO


def load_log_file(path: Path | str) -> LogWeekDTO:
    """Load and validate one weekly log file into its DTO."""
    file_path = Path(path)
    data = read_yaml(file_path, what="Log week")

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {file_path}: expected a mapping")

    log = LogWeekDTO.model_validate(data)
    log.source_path = file_path
    return log


def load_all_logs(logs_dir: Path | str = Path("logs")) -> dict[str, LogWeekDTO]:
    """Load and validate all weekly log files and ensure week uniqueness."""
    directory = Path(logs_dir)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Logs directory not found: {directory}")

    logs: dict[str, LogWeekDTO] = {}
    for yaml_file in sorted(directory.glob("*.yaml")):
        log = load_log_file(yaml_file)
        if log.week in logs:
            raise ValueError(f"Duplicate log week '{log.week}' across multiple files!")
        logs[log.week] = log

    return logs
