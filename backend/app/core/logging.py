import json
import logging
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "at": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "event",
            "game_id",
            "user_id",
            "provider",
            "operation",
            "reason",
            "snapshot_id",
            "expected_value",
            "target_projection",
            "multiplier",
            "dealer_algorithm",
            "standard_deviation",
            "ev_multiplier",
            "risk_weight",
            "base_target",
            "random_factor",
        ):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data, default=str)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
