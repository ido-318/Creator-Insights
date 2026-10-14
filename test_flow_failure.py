from handoff_integrity import seal_handoff
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

import project_flow


def test_invalid_hour_blocks_modeling():
    source = Path(__file__).resolve().parent / "artifacts"

    with TemporaryDirectory() as temporary_directory:
        artifacts = Path(temporary_directory)

        for filename in ["clean_data.csv", "dataset_contract.json"]:
            shutil.copy2(source / filename, artifacts / filename)

        # Corrupt only the temporary copy
        data_path = artifacts / "clean_data.csv"
        df = pd.read_csv(data_path)
        df.loc[0, "post_hour"] = 99
        df.to_csv(data_path, index=False)
        seal_handoff(artifacts)

        # Simulate the crews, but keep the real Flow and validator
        with (
            patch.object(project_flow, "ARTIFACTS", artifacts),
            patch.object(
                project_flow,
                "run_checked_crew",
            ) as crew_runner,
            patch.object(
                project_flow,
                "review_model_results",
            ) as evaluator,
        ):
            flow = project_flow.CreatorInsightsFlow()
            result = flow.kickoff()

            assert flow.state.status == "failed", result
            assert "post_hour" in flow.state.error
            assert "values above 23" in flow.state.error

            # Only the analyst stage was reached
            assert crew_runner.call_count == 1
            assert (
                crew_runner.call_args.args[0]
                is project_flow.build_analyst_crew
            )

            evaluator.assert_not_called()

            statuses = [
                event["status"]
                for event in flow.state.events
            ]
            assert "scientists_running" not in statuses

            print("\nPASS: Invalid hour blocked the modeling crew.")
            print("Detected:", flow.state.error)


if __name__ == "__main__":
    test_invalid_hour_blocks_modeling()