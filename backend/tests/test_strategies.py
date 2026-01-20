import unittest
from pathlib import Path
import sys
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

from backend.app.core.pipeline import PipelineContext  # noqa: E402
from backend.app.strategies.registry import get_strategy, strategy_ids  # noqa: E402


class StrategySmokeTest(unittest.TestCase):
    def test_strategies_run_in_mock_mode(self) -> None:
        for strategy_id in strategy_ids():
            strategy = get_strategy(strategy_id)
            context = PipelineContext(
                job_id=uuid4(),
                strategy_id=strategy_id,
                safety_text="안전모를 착용한다. 작업 반경을 확보한다.",
                options={"duration_seconds": 30, "mood": "tense", "site_type": "warehouse"},
                attachments=None,
            )
            result = strategy.run(context)
            self.assertTrue(result.artifacts, f"no artifacts for {strategy_id}")


if __name__ == "__main__":
    unittest.main()
