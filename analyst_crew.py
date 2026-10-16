import os
from pathlib import Path

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM

from analyst_tools import clean_facebook_dataset
from analysis_tools import analyze_facebook_content
from contract_tools import publish_dataset_contract


def build_analyst_crew():
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

    cleaner = Agent(
        role="Data Cleaning Analyst",
        goal="Prepare clean data using the cleaning tool",
        backstory=(
            "You report only facts returned by tools. "
            "You never invent cleaning actions or removal reasons."
        ),
        tools=[clean_facebook_dataset],
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=True,
    )

    analyst = Agent(
        role="Exploratory Data Analyst",
        goal="Generate charts and summarize measured patterns",
        backstory=(
            "You distinguish descriptive patterns from causation. "
            "You always consider sample sizes. "
            "You do not infer outliers or variance from means "
            "and medians alone."
        ),
        tools=[analyze_facebook_content],
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=True,
    )

    publisher = Agent(
        role="Dataset Contract and Insights Publisher",
        goal="Publish the defined contract and evidence-based insights",
        backstory=(
            "You document assumptions and limitations concisely. "
            "You never claim a validation passed without a tool result. "
            "You avoid unsupported statistical conclusions."
        ),
        tools=[publish_dataset_contract],
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=True,
    )

    cleaning_task = Task(
        description=(
            "Call Clean Facebook Dataset. "
            "Report the exact counts, removal reason, duplicate-check "
            "status and output path from the tool. "
            "Keep the summary concise. "
            "If it fails, report failure; do not claim success."
        ),
        expected_output="A factual cleaning summary with exact counts.",
        agent=cleaner,
    )

    analysis_task = Task(
        description=(
            "If the previous task reported failure, stop and report it. "
            "Otherwise call Analyze Facebook Content. "
            "Include every post type's count, median and mean in your "
            "summary, plus the output paths and limitations. "
            "Do not claim causal effects or invent statistical tests. "
            "Do not infer outliers, variance or distribution shape "
            "from means and medians alone. "
            "Do not equate sample counts with publishing frequency. "
            "Keep the summary concise."
        ),
        expected_output=(
            "A measured summary by post type, artifact paths "
            "and limitations."
        ),
        agent=analyst,
        context=[cleaning_task],
    )

    publication_task = Task(
        description=(
            "If an earlier task reported failure, report it clearly. "
            "Otherwise call Publish Dataset Contract. "
            "Only if validation passes, write a concise Hebrew "
            "Markdown report of at most 350 words. "
            "Use exactly these sections: "
            "1. Contract version and validation result. "
            "2. Cleaning decisions, including the removal reason "
            "and whether duplicates were checked. "
            "3. A table with count, median and mean for each post type. "
            "4. Two descriptive observations. "
            "5. Limitations and a cautious business interpretation. "
            "Use only facts returned by tools. "
            "Do not infer outliers, variance, statistical significance "
            "or distribution shape from means and medians alone. "
            "Do not equate sample counts with publishing frequency. "
            "State that the data is historical and from one Facebook "
            "page, generalization to other accounts is untested, "
            "and observed differences do not establish causation. "
            "Avoid emojis, repeated warnings and absolute file paths. "
            "End the report with: סוף הדוח"
        ),
        expected_output=(
            "A complete Hebrew Markdown report of at most 350 words, "
            "ending with סוף הדוח, or an explicit failure report."
        ),
        agent=publisher,
        context=[cleaning_task, analysis_task],
                )

    return Crew(
        agents=[cleaner, analyst, publisher],
        tasks=[cleaning_task, analysis_task, publication_task],
        process=Process.sequential,
        memory=False,
        verbose=True,
    )


if __name__ == "__main__":
    result = build_analyst_crew().kickoff()
    print(result.raw)