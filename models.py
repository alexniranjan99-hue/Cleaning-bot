from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field

@dataclass
class User:
    user_id: int
    username: Optional[str]
    first_name: str
    last_name: Optional[str] = None
    tokens: int = 0
    total_reports: int = 0
    joined_date: datetime = field(default_factory=datetime.now)
    last_report_date: Optional[datetime] = None
    is_blocked: bool = False
    
@dataclass
class Transaction:
    transaction_id: str
    user_id: int
    amount: float
    currency: str  # 'STARS' or 'INR'
    tokens_purchased: int
    payment_method: str  # 'stars' or 'upi'
    status: str  # 'pending', 'completed', 'failed'
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

@dataclass
class Report:
    report_id: str
    user_id: int
    report_type: str  # 'user', 'group', 'channel'
    target: str  # username or link
    reason: str
    details: str
    status: str  # 'pending', 'reviewed', 'resolved', 'rejected'
    created_at: datetime = field(default_factory=datetime.now)
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    tokens_used: int = 1

@dataclass
class TokenPackage:
    package_id: str
    name: str
    tokens: int
    price_stars: int
    price_inr: int
    is_active: bool = True
