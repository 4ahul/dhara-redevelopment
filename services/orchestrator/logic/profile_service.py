"""
Dhara AI — Profile Service
Business logic for user profile updates and media (avatar/portfolio) management.
Refactored for consistency with the new Service/CRUD architecture.
"""

import logging

from fastapi import HTTPException, UploadFile
from services.orchestrator.models.user import User
from services.orchestrator.schemas.profile import PortfolioUploadResponse, ProfileResponse, ProfileUpdate
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.logic.cloudinary import upload_avatar, upload_portfolio

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

    async def handle_portfolio_upload(self, user: User, file: UploadFile) -> PortfolioUploadResponse:
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
            size_bytes=result["bytes"]
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
            "public_id": result["public_id"]
        }




