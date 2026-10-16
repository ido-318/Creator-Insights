from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field
from crewai.flow.flow import Flow, start, listen

from analyst_crew import build_analyst_crew
from scientist_crew import build_scientist_crew
from modeling_tools import inspect_modeling_input
from evaluation_tools import review_model_results
from app_security import redact_secrets
from workspace_runtime import WorkspaceBusy, workspace_lock


PROJECT_DIR = Path(__file__).resolve().parent
ARTIFACTS = PROJECT_DIR / "artifacts"


class ProjectState(BaseModel):
    status: str = "not_started"
    error: str = ""
    events: list[dict] = Field(default_factory=list)


def run_checked_crew(factory, report_name, filenames):
    """Run a crew, save its report and verify refreshed artifacts."""
    ARTIFACTS.mkdir(exist_ok=True)

    previous = {}

    for filename in filenames:
        path = ARTIFACTS / filename
        previous[filename] = (
            path.stat().st_mtime_ns if path.exists() else None
        )

    result = factory().kickoff()
    report = result.raw

    if not isinstance(report, str) or not report.strip():
        raise RuntimeError("Crew returned an empty report.")

    expected_endings = {
        "insights.md": "סוף הדוח",
        "scientist_review.md": "סוף הבדיקה",
    }

    if not report.strip().endswith(expected_endings[report_name]):
        raise RuntimeError(
            f"Report may be incomplete or report a failure: {report_name}"
        )

    # Save the actual report returned by this execution
    (ARTIFACTS / report_name).write_text(
        report,
        encoding="utf-8",
    )

    # Require fresh artifacts rather than files from an earlier run
    for filename in filenames:
        path = ARTIFACTS / filename

        if not path.is_file():
            raise RuntimeError(f"Missing artifact: {filename}")

        if path.stat().st_mtime_ns == previous[filename]:
            raise RuntimeError(f"Artifact was not updated: {filename}")


class CreatorInsightsFlow(Flow[ProjectState]):

    def record(self, status, message):
        message = redact_secrets(message)
        self.state.status = status
        self.state.events.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "message": message,
        })

        ARTIFACTS.mkdir(exist_ok=True)

        log_path = ARTIFACTS / f"flow_{self.state.id}.json"
        log_path.write_text(
            self.state.model_dump_json(indent=2),
            encoding="utf-8",
        )

        print(f"\n[{status}] {message}")

    def fail(self, stage, error):
        self.state.error = redact_secrets(f"{stage}: {error}")
        self.record("failed", self.state.error)
        return False

    @start()
    def run_analysts(self):
        self.record("analysts_running", "Starting analyst crew.")

        try:
            run_checked_crew(
                build_analyst_crew,
                "insights.md",
                [
                    "clean_data.csv",
                    "eda_report.html",
                    "insights.md",
                    "dataset_contract.json",
                    "handoff_manifest.json",
                ],
            )
        except Exception as error:
            return self.fail("Analyst crew", error)

        self.record(
            "analysts_done",
            "Analyst artifacts and handoff manifest updated.",
        )
        return True

    @listen(run_analysts)
    def validate_handoff(self, analysts_ok):
        if not analysts_ok:
            return False

        self.record(
            "validating",
            "Checking handoff integrity, contract and data.",
        )

        try:
            result = inspect_modeling_input(ARTIFACTS)
        except Exception as error:
            return self.fail("Handoff validation", error)

        self.record(
            "handoff_passed",
            f"Validated {result['rows']} rows against the contract "
            "and verified handoff fingerprints.",
        )
        return True

    @listen(validate_handoff)
    def run_scientists(self, handoff_ok):
        if not handoff_ok:
            print("\nSTOPPED: modeling crew was not started.")
            return {
                "status": "failed",
                "error": self.state.error,
            }

        self.record("scientists_running", "Starting modeling crew.")

        try:
            run_checked_crew(
                build_scientist_crew,
                "scientist_review.md",
                [
                    "features.csv",
                    "model.joblib",
                    "evaluation_report.md",
                    "model_card.md",
                    "training_summary.json",
                    "test_predictions.csv",
                    "data_split.csv",
                    "evaluation_check.json",
                    "scientist_review.md",
                ],
            )

            # Verify metrics independently of the agent's explanation
            review = review_model_results()

        except Exception as error:
            self.fail("Modeling crew or evaluation", error)
            return {
                "status": "failed",
                "error": self.state.error,
            }

        self.record(
            "completed",
            "Artifacts updated and evaluation metrics verified.",
        )

        return {
            "status": "completed",
            "model": review["selected_model"],
            "test_mae": review["recalculated_model_mae"],
            "beats_baseline": review["beats_baseline"],
        }


def run_project():
    """The supported UI/CLI entry point serializes the entire paid workflow."""
    with workspace_lock(ARTIFACTS):
        flow = CreatorInsightsFlow()
        result = flow.kickoff()
        return flow, result


if __name__ == "__main__":
    try:
        flow, result = run_project()
    except WorkspaceBusy as error:
        print(str(error))
        raise SystemExit(2)

    print("\nFlow result:")
    print(result)

    if flow.state.status != "completed":
        raise SystemExit(1)
