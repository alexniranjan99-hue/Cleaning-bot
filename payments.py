import logging
import uuid
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import qrcode
from io import BytesIO

from database import db
import config

logger = logging.getLogger(__name__)

class PaymentHandler:
    async def show_token_packages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available token packages"""
        packages = await db.get_token_packages()
        
        message = "💰 **Token Packages**\n\n"
        message += "Buy tokens to make reports:\n\n"
        
        keyboard = []
        
        for package in packages:
            message += f"**{package.name}**\n"
            message += f"• {package.tokens} Reports\n"
            message += f"• ⭐ {package.price_stars} Stars\n"
            message += f"• ₹{package.price_inr} UPI\n"
            message += f"• {package.description}\n\n"
            
            # Add buttons for each package
            keyboard.append([
                InlineKeyboardButton(
                    f"⭐ Buy {package.name} with Stars",
                    callback_data=f"buy_stars_{package.package_id}"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    f"💳 Buy {package.name} with UPI",
                    callback_data=f"buy_upi_{package.package_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("📊 My Balance", callback_data="check_balance")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_package_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle package selection"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if data.startswith("buy_stars_"):
            package_id = data.replace("buy_stars_", "")
            await self.initiate_stars_payment(update, context, package_id)
        elif data.startswith("buy_upi_"):
            package_id = data.replace("buy_upi_", "")
            await self.initiate_upi_payment(update, context, package_id)
        elif data == "check_balance":
            await self.check_balance(update, context)
    
    async def initiate_stars_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, package_id: str):
        """Initiate Telegram Stars payment"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        package = await db.get_package(package_id)
        if not package:
            await query.edit_message_text("❌ Invalid package selected.")
            return
        
        # Create transaction
        transaction = await db.create_transaction(
            user_id=user_id,
            amount=package.price_stars,
            currency="STARS",
            tokens=package.tokens,
            payment_method="stars"
        )
        
        # In a real implementation, you would integrate with Telegram Stars API
        # This is a simplified version
        payment_text = (
            f"💫 **Telegram Stars Payment**\n\n"
            f"Package: {package.name}\n"
            f"Tokens: {package.tokens}\n"
            f"Price: {package.price_stars} ⭐\n\n"
            f"Transaction ID: `{transaction.transaction_id}`\n\n"
            f"To complete payment:\n"
            f"1. Send {package.price_stars} Stars to @YourBot\n"
            f"2. Use /confirm_payment {transaction.transaction_id}\n\n"
            f"⏰ Transaction expires in 30 minutes."
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ I've Sent Stars", callback_data=f"confirm_stars_{transaction.transaction_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def initiate_upi_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, package_id: str):
        """Initiate UPI payment"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        package = await db.get_package(package_id)
        if not package:
            await query.edit_message_text("❌ Invalid package selected.")
            return
        
        # Create transaction
        transaction = await db.create_transaction(
            user_id=user_id,
            amount=package.price_inr,
            currency="INR",
            tokens=package.tokens,
            payment_method="upi"
        )
        
        # Generate UPI payment link
        upi_link = f"upi://pay?pa={config.UPI_ID}&pn={config.PAYEE_NAME}&am={package.price_inr}&cu=INR&tn={transaction.transaction_id}"
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(upi_link)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        
        payment_text = (
            f"💳 **UPI Payment**\n\n"
            f"Package: {package.name}\n"
            f"Tokens: {package.tokens}\n"
            f"Amount: ₹{package.price_inr}\n"
            f"UPI ID: `{config.UPI_ID}`\n"
            f"Transaction ID: `{transaction.transaction_id}`\n\n"
            f"**Instructions:**\n"
            f"1. Scan QR code or use UPI ID\n"
            f"2. Send exact amount: ₹{package.price_inr}\n"
            f"3. Use Transaction ID as reference\n"
            f"4. Click 'I've Paid' after payment\n\n"
            f"⏰ Transaction expires in 30 minutes."
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ I've Paid", callback_data=f"confirm_upi_{transaction.transaction_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')
        
        # Send QR code
        await context.bot.send_photo(
            chat_id=user_id,
            photo=bio,
            caption="Scan this QR code to pay via UPI"
        )
    
    async def confirm_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm payment (manual verification)"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("confirm_stars_"):
            transaction_id = data.replace("confirm_stars_", "")
            await self.verify_stars_payment(update, context, transaction_id)
        elif data.startswith("confirm_upi_"):
            transaction_id = data.replace("confirm_upi_", "")
            await self.verify_upi_payment(update, context, transaction_id)
        elif data == "cancel_payment":
            await query.edit_message_text("❌ Payment cancelled.")
    
    async def verify_stars_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, transaction_id: str):
        """Verify Stars payment"""
        query = update.callback_query
        
        # In production, you would verify with Telegram API
        # This is a simplified version
        transaction = await db.get_transaction(transaction_id)
        if not transaction:
            await query.edit_message_text("❌ Transaction not found.")
            return
        
        # Mark as completed
        await db.complete_transaction(transaction_id)
        
        # Add tokens to user
        await db.update_user_tokens(transaction.user_id, transaction.tokens_purchased)
        
        await query.edit_message_text(
            f"✅ **Payment Verified!**\n\n"
            f"🎉 {transaction.tokens_purchased} tokens have been added to your account.\n\n"
            f"Use /balance to check your tokens.\n"
            f"Use /report to start reporting!"
        )
    
    async def verify_upi_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, transaction_id: str):
        """Verify UPI payment"""
        query = update.callback_query
        
        # In production, you would have a webhook or manual verification
        # This notifies admins to verify
        transaction = await db.get_transaction(transaction_id)
        if not transaction:
            await query.edit_message_text("❌ Transaction not found.")
            return
        
        # Notify admins
        for admin_id in config.ADMIN_IDS + config.OWNER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💰 **UPI Payment Pending Verification**\n\n"
                         f"User ID: `{transaction.user_id}`\n"
                         f"Amount: ₹{transaction.amount}\n"
                         f"Tokens: {transaction.tokens_purchased}\n"
                         f"Transaction ID: `{transaction_id}`\n\n"
                         f"Use /verify_payment {transaction_id} to confirm.",
                    parse_mode='Markdown'
                )
            except:
                pass
        
        await query.edit_message_text(
            f"⏳ **Payment Submitted for Verification**\n\n"
            f"Your payment is being verified.\n"
            f"You'll receive a notification once confirmed.\n\n"
            f"Transaction ID: `{transaction_id}`"
        )
    
    async def check_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check user's token balance"""
        user_id = update.effective_user.id
        user = await db.get_user(user_id)
        
        if not user:
            user = await db.create_user(
                user_id=user_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name
            )
        
        await update.message.reply_text(
            f"💰 **Your Balance**\n\n"
            f"Tokens: **{user.tokens}**\n"
            f"Reports Made: **{user.total_reports}**\n"
            f"Account Type: **{user.role.value.upper()}**\n\n"
            f"Use /buy to purchase more tokens.",
            parse_mode='Markdown'
        )
    
    async def admin_verify_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to verify payment"""
        user_id = update.effective_user.id
        
        # Check if user is admin/owner
        if user_id not in config.ADMIN_IDS and user_id not in config.OWNER_IDS and user_id != config.SUPER_ADMIN_ID:
            await update.message.reply_text("❌ Unauthorized.")
            return
        
        # Get transaction ID from command
        try:
            transaction_id = context.args[0]
        except:
            await update.message.reply_text("Usage: /verify_payment <transaction_id>")
            return
        
        # Verify transaction
        result = await db.complete_transaction(transaction_id)
        
        if result:
            # Get transaction details
            transaction = await db.get_transaction(transaction_id)
            if transaction:
                # Add tokens
                await db.update_user_tokens(transaction.user_id, transaction.tokens_purchased)
                
                # Notify user
                await context.bot.send_message(
                    chat_id=transaction.user_id,
                    text=f"✅ **Payment Verified!**\n\n"
                         f"🎉 {transaction.tokens_purchased} tokens have been added to your account.",
                    parse_mode='Markdown'
                )
                
                await update.message.reply_text(f"✅ Payment verified. Tokens added to user {transaction.user_id}.")
        else:
            await update.message.reply_text("❌ Transaction not found or already verified.")