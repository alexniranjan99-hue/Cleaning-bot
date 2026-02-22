# 🤖 Telegram Advanced Report Bot

A comprehensive Telegram bot for reporting channels, groups, and users with multi-account support, token system, and admin panel. Perfect for content moderation and community management.

## ✨ Features

### 🔐 **Multi-Account Support**
- Add multiple Telegram accounts for reporting
- Switch between accounts seamlessly
- Keep your main account safe
- Account activity tracking

### 💰 **Token System**
- Purchase tokens via Telegram Stars or UPI
- Multiple token packages available
- Track your token balance
- Automatic token deduction per report

### 👑 **Role-Based Access**
- **Normal Users**: Buy tokens to report
- **Admins**: Free unlimited reporting
- **Owners**: Manage users and tokens
- **Super Admin**: Full system control

### 📊 **Comprehensive Reporting**
- Report users, groups, and channels
- Template-based quick reporting
- Custom reason support
- Report history tracking
- Evidence attachment

### 🛠️ **Admin Panel**
- Review pending reports
- User management
- Token management
- Statistics dashboard
- System configuration

### 💳 **Payment Integration**
- Telegram Stars payments
- UPI payments with QR code
- Automatic token delivery
- Payment verification system

## 🚀 Quick Deployment on Railway

### Step 1: Create a Telegram Bot
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow instructions
3. Copy the bot token you receive

### Step 2: Set Up MongoDB
1. Create a free MongoDB cluster at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Get your connection string (MONGODB_URI)

### Step 3: Deploy on Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/yourusername/telegram-advanced-report-bot)

Or deploy manually:

1. **Fork this repository**
```bash
git clone https://github.com/yourusername/telegram-advanced-report-bot.git
cd telegram-advanced-report-bot