#!/usr/bin/env python3
"""
Telegram Advanced Report Bot
Complete solution with multi-account support, token system, and admin panel
"""

import logging
import asyncio
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.error import InvalidToken

import config
from database import db
from auth import AuthHandler, PHONE_NUMBER, OTP_CODE, PASSWORD, TWO_FA_SETUP
from payments import PaymentHandler
from report_handler import ReportHandler, SELECT_ACCOUNT, REPORT_TYPE, REPORT_TARGET, REPORT_REASON, REPORT_DETAILS, CONFIRMATION, ADMIN_TARGET, ADMIN_REASON
from admin_handler import AdminHandler
from models import UserRole

# Enable logging
logging.basic