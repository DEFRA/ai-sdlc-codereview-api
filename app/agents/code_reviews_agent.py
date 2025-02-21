"""Code Reviews Agent for compliance analysis.

This module handles the core processing logic for code reviews, including:
- Processing repositories for analysis
- Matching code against compliance standards
- Generating detailed compliance reports
- Managing the review lifecycle

The agent runs in a separate process to handle long-running tasks without blocking
the main service. It follows the established standards agent pattern for consistency
across the codebase.
"""
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import asyncio
from bson import ObjectId

from app.utils.anthropic_client import AnthropicClient
from app.common.logging import get_logger
from app.database.database_utils import get_database
from app.models.code_review import ReviewStatus
from app.models.classification import Classification
from app.repositories.code_review_repo import CodeReviewRepository
from app.agents.git_repos_agent import process_repositories
from app.agents.standards_classification_agent import analyze_codebase_classifications
from app.utils.id_validation import ensure_object_id


logger = get_logger(__name__)


class CodeReviewError(Exception):
    """Base exception for code review errors."""
    pass


class StandardsFilterError(CodeReviewError):
    """Error filtering standards."""
    pass


class ReportGenerationError(CodeReviewError):
    """Error generating compliance report."""
    pass


class ProcessingError(CodeReviewError):
    """Error during code review processing."""
    pass


SYSTEM_PROMPT = """You are a code compliance analysis expert.
Analyze code against compliance standards.
Determine if code meets each standard.
Provide detailed recommendations for non-compliant areas.
Consider the codebase as a whole when evaluating compliance."""


class CodeReviewConfig:
    """Configuration management for code reviews."""

    def __init__(self) -> None:
        self.llm_testing: bool = os.getenv(
            "LLM_TESTING", "false").lower() == "true"
        self.testing_files: List[str] = (
            os.getenv("LLM_TESTING_STANDARDS_FILES", "").split(",")
            if self.llm_testing else []
        )


async def filter_standards(
    standards: List[Dict[str, Any]],
    config: CodeReviewConfig
) -> List[Dict[str, Any]]:
    """Filter standards based on configuration.

    Args:
        standards: List of standards to filter
        config: Code review configuration

    Returns:
        Filtered list of standards

    Raises:
        StandardsFilterError: If filtering fails
    """
    try:
        if not config.llm_testing:
            return standards

        filtered_standards = []
        for standard in standards:
            repository_path = standard.get('repository_path', '')
            if any(test_file.strip() in repository_path
                   for test_file in config.testing_files):
                filtered_standards.append(standard)

        logger.info(
            f"LLM Testing enabled - filtered to {len(filtered_standards)} standards")
        return filtered_standards

    except Exception as e:
        raise StandardsFilterError(
            f"Failed to filter standards: {str(e)}") from e


async def generate_user_prompt(
    standard: Dict[str, Any],
    codebase_content: str
) -> str:
    """Generate the user prompt for the Anthropic model.

    Args:
        standard: Standard to check compliance against
        codebase_content: Content of the codebase to analyze

    Returns:
        Generated prompt for the model
    """
    standard_preview = (
        standard.get('text', '')[:150] + '...'
        if len(standard.get('text', '')) > 150
        else standard.get('text', '')
    )
    logger.debug(f"Processing standard ID: {standard.get('_id')}")
    logger.debug(f"Standard preview: {standard_preview}")

    prompt = f"""Given the standard below:
## Standard {standard['_id']}
{standard['text']}

Compare the entire codebase of the submitted repository below, to assess how well the standard is adhered to:
{codebase_content}

Determine if the codebase as a whole is compliant (true/false).
List specific files/sections in the codebase that are relevant to the standard (if any).
If non-compliant, provide concise recommendations - 1-2 sentences.
Consider dependencies and interactions between different parts of the code.

Generate a informative but concise compliance report using this format:

Replace the <span style="color: [COLOUR]"> with the appropriate hash code of the colour for the compliance status detailed below.
Yes = #00703c, No = #d4351c, Partially = #1d70b8

## Standard: [Standard Title from the standard text]

Compliant: <span style="color: [COLOUR]">**[Yes/No/Partially]**</span>

Relevant Files/Sections:
- [file/path/1]
- [file/path/2]

[Describe how the codebase implements or fails to implement this standard - keep this informative and concise]
[If partially compliant or non-compliant, explain specific issues - keep this informative and concise]

## [Standard Category 2]

[...repeat format for each standard...]

## Specific Recommendations

- [Describe specific change needed]
- [Additional action items as needed]
"""
    word_count = len(prompt.split())
    logger.debug(f"Generated prompt word count: {word_count}")
    return prompt


async def process_standards(
    standards: List[Dict[str, Any]],
    codebase_content: str
) -> List[str]:
    """Process each standard and generate compliance reports.

    Args:
        standards: List of standards to process
        codebase_content: Content of the codebase

    Returns:
        List of generated reports

    Raises:
        ReportGenerationError: If report generation fails
    """
    try:
        reports = []
        for idx, standard in enumerate(standards, 1):
            prompt = await generate_user_prompt(standard, codebase_content)
            logger.info(
                f"Starting compliance check {idx}/{len(standards)}: {standard['_id']}")

            report_text = await AnthropicClient.create_message(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT
            )

            reports.append(report_text)
            logger.debug(
                f"Completed standard {idx}/{len(standards)}: {standard['_id']}\n"
                f"Report length: {len(report_text)} chars\n"
                f"Preview: {report_text[:150]}..."
            )

            await asyncio.sleep(10)  # Rate limiting

        return reports

    except Exception as e:
        raise ReportGenerationError(
            f"Failed to generate reports: {str(e)}") from e


async def get_classification_names(
    classification_ids: List[str]
) -> List[str]:
    """Get classification names from database.

    Args:
        classification_ids: List of classification IDs

    Returns:
        List of classification names
    """
    db = await get_database()
    classification_obj_ids = [ObjectId(id) for id in classification_ids]
    classifications = await db.classifications.find(
        {"_id": {"$in": classification_obj_ids}}
    ).to_list(None)
    return [c.get('name', '') for c in classifications if c.get('name')]


async def generate_report_header(
    standard_set_name: str,
    classification_names: List[str]
) -> str:
    """Generate the header section of the report.

    Args:
        standard_set_name: Name of the standard set
        classification_names: List of classification names

    Returns:
        Generated header text
    """
    current_time = datetime.now().strftime("%d %B %Y %H:%M:%S")
    classifications_text = ", ".join(
        classification_names) if classification_names else "None"

    return f"""# {standard_set_name} Code Review
Date: {current_time}
Matched Classifications: {classifications_text}

"""


async def check_compliance(
    codebase_file: Path,
    standards: List[Dict[str, Any]],
    review_id: str,
    standard_set_name: str,
    matching_classification_ids: List[str]
) -> Path:
    """Check codebase compliance against standards using Anthropic's Claude.

    Args:
        codebase_file: Path to the codebase file
        standards: List of standards to check against
        review_id: Unique identifier for the review
        standard_set_name: Name of the standard set
        matching_classification_ids: List of matching classification IDs

    Returns:
        Path to the generated report file

    Raises:
        CodeReviewError: If compliance check fails
    """
    try:
        # Get classification names first to catch DB errors early
        classification_names = await get_classification_names(matching_classification_ids)

        config = CodeReviewConfig()
        filtered_standards = await filter_standards(standards, config)

        with open(codebase_file, 'r', encoding='utf-8') as f:
            codebase_content = f.read()
        logger.debug(
            f"Codebase content length: {len(codebase_content)} characters")

        reports = await process_standards(filtered_standards, codebase_content)
        logger.info(f"Generated {len(reports)} compliance reports")

        header = await generate_report_header(standard_set_name, classification_names)

        combined_report = header + "\n\n".join(reports)
        combined_report += "\n\n## Specific Recommendations\n\n"

        report_file = codebase_file.parent / \
            f"{review_id}-{standard_set_name}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(combined_report)

        logger.info(
            f"Completed compliance check for '{standard_set_name}', "
            f"saved {len(reports)} reports to {report_file}"
        )
        return report_file

    except Exception as e:
        raise CodeReviewError(f"Compliance check failed: {str(e)}") from e


async def process_code_review(review_id: str, repository_url: str, standard_sets: List[str]) -> None:
    """Process a code review in the background.

    Args:
        review_id: The ID of the code review
        repository_url: URL of the repository to analyze
        standard_sets: List of standard set IDs to check against

    Raises:
        ProcessingError: If processing fails
    """
    codebase_file = None
    try:
        logger.debug(
            f"Starting code review {review_id} for repository {repository_url}")

        # Get database connection
        db = await get_database()
        repo = CodeReviewRepository(db.code_reviews)

        # Update status to in progress
        await repo.update_status(review_id, ReviewStatus.IN_PROGRESS)

        # Process repository
        codebase_file = await process_repositories(repository_url)

        # Get all classifications
        raw_classifications = await db.classifications.find().to_list(None)
        classifications = [Classification.model_validate(
            doc) for doc in raw_classifications]

        # Analyze codebase to determine relevant classifications
        matching_classification_ids = await analyze_codebase_classifications(
            codebase_file.parent,
            classifications
        )

        # Process each standard set
        compliance_reports = []
        for standard_set_id in standard_sets:
            try:
                # Get standard set from database
                object_id = ensure_object_id(standard_set_id)
                if not object_id:
                    logger.error(
                        f"Invalid standard set ID format: {standard_set_id}")
                    continue

                standard_set = await db.standard_sets.find_one({"_id": object_id})
                if not standard_set:
                    logger.error(f"Standard set {standard_set_id} not found")
                    continue

                # Query for matching standards
                query = {
                    "standard_set_id": object_id,
                    "$or": [
                        *[{"classification_ids": obj_id}
                            for obj_id in matching_classification_ids],
                        {"$or": [
                            {"classification_ids": {"$size": 0}},
                            {"classification_ids": {"$exists": False}},
                            {"classification_ids": None}
                        ]}
                    ]
                }

                standards = await db.standards.find(query).to_list(None)
                if not standards:
                    logger.warning(
                        f"No matching standards found for standard set {standard_set_id}")
                    continue

                # Check compliance
                report_file = await check_compliance(
                    codebase_file,
                    standards,
                    review_id,
                    standard_set.get("name", "Unknown"),
                    matching_classification_ids
                )

                # Create compliance report
                compliance_reports.append({
                    "_id": ObjectId(),
                    "standard_set_name": standard_set.get("name", "Unknown"),
                    "file": str(report_file),
                    "report": report_file.read_text()
                })

            except Exception as e:
                logger.error(
                    f"Error processing standard set {standard_set_id}: {str(e)}")
                continue

        # Update the code review with compliance reports
        await repo.update_status(review_id, ReviewStatus.COMPLETED, compliance_reports)

    except Exception as e:
        logger.error(f"Error processing code review {review_id}: {str(e)}")
        await repo.update_status(review_id, ReviewStatus.FAILED)
        raise ProcessingError(
            f"Failed to process code review: {str(e)}") from e
    finally:
        if codebase_file and codebase_file.exists():
            try:
                codebase_file.unlink()
                logger.debug(f"Cleaned up temporary file: {codebase_file}")
            except Exception as e:
                logger.warning(
                    f"Failed to clean up temporary file {codebase_file}: {e}")
