import motor.motor_asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
import uuid
from bson import ObjectId

from models import *
import config
from utils import encrypt_data, decrypt_data

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
            await self.db.accounts.create_index([("user_id", 1), ("account_id", 1)], unique=True)
            await self.db.sessions.create_index("session_id", unique=True)
            await self.db.sessions.create_index("expires_at", expireAfterSeconds=0)
            await self.db.transactions.create_index("transaction_id", unique=True)
            await self.db.reports.create_index("report_id", unique=True)
            await self.db.reports.create_index([("user_id", 1), ("created_at", -1)])
            
            # Initialize data
            await self.init_token_packages()
            await self.init_report_templates()
            
            logger.info("Database connected successfully")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    async def init_token_packages(self):
        """Initialize default token packages"""
        packages = [
            {
                "package_id": "basic",
                "name": "Basic Pack",
                "tokens": 5,
                "price_stars": 50,
                "price_inr": 50,
                "description": "5 reports - Best for testing"
            },
            {
                "package_id": "standard",
                "name": "Standard Pack",
                "tokens": 15,
                "price_stars": 120,
                "price_inr": 120,
                "description": "15 reports - Most popular"
            },
            {
                "package_id": "premium",
                "name": "Premium Pack",
                "tokens": 30,
                "price_stars": 200,
                "price_inr": 200,
                "description": "30 reports - Great value"
            },
            {
                "package_id": "pro",
                "name": "Pro Pack",
                "tokens": 100,
                "price_stars": 500,
                "price_inr": 500,
                "description": "100 reports - For power users"
            }
        ]
        
        for package in packages:
            existing = await self.db.token_packages.find_one({"package_id": package["package_id"]})
            if not existing:
                await self.db.token_packages.insert_one(package)
    
    async def init_report_templates(self):
        """Initialize default report templates"""
        templates = [
            {
                "template_id": "spam",
                "name": "Spam Report",
                "category": "spam",
                "content": "This account is sending spam messages including promotional content and unwanted advertisements.",
                "created_by": 0,
                "is_public": True
            },
            {
                "template_id": "scam",
                "name": "Scam Report",
                "category": "scam",
                "content": "This account is attempting to scam users by promising fake rewards and requesting personal information.",
                "created_by": 0,
                "is_public": True
            },
            {
                "template_id": "harassment",
                "name": "Harassment Report",
                "category": "harassment",
                "content": "This user is engaging in harassment, bullying, and making threats against others.",
                "created_by": 0,
                "is_public": True
            }
        ]
        
        for template in templates:
            existing = await self.db.report_templates.find_one({"template_id": template["template_id"]})
            if not existing:
                await self.db.report_templates.insert_one(template)
    
    # User methods
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        user_data = await self.db.users.find_one({"user_id": user_id})
        if user_data:
            # Convert role string to enum
            if "role" in user_data and isinstance(user_data["role"], str):
                user_data["role"] = UserRole(user_data["role"])
            return User(**user_data)
        return None
    
    async def create_user(self, user_id: int, username: str, first_name: str, 
                         last_name: str = None, referred_by: int = None) -> User:
        """Create new user"""
        # Determine role
        role = UserRole.NORMAL
        if user_id in config.OWNER_IDS:
            role = UserRole.OWNER
        elif user_id in config.ADMIN_IDS:
            role = UserRole.ADMIN
        elif user_id == config.SUPER_ADMIN_ID:
            role = UserRole.SUPER_ADMIN
            
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=role,
            tokens=config.FREE_REPORTS_FOR_NEW_USERS,
            referred_by=referred_by
        )
        
        # Convert enum to string for storage
        user_dict = user.__dict__.copy()
        user_dict["role"] = user_dict["role"].value
        
        await self.db.users.insert_one(user_dict)
        return user
    
    async def update_user_role(self, user_id: int, role: UserRole) -> bool:
        """Update user role"""
        result = await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"role": role.value}}
        )
        return result.modified_count > 0
    
    async def update_user_tokens(self, user_id: int, tokens_change: int) -> bool:
        """Update user tokens"""
        result = await self.db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"tokens": tokens_change}}
        )
        return result.modified_count > 0
    
    # Account management methods
    async def add_telegram_account(self, user_id: int, phone_number: str, 
                                  session_string: str, account_name: str,
                                  twofa_password: str = None) -> TelegramAccount:
        """Add a new Telegram account for reporting"""
        # Check account limit
        account_count = await self.db.accounts.count_documents({"user_id": user_id})
        if account_count >= config.MAX_ACCOUNTS_PER_USER:
            raise Exception(f"Maximum accounts limit reached ({config.MAX_ACCOUNTS_PER_USER})")
        
        # Encrypt sensitive data
        encrypted_session = encrypt_data(session_string)
        encrypted_2fa = encrypt_data(twofa_password) if twofa_password else None
        
        account = TelegramAccount(
            account_id=str(uuid.uuid4()),
            user_id=user_id,
            phone_number=phone_number,
            session_string=encrypted_session,
            account_name=account_name,
            twofa_password=encrypted_2fa,
            is_primary=(account_count == 0)  # First account is primary
        )
        
        await self.db.accounts.insert_one(account.__dict__)
        return account
    
    async def get_user_accounts(self, user_id: int) -> List[TelegramAccount]:
        """Get all accounts for a user"""
        cursor = self.db.accounts.find({"user_id": user_id, "status": AccountStatus.ACTIVE.value})
        accounts = []
        async for doc in cursor:
            # Convert status string to enum
            if "status" in doc and isinstance(doc["status"], str):
                doc["status"] = AccountStatus(doc["status"])
            accounts.append(TelegramAccount(**doc))
        return accounts
    
    async def get_account(self, account_id: str) -> Optional[TelegramAccount]:
        """Get account by ID"""
        account_data = await self.db.accounts.find_one({"account_id": account_id})
        if account_data:
            if "status" in account_data and isinstance(account_data["status"], str):
                account_data["status"] = AccountStatus(account_data["status"])
            return TelegramAccount(**account_data)
        return None
    
    async def update_account_status(self, account_id: str, status: AccountStatus) -> bool:
        """Update account status"""
        result = await self.db.accounts.update_one(
            {"account_id": account_id},
            {"$set": {"status": status.value}}
        )
        return result.modified_count > 0
    
    async def set_primary_account(self, user_id: int, account_id: str) -> bool:
        """Set an account as primary"""
        # Remove primary from all accounts
        await self.db.accounts.update_many(
            {"user_id": user_id},
            {"$set": {"is_primary": False}}
        )
        
        # Set new primary
        result = await self.db.accounts.update_one(
            {"account_id": account_id, "user_id": user_id},
            {"$set": {"is_primary": True}}
        )
        return result.modified_count > 0
    
    # Session management
    async def create_session(self, user_id: int, account_id: str) -> ActiveSession:
        """Create an active session"""
        session = ActiveSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            account_id=account_id,
            expires_at=datetime.now() + timedelta(seconds=config.SESSION_TIMEOUT)
        )
        await self.db.sessions.insert_one(session.__dict__)
        return session
    
    async def get_active_session(self, session_id: str) -> Optional[ActiveSession]:
        """Get active session"""
        session_data = await self.db.sessions.find_one({
            "session_id": session_id,
            "expires_at": {"$gt": datetime.now()}
        })
        if session_data:
            return ActiveSession(**session_data)
        return None
    
    async def end_session(self, session_id: str) -> bool:
        """End a session"""
        result = await self.db.sessions.delete_one({"session_id": session_id})
        return result.deleted_count > 0
    
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
    
    async def complete_transaction(self, transaction_id: str, payment_details: Dict = None) -> bool:
        """Mark transaction as completed"""
        update_data = {
            "$set": {
                "status": "completed",
                "completed_at": datetime.now()
            }
        }
        if payment_details:
            update_data["$set"]["payment_details"] = payment_details
            
        result = await self.db.transactions.update_one(
            {"transaction_id": transaction_id},
            update_data
        )
        return result.modified_count > 0
    
    # Report methods
    async def create_report(self, user_id: int, account_id: str, report_type: str,
                          target: str, reason: str, details: str,
                          tokens_used: int = 1, evidence: List[str] = None) -> Report:
        """Create a new report"""
        report = Report(
            report_id=str(uuid.uuid4()),
            user_id=user_id,
            account_id=account_id,
            report_type=report_type,
            target=target,
            reason=reason,
            details=details,
            status=ReportStatus.PENDING,
            tokens_used=tokens_used,
            evidence=evidence or []
        )
        
        report_dict = report.__dict__.copy()
        report_dict["status"] = report_dict["status"].value
        
        await self.db.reports.insert_one(report_dict)
        
        # Update account usage
        await self.db.accounts.update_one(
            {"account_id": account_id},
            {"$inc": {"total_reports_used": 1}, "$set": {"last_used": datetime.now()}}
        )
        
        return report
    
    async def get_user_reports(self, user_id: int, page: int = 1) -> List[Report]:
        """Get user's reports with pagination"""
        skip = (page - 1) * config.REPORTS_PER_PAGE
        cursor = self.db.reports.find({"user_id": user_id})\
                               .sort("created_at", -1)\
                               .skip(skip)\
                               .limit(config.REPORTS_PER_PAGE)
        
        reports = []
        async for doc in cursor:
            if "status" in doc and isinstance(doc["status"], str):
                doc["status"] = ReportStatus(doc["status"])
            reports.append(Report(**doc))
        return reports
    
    async def get_pending_reports(self, limit: int = 50) -> List[Report]:
        """Get pending reports for admin"""
        cursor = self.db.reports.find({"status": ReportStatus.PENDING.value})\
                               .sort("created_at", 1)\
                               .limit(limit)
        
        reports = []
        async for doc in cursor:
            doc["status"] = ReportStatus(doc["status"])
            reports.append(Report(**doc))
        return reports
    
    async def update_report_status(self, report_id: str, status: ReportStatus,
                                  reviewed_by: int, result: str = None) -> bool:
        """Update report status"""
        update_data = {
            "$set": {
                "status": status.value,
                "reviewed_by": reviewed_by,
                "reviewed_at": datetime.now()
            }
        }
        if result:
            update_data["$set"]["result"] = result
            
        result = await self.db.reports.update_one(
            {"report_id": report_id},
            update_data
        )
        return result.modified_count > 0
    
    # Template methods
    async def get_templates(self, category: str = None) -> List[ReportTemplate]:
        """Get report templates"""
        query = {"is_public": True}
        if category:
            query["category"] = category
            
        cursor = self.db.report_templates.find(query)
        templates = []
        async for doc in cursor:
            templates.append(ReportTemplate(**doc))
        return templates
    
    async def create_template(self, template: ReportTemplate) -> bool:
        """Create a custom template"""
        result = await self.db.report_templates.insert_one(template.__dict__)
        return result.inserted_id is not None

# Global database instance
db = Database()