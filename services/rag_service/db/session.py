import logging
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from ..core.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Database Config ---
DATABASE_URL = settings.DATABASE_URL

# Convert async URL if passed incorrectly
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Models ---


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    clerk_id = Column(String(255), unique=True, index=True, nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    username = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    auth_provider = Column(String(50), default="email")
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "sessions"
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    title = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False)
    last_message_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), index=True)
    role = Column(String(20))  # user, assistant
    content = Column(Text)
    sources = Column(Text, nullable=True)
    clauses = Column(Text, nullable=True)
    extra_data = Column(Text, nullable=True)
    feedback = Column(String(20), nullable=True)
    edited_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FeedbackLog(Base):
    __tablename__ = "feedback_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
    session_id = Column(String(36), nullable=False)
    feedback_type = Column(String(20))
    original_content = Column(Text, nullable=True)
    new_content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes the database schema and creates a default system and admin user."""
    try:
        from ..routers.auth_router import hash_password

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            # 1. Internal System User
            system_email = "system@dhara.local"
            if not db.query(User).filter(User.email == system_email).first():
                db.add(
                    User(
                        id="00000000-0000-0000-0000-000000000000",
                        email=system_email,
                        username="system",
                        full_name="System User",
                        auth_provider="system",
                        is_active=True,
                        is_verified=True,
                    )
                )

            # 2. Default Admin User for UI Login
            admin_email = "admin@dhara.local"
            if not db.query(User).filter(User.email == admin_email).first():
                db.add(
                    User(
                        id="00000000-0000-0000-0000-000000000001",
                        email=admin_email,
                        username="admin",
                        full_name="Admin User",
                        hashed_password=hash_password("admin1234"),
                        auth_provider="email",
                        is_active=True,
                        is_verified=True,
                    )
                )

            db.commit()
            logger.info("Database initialized with default users.")
        except Exception as e:
            logger.error(f"Error creating system user: {e}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Schema creation failed: {e}")
