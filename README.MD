# Python Telegram Bot

Template for quick deployment using [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) library.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/-6JUpc?referralCode=NC4Tt6)

# Banking Telegram Bot

This is a Telegram bot simulating a banking system. The bot provides functionalities such as balance checking, transaction history, fund transfers, and daily gifts. It uses Python with the `telebot` library and MongoDB for data storage.

## Features

- 💰 **Check Balance**: View your current account balance.
- 📜 **Transaction History**: See a list of your previous transactions.
- 🏦 **Bot Liquidity**: Check the current liquidity of the bot and the total balance of all users.
- 💸 **Transfer Funds**: Send money to other users with a small transaction fee.
- 🎁 **Daily Gift**: Receive a random daily gift to your account.

## Setup

### Prerequisites

- Python 3.7+
- MongoDB instance (local or cloud)
- Telegram Bot Token

### Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/banking-telegram-bot.git
   cd banking-telegram-bot

2.Install Dependencies

Use pip to install the required libraries.

  ```bash
     pip install -r requirements.txt
```
3.Set Environment Variables

You need to set the following environment variables:

TOKEN: Your Telegram bot token.
DB_USER: Your MongoDB username.
DB_PASS: Your MongoDB password.
DB_CLUSTER: Your MongoDB cluster URL.
You can set these in your terminal session or use a .env file. Here's an example of a .env file:

 ```bash
TOKEN=your-telegram-bot-token
DB_USER=your-db-username
DB_PASS=your-db-password
DB_CLUSTER=your-db-cluster-url

