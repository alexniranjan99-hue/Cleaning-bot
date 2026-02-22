import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
import re

from database import db
from models import UserRole, ReportStatus
import config
from utils import validate_target

logger = logging.getLogger(__name__)

# Conversation states
(REPORT_TYPE, SELECT_ACCOUNT, REPORT_TARGET, REPORT_REASON, 
 REPORT_DETAILS, CONFIRMATION, ADMIN_TARGET, ADMIN_REASON) = range(8)

# Report types
REPORT_TYPES = {
    'user': '👤 User',
    'group': '👥 Group', 
    'channel': '📢 Channel'
}

class ReportHandler:
    def __init__(self):
        self.temp_data = {}
    
    async def start_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the report process"""
        user_id = update.effective_user.id
        user = await db.get_user(user_id)
        
        if not user:
            user = await db.create_user(
                user_id=user_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name
            )
        
        # Check if user is admin/owner (free reporting)
        if user.role in [UserRole.ADMIN, UserRole.OWNER, UserRole.SUPER_ADMIN]:
            return await self.start_admin_report(update, context)
        
        # Check tokens for normal users
        if user.tokens < config.REPORT_COST_IN_TOKENS:
            keyboard = [
                [InlineKeyboardButton("💰 Buy Tokens", callback_data="buy_tokens")],
                [InlineKeyboardButton("📞 Contact Support", url=f"https://t.me/{config.CONTACT_INFO['admin_username']}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ **Insufficient Tokens**\n\n"
                f"You need {config.REPORT_COST_IN_TOKENS} token(s) to make a report.\n"
                f"Your balance: {user.tokens} tokens\n\n"
                "Please purchase tokens to continue.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return ConversationHandler.END
        
        # Check if user has any accounts
        accounts = await db.get_user_accounts(user_id)
        if not accounts:
            keyboard = [
                [InlineKeyboardButton("➕ Add Account", callback_data="add_account")],
                [InlineKeyboardButton("📞 Contact Support", url=f"https://t.me/{config.CONTACT_INFO['admin_username']}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ **No Accounts Found**\n\n"
                "You need to add a Telegram account to report.\n"
                "This keeps your main account safe.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        # Ask user to select account
        return await self.show_account_selection(update, context, user_id)
    
    async def show_account_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show available accounts for reporting"""
        accounts = await db.get_user_accounts(user_id)
        
        keyboard = []
        for acc in accounts:
            if acc.status.value == "active":
                status = "✅" if acc.is_primary else "📱"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status} {acc.account_name}",
                        callback_data=f"select_acc_{acc.account_id}"
                    )
                ])
        
        keyboard.append([InlineKeyboardButton("➕ Add New Account", callback_data="add_account")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_report")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = update.message if update.message else update.callback_query.message
        
        await message.reply_text(
            "📱 **Select Account to Report With**\n\n"
            "Choose which account you want to use for this report:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return SELECT_ACCOUNT
    
    async def handle_account_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle account selection"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "add_account":
            await query.edit_message_text(
                "Use /login to add a new account.\n"
                "Then start /report again."
            )
            return ConversationHandler.END
        elif data == "cancel_report":
            await query.edit_message_text("❌ Report cancelled.")
            return ConversationHandler.END
        elif data.startswith("select_acc_"):
            account_id = data.replace("select_acc_", "")
            context.user_data['report_account_id'] = account_id
            
            # Show report type selection
            keyboard = [
                [InlineKeyboardButton(REPORT_TYPES['user'], callback_data='report_type_user')],
                [InlineKeyboardButton(REPORT_TYPES['group'], callback_data='report_type_group')],
                [InlineKeyboardButton(REPORT_TYPES['channel'], callback_data='report_type_channel')],
                [InlineKeyboardButton('❌ Cancel', callback_data='cancel_report')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🔍 **What would you like to report?**\n\n"
                "Select the type of content you want to report:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return REPORT_TYPE
    
    async def handle_report_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle report type selection"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel_report':
            await query.edit_message_text("❌ Report cancelled.")
            return ConversationHandler.END
        
        report_type = query.data.replace('report_type_', '')
        context.user_data['report_type'] = report_type
        
        await query.edit_message_text(
            f"📝 **Reporting: {REPORT_TYPES[report_type]}**\n\n"
            f"Please send the username, link, or ID of the {report_type} you want to report.\n\n"
            f"Examples:\n"
            f"• Username: @username\n"
            f"• Link: https://t.me/username\n"
            f"• Group link: https://t.me/+abc123...\n"
            f"• User ID: 123456789",
            parse_mode='Markdown'
        )
        
        return REPORT_TARGET
    
    async def handle_target(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle target input"""
        target = update.message.text.strip()
        
        if not validate_target(target):
            await update.message.reply_text(
                "❌ Invalid format. Please provide a valid username, link, or ID.\n\n"
                "Examples:\n"
                "• @username\n"
                "• https://t.me/username\n"
                "• https://t.me/+abc123...\n"
                "• 123456789"
            )
            return REPORT_TARGET
        
        context.user_data['report_target'] = target
        
        # Get templates for reason selection
        templates = await db.get_templates()
        
        keyboard = []
        for template in templates[:5]:  # Show first 5 templates
            keyboard.append([
                InlineKeyboardButton(
                    f"📌 {template.name}",
                    callback_data=f"reason_template_{template.template_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("✏️ Custom Reason", callback_data="reason_custom")])
        keyboard.append([InlineKeyboardButton('❌ Cancel', callback_data='cancel_report')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ **Select a reason for your report:**\n\n"
            "Choose a template or write your own reason:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        return REPORT_REASON
    
    async def handle_reason(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle reason selection"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel_report':
            await query.edit_message_text("❌ Report cancelled.")
            return ConversationHandler.END
        
        if query.data == 'reason_custom':
            await query.edit_message_text(
                "✏️ **Custom Reason**\n\n"
                "Please type your reason for reporting:\n"
                f"Maximum {config.MAX_REPORT_LENGTH} characters.",
                parse_mode='Markdown'
            )
            return REPORT_DETAILS
        elif query.data.startswith('reason_template_'):
            template_id = query.data.replace('reason_template_', '')
            # Store template ID to fetch details later
            context.user_data['report_template'] = template_id
            
            await query.edit_message_text(
                "📝 **Additional Details**\n\n"
                "Please provide any additional details or evidence:\n"
                "(Send /skip to continue without details)",
                parse_mode='Markdown'
            )
            return REPORT_DETAILS
    
    async def handle_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle additional details"""
        details = update.message.text.strip()
        
        if len(details) > config.MAX_REPORT_LENGTH:
            await update.message.reply_text(
                f"❌ Details too long. Maximum {config.MAX_REPORT_LENGTH} characters.\n"
                "Please try again or use /skip."
            )
            return REPORT_DETAILS
        
        context.user_data['report_details'] = details
        return await self.confirm_report(update, context)
    
    async def skip_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip additional details"""
        context.user_data['report_details'] = "No additional details provided."
        return await self.confirm_report(update, context)
    
    async def confirm_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show report summary for confirmation"""
        user_data = context.user_data
        user = await db.get_user(update.effective_user.id)
        
        # Get template if used
        reason_text = user_data.get('report_reason', 'Custom')
        if 'report_template' in user_data:
            template = await db.get_template(user_data['report_template'])
            if template:
                reason_text = template.name
        
        summary = (
            "📋 **Please confirm your report:**\n\n"
            f"**Type:** {REPORT_TYPES[user_data['report_type']]}\n"
            f"**Target:** {user_data['report_target']}\n"
            f"**Reason:** {reason_text}\n"
            f"**Details:** {user_data['report_details'][:200]}\n"
            f"**Cost:** {config.REPORT_COST_IN_TOKENS} token(s)\n"
            f"**Your Balance:** {user.tokens} tokens\n\n"
            f"Once confirmed, tokens will be deducted."
        )
        
        keyboard = [
            [
                InlineKeyboardButton('✅ Confirm', callback_data='confirm_report'),
                InlineKeyboardButton('❌ Cancel', callback_data='cancel_report')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(summary, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.callback_query.edit_message_text(summary, reply_markup=reply_markup, parse_mode='Markdown')
        
        return CONFIRMATION
    
    async def submit_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Submit the report"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'cancel_report':
            await query.edit_message_text("❌ Report cancelled.")
            return ConversationHandler.END
        
        user_id = update.effective_user.id
        user_data = context.user_data
        
        # Get account
        account = await db.get_account(user_data['report_account_id'])
        if not account:
            await query.edit_message_text("❌ Account not found. Please try again.")
            return ConversationHandler.END
        
        # Get template reason if used
        reason = user_data.get('report_reason', 'Custom')
        if 'report_template' in user_data:
            template = await db.get_template(user_data['report_template'])
            if template:
                reason = template.content
        
        # Deduct tokens (only for non-admin users)
        user = await db.get_user(user_id)
        if user.role not in [UserRole.ADMIN, UserRole.OWNER, UserRole.SUPER_ADMIN]:
            await db.update_user_tokens(user_id, -config.REPORT_COST_IN_TOKENS)
        
        # Create report
        report = await db.create_report(
            user_id=user_id,
            account_id=account.account_id,
            report_type=user_data['report_type'],
            target=user_data['report_target'],
            reason=reason,
            details=user_data.get('report_details', ''),
            tokens_used=config.REPORT_COST_IN_TOKENS
        )
        
        # Update user report count
        await db.add_report_count(user_id)
        
        # Send to report channel if configured
        if config.REPORT_CHANNEL_ID:
            try:
                report_text = (
                    f"🚨 **NEW REPORT**\n\n"
                    f"**Report ID:** `{report.report_id}`\n"
                    f"**User:** {update.effective_user.full_name} (ID: `{user_id}`)\n"
                    f"**Account:** {account.account_name}\n"
                    f"**Type:** {REPORT_TYPES[user_data['report_type']]}\n"
                    f"**Target:** {user_data['report_target']}\n"
                    f"**Reason:** {reason[:100]}\n"
                    f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                await context.bot.send_message(
                    chat_id=config.REPORT_CHANNEL_ID,
                    text=report_text,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to send to report channel: {e}")
        
        # Send confirmation to user
        await query.edit_message_text(
            f"✅ **Report Submitted Successfully!**\n\n"
            f"**Report ID:** `{report.report_id}`\n"
            f"**Tokens Used:** {config.REPORT_COST_IN_TOKENS}\n"
            f"**Status:** Pending Review\n\n"
            f"Thank you for helping keep Telegram safe.\n\n"
            f"Use /myreports to track your reports.\n"
            f"Need help? Contact @{config.CONTACT_INFO['admin_username']}",
            parse_mode='Markdown'
        )
        
        # Clear user data
        context.user_data.clear()
        
        return ConversationHandler.END
    
    async def start_admin_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin-specific report process (free, can target anything)"""
        await update.message.reply_text(
            "👑 **Admin Report Mode**\n\n"
            "You can report any user, group, or channel for free.\n\n"
            "Please send the username, link, or ID of the target:",
            parse_mode='Markdown'
        )
        
        return ADMIN_TARGET
    
    async def handle_admin_target(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin target input"""
        target = update.message.text.strip()
        
        if not validate_target(target):
            await update.message.reply_text(
                "❌ Invalid format. Please provide a valid username, link, or ID."
            )
            return ADMIN_TARGET
        
        context.user_data['admin_target'] = target
        
        await update.message.reply_text(
            "⚠️ **Enter report reason:**\n\n"
            "Please explain why you're reporting this target:",
            parse_mode='Markdown'
        )
        
        return ADMIN_REASON
    
    async def handle_admin_reason(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin reason input"""
        reason = update.message.text.strip()
        
        if len(reason) > config.MAX_REPORT_LENGTH:
            await update.message.reply_text(
                f"❌ Reason too long. Maximum {config.MAX_REPORT_LENGTH} characters."
            )
            return ADMIN_REASON
        
        user_id = update.effective_user.id
        target = context.user_data['admin_target']
        
        # Create admin report
        report = await db.create_report(
            user_id=user_id,
            account_id="admin",
            report_type="admin",
            target=target,
            reason=reason,
            details="Admin Report",
            tokens_used=0
        )
        
        # Send to report channel
        if config.REPORT_CHANNEL_ID:
            report_text = (
                f"👑 **ADMIN REPORT**\n\n"
                f"**Admin:** {update.effective_user.full_name}\n"
                f"**Target:** {target}\n"
                f"**Reason:** {reason}\n"
                f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await context.bot.send_message(
                chat_id=config.REPORT_CHANNEL_ID,
                text=report_text,
                parse_mode='Markdown'
            )
        
        await update.message.reply_text(
            f"✅ **Admin Report Submitted**\n\n"
            f"Target: {target}\n"
            f"Report ID: `{report.report_id}`",
            parse_mode='Markdown'
        )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DATE_TYPE):
        """Cancel the conversation"""
        await update.message.reply_text(
            "❌ Operation cancelled. Use /report to start over."
        )
        return ConversationHandler.END
    
    async def my_reports(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's reports"""
        user_id = update.effective_user.id
        page = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
        
        reports = await db.get_user_reports(user_id, page)
        
        if not reports:
            await update.message.reply_text(
                "📊 **No Reports Found**\n\n"
                "You haven't made any reports yet.\n"
                "Use /report to get started!",
                parse_mode='Markdown'
            )
            return
        
        message = f"📊 **Your Reports (Page {page})**\n\n"
        
        for report in reports[:5]:
            status_emoji = {
                ReportStatus.PENDING: "⏳",
                ReportStatus.REVIEWED: "👀",
                ReportStatus.RESOLVED: "✅",
                ReportStatus.REJECTED: "❌"
            }.get(report.status, "📝")
            
            message += f"{status_emoji} **{report.report_type.upper()}** - {report.target}\n"
            message += f"ID: `{report.report_id[:8]}...` | Status: {report.status.value}\n"
            message += f"Date: {report.created_at.strftime('%Y-%m-%d')}\n\n"
        
        # Add navigation buttons
        keyboard = []
        nav_buttons = []
        
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"reports_page_{page-1}"))
        if len(reports) > 5:
            nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"reports_page_{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("🆕 New Report", callback_data="new_report")])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')