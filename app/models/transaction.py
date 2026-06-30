import uuid
from sqlalchemy import Column, String, Float, Boolean, Text, ForeignKey, JSON, Integer
from app.core.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id           = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)
    txn_id           = Column(String, nullable=True)
    date             = Column(String, nullable=True)
    merchant         = Column(String, nullable=True)
    amount           = Column(Float,  nullable=True)
    currency         = Column(String, nullable=True)
    status           = Column(String, nullable=True)
    category         = Column(String, nullable=True)
    account_id       = Column(String, nullable=True)
    notes            = Column(Text,   nullable=True)
    is_anomaly       = Column(Boolean, default=False)
    anomaly_reason   = Column(Text,    nullable=True)
    llm_category     = Column(String,  nullable=True)
    llm_raw_response = Column(Text,    nullable=True)
    llm_failed       = Column(Boolean, default=False)


class JobSummary(Base):
    __tablename__ = "job_summaries"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id          = Column(String, ForeignKey("jobs.id"), nullable=False, unique=True)
    total_spend_inr = Column(Float,   default=0.0)
    total_spend_usd = Column(Float,   default=0.0)
    top_merchants   = Column(JSON,    nullable=True)
    anomaly_count   = Column(Integer, default=0)
    narrative       = Column(Text,    nullable=True)
    risk_level      = Column(String,  nullable=True)