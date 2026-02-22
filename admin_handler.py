import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta

from database import db
from models import UserRole, ReportStatus
import config

logger = logging.getLogger(__name__)

class AdminHandler:
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin panel"""
        user_id = update.effective_user.id
        
        # Check if user is admin/owner
        if user_id not in config.ADMIN_IDS and user_id not in config.OWNER_IDS and user_id != config.SUPER_ADMIN_ID:
            await update.message.reply_text("❌ Unauthorized access.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Pending Reports", callback_data="admin_pending")],
            [InlineKeyboardButton("👥 User Management", callback_data="admin_users")],
            [InlineKeyboardButton("💰 Token Management", callback_data="admin_tokens")],
            [InlineKeyboardButton("📈 Statistics", callback_data="admin_stats")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")]
        ]
        
        if user_id == config.SUPER_ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👑 Super Admin", callback_data="admin_super")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👑 **Admin Control Panel**\n\n"
            "Select an option:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin panel callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "admin_pending":
            await self.show_pending_reports(update, context)
        elif data == "admin_users":
            await self.user_management(update, context)
        elif data == "admin_tokens":
            await self.token_management(update, context)
        elif data == "admin_stats":
            await self.show_statistics(update, context)
        elif data == "admin_settings":
            await self.bot_settings(update, context)
        elif data == "admin_super":
            await self.super_admin_panel(update, context)
        elif data.startswith("review_"):
            await self.review_report(update, context)
    
    async def show_pending_reports(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending reports for review"""
        query = update.callback_query
        
        reports = await db.get_pending_reports(limit=10)
        
        if not reports:
            await query.edit_message_text(
                "✅ No pending reports to review.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="admin_back")
                ]])
            )
            return
        
        message = "📋 **Pending Reports**\n\n"
        keyboard = []
        
        for report in reports[:5]:
            message += f"**ID:** `{report.report_id[:8]}...`\n"
            message += f"**Type:** {report.report_type}\n"
            message += f"**Target:** {report.target}\n"
            message += f"**User:** {report.user_id}\n"
            message += f"**Time:** {report.created_at.strftime('%H:%M %d/%m')}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"Review #{report.report_id[:8]}",
                    callback_data=f"review_{report.report_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def review_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Review a specific report"""
        query = update.callback_query
        report_id = query.data.replace("review_", "")
        
        report = await db.get_report(report_id)
        if not report:
            await query.edit_message_text("❌ Report not found.")
            return
        
        message = (
            f"📋 **Report Review**\n\n"
            f"**Report ID:** `{report.report_id}`\n"
            f"**User ID:** `{report.user_id}`\n"
            f"**Account:** {report.account_id}\n"
            f"**Type:** {report.report_type}\n"
            f"**Target:** {report.target}\n"
            f"**Reason:** {report.reason}\n"
            f"**Details:** {report.details}\n"
            f"**Submitted:** {report.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"**Actions:**"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Resolve", callback_data=f"resolve_{report_id}"),
                InlineKeyboardButton("👀 Mark Reviewed", callback_data=f"reviewed_{report_id}")
            ],
            [
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{report_id}"),
                InlineKeyboardButton("📌 Add Note", callback_data=f"note_{report_id}")
            ],
            [InlineKeyboardButton("🔙 Back to List", callback_data="admin_pending")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def user_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """User management interface"""
        query = update.callback_query
        
        # Get user count
        total_users = await db.db.users.count_documents({})
        active_today = await db.db.users.count_documents({
            "last_active": {"$gte": datetime.now() - timedelta(days=1)}
        })
        
        message = (
            f"👥 **User Management**\n\n"
            f"Total Users: {total_users}\n"
            f"Active Today: {active_today}\n\n"
            f"**Options:**"
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 List Users", callback_data="list_users")],
            [InlineKeyboardButton("🔍 Search User", callback_data="search_user")],
            [InlineKeyboardButton("👑 Manage Admins", callback_data="manage_admins")],
            [InlineKeyboardButton("🚫 Blocked Users", callback_data="blocked_users")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def token_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Token management interface"""
        query = update.callback_query
        
        message = "💰 **Token Management**\n\nSelect an option:"
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Tokens to User", callback_data="add_tokens")],
            [InlineKeyboardButton("📊 Token Packages", callback_data="manage_packages")],
            [InlineKeyboardButton("📈 Token Stats", callback_data="token_stats")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show bot statistics"""
        query = update.callback_query
        
        # Gather statistics
        total_users = await db.db.users.count_documents({})
        total_reports = await db.db.reports.count_documents({})
        pending_reports = await db.db.reports.count_documents({"status": ReportStatus.PENDING.value})
        total_tokens_sold = await db.db.transactions.aggregate([
            {"$match": {"status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$tokens_purchased"}}}
        ]).to_list(length=1)
        
        tokens_sold = total_tokens_sold[0]['total'] if total_tokens_sold else 0
        
        # Get today's stats
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        reports_today = await db.db.reports.count_documents({
            "created_at": {"$gte": today_start}
        })
        
        message = (
            f"📊 **Bot Statistics**\n\n"
            f"**Users:** {total_users}\n"
            f"**Total Reports:** {total_reports}\n"
            f"**Pending Reports:** {pending_reports}\n"
            f"**Reports Today:** {reports_today}\n"
            f"**Tokens Sold:** {tokens_sold}\n\n"
            f"**Report Types:**\n"
        )
        
        # Get report types breakdown
        pipeline = [
            {"$group": {"_id": "$report_type", "count": {"$sum": 1}}}
        ]
        report_types = await db.db.reports.aggregate(pipeline).to_list(length=10)
        
        for rt in report_types:
            message += f"• {rt['_id']}: {rt['count']}\n"
        
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="admin_stats"),
                     InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def bot_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot settings interface"""
        query = update.callback_query
        
        message = (
            f"⚙️ **Bot Settings**\n\n"
            f"Current Configuration:\n"
            f"• Token Price: {config.TOKEN_PRICE_STARS} Stars / ₹{config.TOKEN_PRICE_INR}\n"
            f"• Report Cost: {config.REPORT_COST_IN_TOKENS} tokens\n"
            f"• Free Reports: {config.FREE_REPORTS_FOR_NEW_USERS}\n"
            f"• Max Accounts/User: {config.MAX_ACCOUNTS_PER_USER}\n\n"
            f"**Contact Info:**\n"
            f"• Admin: @{config.CONTACT_INFO['admin_username']}\n"
            f"• Owner: @{config.CONTACT_INFO['owner_username']}\n"
            f"• Support: {config.CONTACT_INFO['support_group']}"
        )
        
        keyboard = [
            [InlineKeyboardButton("📝 Edit Settings", callback_data="edit_settings")],
            [InlineKeyboardButton("📞 Update Contact", callback_data="update_contact")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def super_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Super admin only panel"""
        query = update.callback_query
        
        if update.effective_user.id != config.SUPER_ADMIN_ID:
            await query.edit_message_text("❌ Super Admin access only.")
            return
        
        message = "👑 **Super Admin Panel**\n\nExtra privileges:"
        
        keyboard = [
            [InlineKeyboardButton("👥 Manage Admins", callback_data="super_admins")],
            [InlineKeyboardButton("💰 System Balance", callback_data="super_balance")],
            [InlineKeyboardButton("📊 Full Analytics", callback_data="super_analytics")],
            [InlineKeyboardButton("⚙️ System Config", callback_data="super_config")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')