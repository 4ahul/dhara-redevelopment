"""
Dhara AI — Profile Service
Business logic for user profile updates and media (avatar/portfolio) management.
Refactored for consistency with the new Service/CRUD architecture.
"""

import logging
import uuid
from typing import List

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models.user import PortfolioDocument, User
from orchestrator.schemas.profile import (
    PortfolioDocumentResponse,
    PortfolioUploadResponse,
    ProfileResponse,
    ProfileUpdate,
)
from orchestrator.services.cloudinary import (
    delete_file,
    upload_avatar,
    upload_portfolio,
)

logger = logging.getLogger(__name__)


class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_profile(self, user: User, req: ProfileUpdate) -> ProfileResponse:
        """Update user profile fields."""
        data = req.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")

        for k, v in data.items():
            setattr(user, k, v)

        await self.db.flush()
        await self.db.refresh(user)
        logger.info("Profile updated: %s", user.email)
        return ProfileResponse.model_validate(user)

    async def handle_portfolio_upload(
        self, user: User, file: UploadFile
    ) -> PortfolioUploadResponse:
        """Upload portfolio to Cloudinary and update user record."""
        result = await upload_portfolio(file)
        user.portfolio_url = result["secure_url"]
        await self.db.flush()
        await self.db.refresh(user)
        logger.info("Portfolio uploaded: %s", user.email)
        return PortfolioUploadResponse(
            portfolio_url=result["secure_url"],
            public_id=result["public_id"],
            format=result["format"],
            size_bytes=result["bytes"],
        )

    async def handle_avatar_upload(self, user: User, file: UploadFile) -> dict:
        """Upload avatar to Cloudinary and update user record."""
        result = await upload_avatar(file)
        user.avatar_url = result["secure_url"]
        await self.db.flush()
        await self.db.refresh(user)
        return {
            "status": "success",
            "avatar_url": result["secure_url"],
            "public_id": result["public_id"],
        }

    async def upload_multiple_portfolios(
        self, user: User, files: List[UploadFile]
    ) -> List[PortfolioDocumentResponse]:
        """Upload multiple portfolio files to Cloudinary, create PortfolioDocument records."""
        documents = []
        for file in files:
            result = await upload_portfolio(file)
            doc = PortfolioDocument(
                user_id=user.id,
                name=file.filename,
                url=result["secure_url"],
                public_id=result["public_id"],
                size_bytes=result["bytes"],
                format=result["format"],
                resource_type=result["resource_type"],
            )
            self.db.add(doc)
            documents.append(doc)
        await self.db.flush()
        for doc in documents:
            await self.db.refresh(doc)
        logger.info("Uploaded %d portfolio documents for %s", len(documents), user.email)
        return [PortfolioDocumentResponse.model_validate(doc) for doc in documents]

    async def list_portfolio_documents(self, user: User) -> List[PortfolioDocumentResponse]:
        """List all portfolio documents for the user, ordered by upload date descending."""
        stmt = (
            select(PortfolioDocument)
            .where(PortfolioDocument.user_id == user.id)
            .order_by(PortfolioDocument.uploaded_at.desc())
        )
        result = await self.db.execute(stmt)
        docs = result.scalars().all()
        return [PortfolioDocumentResponse.model_validate(doc) for doc in docs]

    async def delete_portfolio_document(self, user: User, document_id: uuid.UUID) -> bool:
        """Delete a portfolio document from Cloudinary and the database."""
        stmt = select(PortfolioDocument).where(
            PortfolioDocument.id == document_id,
            PortfolioDocument.user_id == user.id,
        )
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Portfolio document not found")
        # Delete from Cloudinary
        delete_file(doc.public_id, resource_type=doc.resource_type)
        # Delete from DB
        await self.db.delete(doc)
        await self.db.flush()
        logger.info("Deleted portfolio document %s for %s", document_id, user.email)
        return True
