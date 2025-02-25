"""Service layer for code review operations.

This service orchestrates the code review process by:
- Managing the review lifecycle
- Validating inputs and standard sets
- Initiating background processing via the code reviews agent
- Providing access to review results
"""
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from multiprocessing import Process
from app.models.code_review import CodeReview, CodeReviewCreate, ReviewStatus, CodeReviewList
from app.repositories.code_review_repo import CodeReviewRepository
from app.agents.code_reviews_agent import process_code_review
from app.common.logging import get_logger
from app.utils.id_validation import ensure_object_id
from app.utils.process_utils import run_async_in_process

logger = get_logger(__name__)


def _run_in_process(review_id: str, repository_url: str, standard_sets: List[str]) -> None:
    """Run the code review process in a separate process.

    Args:
        review_id: The ID of the code review
        repository_url: URL of the repository to analyze
        standard_sets: List of standard set IDs to check against
    """
    run_async_in_process(process_code_review, review_id, repository_url, standard_sets)


class CodeReviewService:
    """Service for managing code reviews."""

    def __init__(self, db: AsyncIOMotorDatabase, repo: CodeReviewRepository):
        """Initialize service with database and repository."""
        self.db = db
        self.repo = repo

    async def create_review(self, code_review: CodeReviewCreate) -> CodeReview:
        """Create a new code review and start the review process."""
        # Validate standard sets exist before creating review
        for standard_set_id in code_review.standard_sets:
            object_id = ensure_object_id(standard_set_id)
            if not object_id:
                raise ValueError(
                    f"Invalid standard set ID format: {standard_set_id}")

            standard_set = await self.db.standard_sets.find_one({"_id": object_id})
            if not standard_set:
                raise ValueError(f"Standard set {standard_set_id} not found")

        created_review = await self.repo.create(code_review)

        # Start agent in separate process
        Process(
            target=_run_in_process,
            args=(str(created_review.id), code_review.repository_url,
                  code_review.standard_sets)
        ).start()

        return created_review

    async def get_all_reviews(self, status: Optional[ReviewStatus] = None) -> List[CodeReviewList]:
        """Get all code reviews.

        Args:
            status: Optional filter by review status
        """
        return await self.repo.get_all(status=status)

    async def get_review_by_id(self, review_id: str) -> CodeReview:
        """Get a specific code review."""
        return await self.repo.get_by_id(review_id)
