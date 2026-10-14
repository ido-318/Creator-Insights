from analyst_tools import clean_facebook_dataset
import os
from pathlib import Path

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM

project_dir = Path(__file__).resolve().parent
load_dotenv(project_dir / ".env")

if not os.getenv("ANTHROPIC_API_KEY"):
    raise SystemExit("Missing ANTHROPIC_API_KEY in .env")

llm = LLM(
    model=os.environ["MODEL"],
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_tokens=500,
)

analyst = Agent(
    role="Data Cleaning Analyst",
    goal="Clean the dataset using the provided tool and report its results",
    backstory=(
        "You verify data preparation through tool results. "
        "You never invent counts or claim actions you did not perform."
    ),
    llm=llm,
    tools=[clean_facebook_dataset],
    allow_delegation=False,
    verbose=True,
    max_iter=3,
)

task = Task(
    description=(
        "Use the Clean Facebook Dataset tool to clean the dataset. "
        "Report in Hebrew the original row count, removed row count, "
        "clean row count, column count and output path. "
        "Explain the removal reason using the removal_reason field. "
        "If duplicates_checked is false, state that duplicates were "
        "not checked. Never invent a reason for removing rows. "
        "If the tool fails, report failure without claiming success."
    ),
    expected_output=(
        "A concise Hebrew summary of the tool results, including "
        "the exact removal reason and whether duplicates were checked."
    ),
    agent=analyst,
)

crew = Crew(
    agents=[analyst],
    tasks=[task],
    memory=False,
    verbose=False,
)

if __name__ == "__main__":
    result = crew.kickoff()
    print(result.raw)