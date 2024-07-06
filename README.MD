Here's a `README.md` file for your Telegram bot project, detailing the setup and usage instructions:


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

1. **Clone  the Repository**

   ```bash
   git clone https://github.com/a9ii/BANK_SYSTEM.git
   cd BANK_SYSTEM

   ```

2. **Install Dependencies**

   Use `pip` to install the required libraries.

   ```bash
   pip install -r requirements.txt
   ```

3. **Set Environment Variables**

   You need to set the following environment variables:

   - `TOKEN`: Your Telegram bot token.
   - `DB_USER`: Your MongoDB username.
   - `DB_PASS`: Your MongoDB password.
   - `DB_CLUSTER`: Your MongoDB cluster URL.

   You can set these in your terminal session or use a `.env` file. Here's an example of a `.env` file:

   ```plaintext
   TOKEN=your-telegram-bot-token
   DB_USER=your-db-username
   DB_PASS=your-db-password
   DB_CLUSTER=your-db-cluster-url
   ```

   Load the environment variables by running:

   ```bash
   source .env
   ```

4. **Run the Bot**

   Start the bot by executing:

   ```bash
   python bot.py
   ```

## Usage

Once the bot is running, you can interact with it using the following commands:

- **/start**: Start the bot and display the main menu.
- **💰 رصيدي**: Check your current balance.
- **📜 العمليات السابقة**: View your transaction history.
- **🏦 سيولة البوت**: Check the bot's liquidity and total user balances.
- **💸 تحويل**: Transfer funds to another user.
- **🎁 الهدية اليومية**: Receive your daily gift.

## Example Commands

1. **Start the Bot**

   ```plaintext
   /start
   ```

   The bot will greet you and show the main menu with buttons.

2. **Check Balance**

   Press the "💰 رصيدي" button to see your current balance.

3. **View Transaction History**

   Press the "📜 العمليات السابقة" button to see your past transactions.

4. **Check Bot Liquidity**

   Press the "🏦 سيولة البوت" button to view the bot's liquidity and total user balances.

5. **Transfer Funds**

   Press the "💸 تحويل" button to start a fund transfer. You will be prompted to enter the recipient's account number and the amount to transfer.

6. **Receive Daily Gift**

   Press the "🎁 الهدية اليومية" button to get your random daily gift.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
```

This `README.md` file provides a clear overview of the bot's features, setup instructions, and usage, including the necessary commands and interactions with the bot.
