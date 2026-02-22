import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import pyotp

from database import db
from models import UserRole, AccountStatus
import config
from utils import generate_qr_code, generate_2fa_secret, encrypt_data, decrypt_data

logger = logging.getLogger(__name__)

# Conversation states
(PHONE_NUMBER, OTP_CODE, PASSWORD, ACCOUNT_NAME, TWO_FA_SETUP) = range(5)

class AuthHandler:
    def __init__(self):
        self.temp_data = {}
    
    async def start_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the login process for adding a Telegram account"""
        user_id = update.effective_user.id
        
        # Check if user exists
        user = await db.get_user(user_id)
        if not user:
            user = await db.create_user(
                user_id=user_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name
            )
        
        # Check account limit
        accounts = await db.get_user_accounts(user_id)
        if len(accounts) >= config.MAX_ACCOUNTS_PER_USER and user.role not in [UserRole.ADMIN, UserRole.OWNER, UserRole.SUPER_ADMIN]:
            await update.message.reply_text(
                f"❌ You've reached the maximum limit of {config.MAX_ACCOUNTS_PER_USER} accounts.\n"
                "Please remove an existing account or contact support."
            )
            return ConversationHandler.END
        
        await update.message.reply_text(
            "🔐 **Add Telegram Account**\n\n"
            "Please enter your phone number in international format:\n"
            "Example: `+1234567890`\n\n"
            "This will be used to login to Telegram for reporting.\n"
            "Your credentials are encrypted and secure.",
            parse_mode='Markdown'
        )
        
        return PHONE_NUMBER
    
    async def handle_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle phone number input"""
        phone = update.message.text.strip()
        user_id = update.effective_user.id
        
        # Validate phone number
        if not phone.startswith('+') or not phone[1:].isdigit():
            await update.message.reply_text(
                "❌ Invalid phone number format.\n"
                "Please use international format: +1234567890"
            )
            return PHONE_NUMBER
        
        # Store in context
        context.user_data['login_phone'] = phone
        
        # In a real implementation, you would send OTP via Telegram client API
        # This is a simplified version
        await update.message.reply_text(
            "📱 **Verification Required**\n\n"
            "An OTP has been sent to your Telegram app.\n"
            "Please enter the 5-digit code you received:\n\n"
            "If you have 2FA enabled, type /2fa after entering OTP.",
            parse_mode='Markdown'
        )
        
        return OTP_CODE
    
    async def handle_otp(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle OTP input"""
        otp = update.message.text.strip()
        
        if not otp.isdigit() or len(otp) != 5:
            await update.message.reply_text(
                "❌ Invalid OTP. Please enter the 5-digit code."
            )
            return OTP_CODE
        
        context.user_data['login_otp'] = otp
        
        # Check if 2FA is enabled
        keyboard = [
            [InlineKeyboardButton("✅ No 2FA", callback_data="2fa_no")],
            [InlineKeyboardButton("🔐 Enter 2FA Password", callback_data="2fa_yes")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔐 **Two-Factor Authentication**\n\n"
            "Does your account have 2FA enabled?",
            reply_markup=reply_markup
        )
        
        return PASSWORD
    
    async def handle_2fa_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 2FA choice"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "2fa_no":
            # Complete login
            return await self.complete_login(update, context)
        else:
            await query.edit_message_text(
                "🔐 Please enter your 2FA password:"
            )
            return TWO_FA_SETUP
    
    async def handle_2fa_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle 2FA password"""
        password = update.message.text.strip()
        context.user_data['login_2fa'] = password
        
        return await self.complete_login(update, context)
    
    async def complete_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Complete the login process"""
        user_id = update.effective_user.id
        phone = context.user_data.get('login_phone')
        otp = context.user_data.get('login_otp')
        twofa = context.user_data.get('login_2fa')
        
        # In a real implementation, you would use Telethon to create a client
        # and get the session string. This is a placeholder.
        session_string = f"simulated_session_{phone}_{otp}"
        
        # Encrypt session
        encrypted_session = encrypt_data(session_string)
        
        # Add account to database
        try:
            account = await db.add_telegram_account(
                user_id=user_id,
                phone_number=phone,
                session_string=encrypted_session,
                account_name=f"Account {phone[-4:]}",
                twofa_password=twofa
            )
            
            # Clear temp data
            for key in ['login_phone', 'login_otp', 'login_2fa']:
                context.user_data.pop(key, None)
            
            await update.message.reply_text(
                f"✅ **Account Added Successfully!**\n\n"
                f"Account ID: `{account.account_id}`\n"
                f"Name: {account.account_name}\n"
                f"Status: Active\n\n"
                f"You can now use this account to report.\n"
                f"Use /accounts to manage your accounts.",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            await update.message.reply_text(
                "❌ Failed to add account. Please try again or contact support."
            )
        
        return ConversationHandler.END
    
    async def cancel_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel login process"""
        await update.message.reply_text(
            "❌ Login cancelled. Use /login to try again."
        )
        return ConversationHandler.END
    
    async def show_accounts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's accounts"""
        user_id = update.effective_user.id
        accounts = await db.get_user_accounts(user_id)
        
        if not accounts:
            await update.message.reply_text(
                "📱 **No Accounts Found**\n\n"
                "You haven't added any Telegram accounts yet.\n"
                "Use /login to add an account.",
                parse_mode='Markdown'
            )
            return
        
        message = "📱 **Your Accounts**\n\n"
        keyboard = []
        
        for acc in accounts:
            status_emoji = "✅" if acc.status == AccountStatus.ACTIVE else "❌"
            primary = "⭐" if acc.is_primary else ""
            message += f"{status_emoji} {primary} **{acc.account_name}**\n"
            message += f"ID: `{acc.account_id[:8]}...`\n"
            message += f"Reports: {acc.total_reports_used}\n\n"
            
            # Add buttons for each account
            keyboard.append([
                InlineKeyboardButton(
                    f"📊 {acc.account_name}",
                    callback_data=f"acc_stats_{acc.account_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Add New Account", callback_data="add_account")])
        keyboard.append([InlineKeyboardButton("❌ Remove Account", callback_data="remove_account")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def account_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle account management callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "add_account":
            await query.edit_message_text(
                "Use /login to add a new account."
            )
        elif data == "remove_account":
            # Show accounts to remove
            user_id = update.effective_user.id
            accounts = await db.get_user_accounts(user_id)
            
            keyboard = []
            for acc in accounts:
                keyboard.append([
                    InlineKeyboardButton(
                        f"❌ {acc.account_name}",
                        callback_data=f"remove_acc_{acc.account_id}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_accounts")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Select account to remove:",
                reply_markup=reply_markup
            )
        elif data.startswith("remove_acc_"):
            account_id = data.replace("remove_acc_", "")
            await db.update_account_status(account_id, AccountStatus.INACTIVE)
            await query.edit_message_text("✅ Account removed successfully!")
        elif data.startswith("acc_stats_"):
            account_id = data.replace("acc_stats_", "")
            account = await db.get_account(account_id)
            if account:
                stats = (
                    f"📊 **Account Statistics**\n\n"
                    f"Name: {account.account_name}\n"
                    f"Phone: {account.phone_number}\n"
                    f"Status: {account.status.value}\n"
                    f"Primary: {'Yes' if account.is_primary else 'No'}\n"
                    f"Total Reports: {account.total_reports_used}\n"
                    f"Added: {account.added_date.strftime('%Y-%m-%d')}\n"
                    f"Last Used: {account.last_used.strftime('%Y-%m-%d %H:%M') if account.last_used else 'Never'}"
                )
                await query.edit_message_text(stats, parse_mode='Markdown')