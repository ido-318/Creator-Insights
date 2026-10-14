import os
from pathlib import Path

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM

from modeling_tools import inspect_modeling_input_tool
from training_tools import train_content_models
from evaluation_tools import review_model_results_tool


def build_scientist_crew():
    project_dir = Path(__file__).resolve().parent
    load_dotenv(project_dir / ".env")

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("Missing ANTHROPIC_API_KEY in .env")

    if not os.getenv("MODEL"):
        raise ValueError("Missing MODEL in .env")

    artifacts = project_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)

    llm = LLM(
        model=os.environ["MODEL"],
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=4000,
    )

    inspector = Agent(
        role="Modeling Input Inspector",
        goal="Verify the cleaned data and contract before modeling",
        backstory=(
            "You use only the analyst team's published handoff. "
            "You do not access raw data or change contract rules."
        ),
        tools=[inspect_modeling_input_tool],
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=True,
    )

    trainer = Agent(
        role="Model Training Scientist",
        goal="Train and compare model variants using the training tool",
        backstory=(
            "You report measured results without inventing scores. "
            "You distinguish training cross-validation from test results."
        ),
        tools=[train_content_models],
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=True,
    )

    evaluator = Agent(
        role="Model Evaluation Reviewer",
        goal="Verify evaluation metrics and explain model limitations",
        backstory=(
            "You do not equate successful execution with model quality. "
            "You report honestly when the baseline performs better."
        ),
        tools=[review_model_results_tool],
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=True,
    )

    inspection_task = Task(
        description=(
            "Call Inspect Modeling Input. "
            "Report validation status, row count, input features, "
            "target and contract version from the tool result. "
            "If it fails, clearly report failure."
        ),
        expected_output="A concise factual handoff validation summary.",
        agent=inspector,
    )

    training_task = Task(
        description=(
            "If the inspection reported failure, do not train. "
            "Otherwise call Train Content Models. "
            "Report the cross-validation results for every candidate, "
            "the selection method, selected model and test metrics. "
            "State explicitly whether it beat the test baseline. "
            "Do not change parameters or request repeated training "
            "to obtain a better test result."
        ),
        expected_output=(
            "A concise comparison grounded in the training tool output, "
            "or an explicit failure report."
        ),
        agent=trainer,
        context=[inspection_task],
    )

    review_task = Task(
        description=(
            "If an earlier task reported failure, report that failure "
            "instead of claiming successful evaluation. "
            "Otherwise call Review Model Results. "
            "If verification passes, write a Hebrew Markdown review "
            "of at most 300 words with these sections: "
            "1. What was verified. "
            "2. Selected model and selection method. "
            "3. Verified model and baseline test MAE. "
            "4. Interpretation and limitations. "
            "Use exact tool results, rounding MAE to two decimals. "
            "Lower MAE is better. "
            "If beats_baseline is false, clearly state that the "
            "selected model did not beat the baseline on this test set. "
            "Do not claim production readiness or causal findings. "
            "Mention that the test set was inspected during development. "
            "End with: סוף הבדיקה"
        ),
        expected_output=(
            "A complete Hebrew review grounded in verified metrics, "
            "ending with סוף הבדיקה, or an explicit failure report."
        ),
        agent=evaluator,
        context=[inspection_task, training_task],
        output_file=str(artifacts / "scientist_review.md"),
    )

    return Crew(
        agents=[inspector, trainer, evaluator],
        tasks=[inspection_task, training_task, review_task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )


if __name__ == "__main__":
    result = build_scientist_crew().kickoff()
    print(result.raw)