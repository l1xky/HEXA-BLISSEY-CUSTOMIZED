# Blissey Bot Automation

An automated Telegram bot for interacting with the HeXamonbot Blissey battles.

## Features

- 🤖 **Auto-reply**: Automatically replies to challenge messages with `/challenge@HeXamonbot`
- ⚔️ **Battle automation**: Automatically clicks battle buttons (row 2, column 1)
- 🎯 **Custom attacks**: Choose which attack to use (Attack 1-4)
- 🔄 **Switch handling**: Detects Blissey switches and continues clicking
- ⚡ **Move detection**: Detects when Blissey uses Double-Edge and clicks button
- 💸 **Forfeit handling**: Detects forfeits and automatically sends new challenge
- ⏰ **Battle cooldown**: Detects "currently battling" and waits 2 minutes
- 💰 **Prize detection**: Automatically restarts when prizes are received
- 📝 **Comprehensive logging**: Full activity logging to file and console

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Telegram API Credentials

1. Go to [https://my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application
5. Note down your `API ID` and `API Hash`

### 3. Generate Session String

**Easy Method: Use the included session generator**
```bash
python generate_session.py
```

This interactive script will:
- Ask for your API credentials
- Handle phone verification
- Generate your session string
- Guide you through the setup

**Alternative Method: Manual generation**
```python
from telethon import TelegramClient

api_id = 'YOUR_API_ID'
api_hash = 'YOUR_API_HASH'

client = TelegramClient('session', api_id, api_hash)
client.start()
print(client.session.save())
```

### 4. Configure the Bot

Edit `config.py` and update these values:

```python
API_ID = 12345678  # Your API ID
API_HASH = "your_api_hash_here"  # Your API Hash
SESSION_STRING = "your_session_string_here"  # Your session string
```

### 5. Run the Bot

```bash
python main.py
```

## Quick Start Guide

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Update config.py** with your API credentials

3. **Create session file:**
   ```bash
   python create_session.py
   ```

4. **Run the bot:**
   ```bash
   python main.py
   ```

## 🎯 Custom Attack Selection

### Using the /custom Command

The main bot now includes a built-in custom attack selection system!

1. **Start the main bot:**
   ```bash
   python main.py
   ```

2. **Use the /custom command:**
   - Send `/custom` to the bot
   - Choose from Attack 1, 2, 3, or 4
   - Your selection is saved automatically

### Attack Layout
```
Row 1: Attack 1 | Attack 2
Row 2: Attack 3 | Attack 4
```

### Features
- 🎯 **Choose any attack** - Select from 4 available attacks
- 💾 **Persistent settings** - Your choice is saved in JSON
- 🔄 **Easy switching** - Change attacks anytime with /custom
- 📊 **View settings** - See your current configuration
- ❌ **Reset option** - Go back to default anytime
- 🤖 **Integrated** - No separate bot needed!

## How It Works

1. **Initialization**: Bot connects to Telegram using your session file
2. **Challenge Reply**: Automatically replies to message 530 with `/challenge@HeXamonbot`
3. **Battle Detection**: Monitors for "Battle begins!" messages
4. **Button Clicking**: Clicks the button at row 2, column 1 when battle starts
5. **Switch Handling**: Detects "Blissey switched out" messages and clicks again
6. **Move Detection**: Detects "Blissey used Double-Edge" and clicks button again
7. **Forfeit Handling**: Detects forfeits and automatically sends new challenge
8. **Battle Cooldown**: Detects "currently battling" and waits 2 minutes
9. **Prize Detection**: Detects prize messages and restarts the cycle
7. **Loop**: Continues indefinitely until stopped

## Target Channel

The bot monitors: `@JMD_BLISSEY` (message ID: 530)
Bot interaction: `@HeXamonbot`

## Logging

- Console output: Real-time status updates
- File logging: `blissey_bot.log` for detailed logs
- Log levels: INFO, WARNING, ERROR

## Safety Features

- Flood wait handling
- Error recovery
- Graceful shutdown on Ctrl+C
- Comprehensive error logging

## Troubleshooting

### Common Issues

1. **"Please configure your session string"**
   - Make sure you've updated the configuration in `main.py`

2. **"Failed to start bot"**
   - Check your API credentials
   - Verify your session string is valid

3. **"No reply markup found"**
   - The bot message doesn't have buttons yet
   - Wait for the battle to start

4. **"Button layout not found"**
   - The button layout is different than expected
   - Check the actual message structure

### Getting Help

Check the log file `blissey_bot.log` for detailed error information.

## Disclaimer

This bot is for educational purposes. Use responsibly and in accordance with Telegram's Terms of Service.
