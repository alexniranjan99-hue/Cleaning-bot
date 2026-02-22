import motor.motor_asyncio
from datetime import datetime
from typing import Optional, List, Dict
import logging
import uuid

from models import User, Transaction, Report, TokenPackage
import config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        
    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGODB_URI)
            self.db = self.client[config.DATABASE_NAME]
            
            # Create indexes
            await self.db.users.create_index("user_id", unique=True)
            await self.db.transactions.create_index("transaction_id", unique=True)
            await self.db.reports.create_index("report_id", unique=True)
            await self.db.reports.create_index([("user_id", 1), ("created_at", -1)])
            
            # Initialize token packages if not exist
            await self.init_token_packages()
            
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    async def init_token_packages(self):
        """Initialize default token packages"""
        packages = [
            {
                "package_id": "basic",
                "name": "Basic Pack",
                "tokens": 5,
                "price_stars": 50,
                "price_inr": 50
            },
            {
                "package_id": "standard",
                "name": "Standard Pack",
                "tokens": 15,
                "price_stars": 120,
                "price_inr": 120
            },
            {
                "package_id": "premium",
                "name": "Premium Pack",
                "tokens": 30,
                "price_stars": 200,
                "price_inr": 200
            },
            {
                "package_id": "pro",
                "name": "Pro Pack",
                "tokens": 100,
                "price_stars": 500,
                "price_inr": 500
            }
        ]
        
        for package in packages:
            existing = await self.db.token_packages.find_one({"package_id": package["package_id"]})
            if not existing:
                await self.db.token_packages.insert_one(package)
    
    # User methods
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        user_data = await self.db.users.find_one({"user_id": user_id})
        if user_data:
            return User(**user_data)
        return None
    
    async def create_user(self, user_id: int, username: str, first_name: str, last_name: str = None) -> User:
        """Create new user"""
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            tokens=config.FREE_REPORTS_FOR_NEW_USERS
        )
        await self.db.users.insert_one(user.__dict__)
        return user
    
    async def update_user_tokens(self, user_id: int, tokens_change: int) -> bool:
        """Update user tokens (positive for add, negative for deduct)"""
        result = await self.db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"tokens": tokens_change}}
        )
        return result.modified_count > 0
    
    async def add_report_count(self, user_id: int):
        """Increment user's report count"""
        await self.db.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {"total_reports": 1},
                "$set": {"last_report_date": datetime.now()}
            }
        )
    
    # Transaction methods
    async def create_transaction(self, user_id: int, amount: float, currency: str, 
                                tokens: int, payment_method: str) -> Transaction:
        """Create a new transaction"""
        transaction = Transaction(
            transaction_id=str(uuid.uuid4()),
            user_id=user_id,
            amount=amount,
            currency=currency,
            tokens_purchased=tokens,
            payment_method=payment_method,
            status="pending"
        )
        await self.db.transactions.insert_one(transaction.__dict__)
        return transaction
    
    async def complete_transaction(self, transaction_id: str) -> bool:
        """Mark transaction as completed"""
        result = await self.db.transactions.update_one(
            {"transaction_id": transaction_id},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": datetime.now()
                }
            }
        )
        return result.modified_count > 0
    
    # Report methods
    async def create_report(self, user_id: int, report_type: str, target: str, 
                           reason: str, details: str, tokens_used: int = 1) -> Report:
        """Create a new report"""
        report = Report(
            report_id=str(uuid.uuid4()),
            user_id=user_id,
            report_type=report_type,
            target=target,
            reason=reason,
            details=details,
            status="pending",
            tokens_used=tokens_used
        )
        await self.db.reports.insert_one(report.__dict__)
        return report
    
    async def get_user_reports(self, user_id: int, limit: int = 10) -> List[Report]:
        """Get user's recent reports"""
        cursor = self.db.reports.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
        reports = []
        async for doc in cursor:
            reports.append(Report(**doc))
        return reports
    
    # Token packages
    async def get_token_packages(self) -> List[TokenPackage]:
        """Get all active token packages"""
        cursor = self.db.token_packages.find({"is_active": True})
        packages = []
        async for doc in cursor:
            packages.append(TokenPackage(**doc))
        return packages
    
    async def get_package(self, package_id: str) -> Optional[TokenPackage]:
        """Get package by ID"""
        package_data = await self.db.token_packages.find_one({"package_id": package_id})
        if package_data:
            return TokenPackage(**package_data)
        return None
    
    # Admin methods
    async def get_all_reports(self, status: str = None, limit: int = 50) -> List[Report]:
        """Get all reports (for admin)"""
        query = {"status": status} if status else {}
        cursor = self.db.reports.find(query).sort("created_at", -1).limit(limit)
        reports = []
        async for doc in cursor:
            reports.append(Report(**doc))
        return reports
    
    async def update_report_status(self, report_id: str, status: str, reviewed_by: int) -> bool:
        """Update report status"""
        result = await self.db.reports.update_one(
            {"report_id": report_id},
            {
                "$set": {
                    "status": status,
                    "reviewed_by": reviewed_by,
                    "reviewed_at": datetime.now()
                }
            }
        )
        return result.modified_count > 0

# Global database instance
db = Database()
