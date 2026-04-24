"""
Dhara AI — Landing Page Service
Handles CMS content and public form submissions.
Refactored to use CRUD layer.
"""

import logging

from fastapi import BackgroundTasks
from repositories import enquiry_repository, landing_repository
from schemas.landing import (
    ContactRequestSchema,
    FormSubmissionResponse,
    GetStartedRequestSchema,
    LandingPageResponse,
    LandingPageSection,
)
from sqlalchemy.ext.asyncio import AsyncSession

from services.email import (
    send_admin_notification,
    send_contact_confirmation,
    send_get_started_confirmation,
)

logger = logging.getLogger(__name__)

DEFAULT_SECTIONS = [
    {"section": "hero", "title": "AI-Powered Redevelopment Feasibility Reports", "subtitle": "Instant professional feasibility analysis for Mumbai housing society redevelopment", "cta_text": "Get Started", "cta_url": "/get-started", "display_order": 1},
    {"section": "features", "title": "Why Choose Dhara AI?", "subtitle": "Automated analysis powered by Mumbai's regulatory data", "content": "Automated Site Analysis|NOCAS Height Verification|DCPR 2034 Regulation Engine|Ready Reckoner Rate Integration|Professional Excel Reports|PR Card & DP Remark Extraction", "display_order": 2},
    {"section": "how_it_works", "title": "How It Works", "content": "1. Enter society details|2. AI agent analyses regulations and financials|3. Download your professional feasibility report", "display_order": 3},
    {"section": "cta", "title": "Ready to Transform Your Feasibility Analysis?", "cta_text": "Start Free Trial", "cta_url": "/signup", "display_order": 4},
]


class LandingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_landing_page(self) -> LandingPageResponse:
        """Fetch active landing page sections or initialize with defaults."""
        rows = await landing_repository.list_active_landing_content(self.db)

        if not rows:
            # Seed defaults if empty
            for d in DEFAULT_SECTIONS:
                await landing_repository.create_landing_content(self.db, {**d, "is_active": True})
            rows = await landing_repository.list_active_landing_content(self.db)

        sections = [
            LandingPageSection(
                section=r.section,
                title=r.title,
                subtitle=r.subtitle,
                content=r.content,
                media_url=r.media_url,
                cta_text=r.cta_text,
                cta_url=r.cta_url,
                display_order=r.display_order
            ) for r in rows
        ]

        return LandingPageResponse(sections=sections)

    async def submit_get_started(self, req: GetStartedRequestSchema, bg: BackgroundTasks) -> FormSubmissionResponse:
        """Handle 'Get Started' form submission."""
        data = req.model_dump(exclude_unset=True)
        entry = await enquiry_repository.create_get_started_request(self.db, data)

        ref = str(entry.id)[:8].upper()
        bg.add_task(send_get_started_confirmation, req.email, req.name, ref, req.society_name)
        bg.add_task(send_admin_notification, req.name, req.email, req.message or f"Get Started from {req.name}", ref, "Get Started Request", req.phone, society_name=req.society_name)

        logger.info("Get Started Submission: %s <%s>", req.name, req.email)
        return FormSubmissionResponse(message="Thank you! We'll contact you within 24 hours.", reference_id=ref)

    async def submit_contact(self, req: ContactRequestSchema, bg: BackgroundTasks) -> FormSubmissionResponse:
        """Handle 'Contact Us' form submission."""
        data = req.model_dump(exclude_unset=True)
        data["source"] = "contact_form"
        enquiry = await enquiry_repository.create_enquiry(self.db, data)

        ref = str(enquiry.id)[:8].upper()
        bg.add_task(send_contact_confirmation, req.email, req.name, ref, req.subject)
        bg.add_task(send_admin_notification, req.name, req.email, req.message, ref, "Contact Form", req.phone, req.subject)

        logger.info("Contact Us Submission: %s <%s>", req.name, req.email)
        return FormSubmissionResponse(message="Thank you! We'll respond within 1-2 business days.", reference_id=ref)


