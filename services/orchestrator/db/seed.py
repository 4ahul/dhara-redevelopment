"""
Dhara AI — Database Seeder
Seeds default admin user and roles on first run.
"""

import logging
import os

from sqlalchemy import func, select

from services.orchestrator.core.security import hash_password
from services.orchestrator.db import async_session_factory

logger = logging.getLogger(__name__)


async def seed_defaults():
    """Create default admin user and roles if tables are empty."""
    from services.orchestrator.models import Role, Society, User
    from services.orchestrator.models.enums import UserRole

    async with async_session_factory() as db:
        # ── Seed admin user ──────────────────────────────
        user_count = (await db.execute(select(func.count()).select_from(User))).scalar()
        if user_count == 0:
            admin = User(
                email="admin@dharaai.com",
                name="Dhara AI Admin",
                role=UserRole.ADMIN,
                password_hash=hash_password(os.getenv("INITIAL_ADMIN_PASSWORD", "admin@123")),
                is_active=True,
            )
            db.add(admin)
            logger.info("Default admin seeded: admin@dharaai.com / admin@123")

        # ── Seed default roles ───────────────────────────
        role_count = (await db.execute(select(func.count()).select_from(Role))).scalar()
        if role_count == 0:
            defaults = [
                ("admin", "Administrator", "Full system access", {"all": True}),
                (
                    "pmc",
                    "PMC Consultant",
                    "Report generation and team management",
                    {"societies": True, "reports": True, "team": True},
                ),
                (
                    "society",
                    "Society Member",
                    "Housing society representative",
                    {"view_reports": True},
                ),
                (
                    "builder",
                    "Builder",
                    "Construction company representative",
                    {"view_tenders": True, "bid": True},
                ),
                (
                    "lawyer",
                    "Lawyer",
                    "Legal consultant for redevelopment",
                    {"view_reports": True, "legal_review": True},
                ),
                ("viewer", "Viewer", "Read-only access", {"view": True}),
            ]
            for name, display, desc, perms in defaults:
                db.add(Role(name=name, display_name=display, description=desc, permissions=perms))
            logger.info("Default roles seeded")

        # ── Seed sample society ──────────────────────────
        name = "Prabhadevi Heights CHS"
        exists = (await db.execute(select(Society).filter(Society.name == name))).scalar()

        if not exists:
            admin = (
                await db.execute(select(User).filter(User.email == "admin@dharaai.com"))
            ).scalar()
            if admin:
                prabhadevi = Society(
                    name=name,
                    address="FP No. 1128, TPS IV, Sayani Road, Prabhadevi, Mumbai - 400025",
                    ward="G/S",
                    cts_no="1/1128",
                    plot_area_sqm=1540.50,
                    sale_rate=55000.0,
                    created_by=admin.id,
                )
                db.add(prabhadevi)
                logger.info(f"Sample society seeded: {name}")

        await db.commit()
