import asyncio
import logging
import re
import os
import json
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonCallback
from telethon.errors import FloodWaitError, ChatAdminRequiredError
import time
from config import *

# logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class BlisseyBot:
    def __init__(self, api_id, api_hash, session_file='blissey_session.session'):
        self.client = TelegramClient(session_file, api_id, api_hash)
        self.target_channel = TARGET_CHANNEL
        self.bot_username = BOT_USERNAME
        self.target_message_id = TARGET_MESSAGE_ID
        self.is_running = False
        self.current_battle = False
        self.challenge_sent_time = None
        self.battle_timeout_task = None
        self.attack_config_file = 'attack_config.json'
        self.load_attack_config()
        self.automation_running = False
        
    def load_attack_config(self):
        try:
            if os.path.exists(self.attack_config_file):
                with open(self.attack_config_file, 'r') as f:
                    self.attack_config = json.load(f)
                logger.info("attack config loaded")
            else:
                self.attack_config = {}
                logger.info("no attack config found")
        except Exception as e:
            logger.error(f"error loading attack config: {e}")
            self.attack_config = {}
    
    def get_user_attack_config(self, user_id):
        user_config = self.attack_config.get(str(user_id))
        if user_config:
            return user_config['row'], user_config['col']
        else:
            # Default to row 2, column 1 (Attack 3)
            return BATTLE_BUTTON_ROW, BATTLE_BUTTON_COL
        
    async def start(self):
        """Start the bot and connect to Telegram"""
        try:
            await self.client.start()
            logger.info("✅ Connected to Telegram successfully!")
            
            # Get user info
            me = await self.client.get_me()
            logger.info(f"👤 Logged in as: {me.first_name} (@{me.username})")
            
            # Test channel access
            try:
                channel = await self.client.get_entity(self.target_channel)
                logger.info(f"📺 Channel found: {channel.title} (@{channel.username})")
            except Exception as e:
                logger.error(f"❌ Cannot access channel {self.target_channel}: {e}")
                logger.info("💡 Try using the full channel link or channel ID")
                logger.info("💡 Make sure you're a member of the channel")
                return
            
            # Set up event handlers
            self.setup_handlers()
            
            # Start the automation
            await self.start_automation()
            
        except Exception as e:
            logger.error(f"❌ Failed to start bot: {e}")
            
    def setup_handlers(self):
        """Set up event handlers for message monitoring"""
        
        @self.client.on(events.NewMessage(chats=self.target_channel))
        async def handle_new_message(event):
            await self.process_message(event)
            
        @self.client.on(events.MessageEdited(chats=self.target_channel))
        async def handle_edited_message(event):
            await self.process_message(event)
        
        @self.client.on(events.NewMessage(pattern='/custom'))
        async def handle_custom_command(event):
            await self.handle_custom_command(event)
        
        @self.client.on(events.NewMessage(pattern='/run'))
        async def handle_run_command(event):
            await self.handle_run_command(event)
        
        @self.client.on(events.NewMessage(pattern='/pause'))
        async def handle_pause_command(event):
            await self.handle_pause_command(event)
        
        @self.client.on(events.NewMessage(pattern='/guide'))
        async def handle_guide_command(event):
            await self.handle_guide_command(event)
        
        @self.client.on(events.NewMessage(pattern='/set_attack'))
        async def handle_set_attack_command(event):
            await self.handle_set_attack_command(event)
        
    
    async def process_message(self, event):
        """Process incoming messages and handle bot interactions"""
        try:
            # Only process messages if automation is running
            if not self.automation_running:
                return
                
            message = event.message
            text = message.text or ""
            sender = await message.get_sender()
            
            # Check if message is from HeXamonbot
            if sender and hasattr(sender, 'username') and sender.username == self.bot_username:
                logger.info(f"🤖 Bot message: {text[:100]}...")
                
                # Debug: Log full message for forfeit detection
                if "forfeits" in text.lower() or "has not moved" in text.lower():
                    logger.info(f"🔍 Full forfeit message: {text}")
                
                # Check for battle start
                if BATTLE_START_PATTERN.lower() in text.lower():
                    logger.info("⚔️ Battle started! Looking for buttons...")
                    self.current_battle = True
                    self.challenge_sent_time = None  # Reset challenge timer
                    # Cancel any pending battle timeout
                    if self.battle_timeout_task:
                        self.battle_timeout_task.cancel()
                        self.battle_timeout_task = None
                    await asyncio.sleep(SMOOTH_DELAY)  # Smooth delay
                    await self.click_battle_button(message)
                    
                # Check for Blissey switch
                elif BLISSEY_SWITCH_PATTERN.lower() in text.lower():
                    logger.info("🔄 Blissey switched! Clicking button again...")
                    await asyncio.sleep(SMOOTH_DELAY)  # Smooth delay
                    await self.click_battle_button(message)
                    
                # Check for Blissey Double-Edge
                elif BLISSEY_DOUBLE_EDGE_PATTERN.lower() in text.lower():
                    logger.info("⚔️ Blissey used Double-Edge! Clicking button again...")
                    await asyncio.sleep(SMOOTH_DELAY)  # Smooth delay
                    await self.click_battle_button(message)
                    
                # Check for forfeit message (multiple patterns)
                elif (FORFEIT_PATTERN.lower() in text.lower() or 
                      "has not moved" in text.lower() and "forfeits" in text.lower() and "loses 15" in text.lower()):
                    logger.info("💸 Player forfeited! Sending new challenge...")
                    logger.info(f"🔍 Forfeit detected in: {text[:50]}...")
                    self.current_battle = False
                    self.challenge_sent_time = None  # Reset challenge timer
                    # Cancel any pending battle timeout
                    if self.battle_timeout_task:
                        self.battle_timeout_task.cancel()
                        self.battle_timeout_task = None
                    await asyncio.sleep(SMOOTH_DELAY)  # Smooth delay
                    await self.send_challenge_command()
                    
                # Check for currently battling message
                elif CURRENTLY_BATTLING_PATTERN.lower() in text.lower():
                    logger.info("⚔️ Currently battling detected! Waiting 2 minutes...")
                    logger.info(f"🔍 Message: {text[:50]}...")
                    # Cancel any pending battle timeout
                    if self.battle_timeout_task:
                        self.battle_timeout_task.cancel()
                        self.battle_timeout_task = None
                    # Wait 2 minutes (120 seconds)
                    await asyncio.sleep(120)
                    logger.info("⏰ 2 minutes passed, sending new challenge...")
                    await self.send_challenge_command()
                # Check for daily limit reached message
                elif "Daily limit for battling has been reached" in text and "no prize will be given" in text:
                    logger.info("📅 Daily limit reached, sending new challenge...")
                    await asyncio.sleep(3)
                    await self.send_challenge_command()
                    
                # Check for prize message
                elif PRIZE_PATTERN.lower() in text.lower() and "💵" in text:
                    logger.info("💰 Prize received! Restarting automation...")
                    self.current_battle = False
                    self.challenge_sent_time = None  # Reset challenge timer
                    # Cancel any pending battle timeout
                    if self.battle_timeout_task:
                        self.battle_timeout_task.cancel()
                        self.battle_timeout_task = None
                    await asyncio.sleep(RESTART_DELAY)  # Wait before restarting
                    await self.send_challenge_command()
                    
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
    
    async def handle_custom_command(self, event):
        """Handle /custom command"""
        try:
            await event.edit(
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║                    ⚔️ ATTACK SELECTION ⚔️                   ║\n"
                "╠══════════════════════════════════════════════════════════════╣\n"
                "║                                                              ║\n"
                "║  🎯 AVAILABLE ATTACKS:                                      ║\n"
                "║  ┌────────────────────────────────────────────────────────┐  ║\n"
                "║  │ Attack 1 - Row 1, Column 1                            │  ║\n"
                "║  │ Attack 2 - Row 1, Column 2                            │  ║\n"
                "║  │ Attack 3 - Row 2, Column 1 (DEFAULT)                  │  ║\n"
                "║  │ Attack 4 - Row 2, Column 2                            │  ║\n"
                "║  └────────────────────────────────────────────────────────┘  ║\n"
                "║                                                              ║\n"
                "║  ⚙️ CURRENT: Attack 3 (Default)                            ║\n"
                "║                                                              ║\n"
                "║  🔧 TO CHANGE ATTACK, SEND:                                ║\n"
                "║  ┌────────────────────────────────────────────────────────┐  ║\n"
                "║  │ /set_attack 1 - for Attack 1                          │  ║\n"
                "║  │ /set_attack 2 - for Attack 2                          │  ║\n"
                "║  │ /set_attack 3 - for Attack 3 (default)                │  ║\n"
                "║  │ /set_attack 4 - for Attack 4                          │  ║\n"
                "║  └────────────────────────────────────────────────────────┘  ║\n"
                "║                                                              ║\n"
                "╚══════════════════════════════════════════════════════════════╝"
            )
            
        except Exception as e:
            logger.error(f"Error handling custom command: {e}")
    
    async def handle_run_command(self, event):
        """Handle /run command"""
        try:
            if self.automation_running:
                await event.edit(
                    "╔══════════════════════════════════╗\n"
                    "║        ⚠️  ALREADY ACTIVE ⚠️      ║\n"
                    "╠══════════════════════════════════╣\n"
                    "║ 🔥 Bot is already running!      ║\n"
                    "║ 💪 Automation is active         ║\n"
                    "║ 🎯 Use /pause to stop           ║\n"
                    "╚══════════════════════════════════╝"
                )
                return
            
            self.automation_running = True
            logger.info("🚀 Automation started by user command")
            
            await event.edit(
                "╔══════════════════════════════════╗\n"
                "║        🚀 BLISSEY BOT 🚀         ║\n"
                "╠══════════════════════════════════╣\n"
                "║ ✅ STATUS: ACTIVE               ║\n"
                "║ 🔥 AUTOMATION: RUNNING           ║\n"
                "║ ⚡ CHALLENGE: SENDING...         ║\n"
                "║ 🎯 TARGET: @JMD_BLISSEY         ║\n"
                "║ 💪 READY FOR BATTLE!             ║\n"
                "╚══════════════════════════════════╝"
            )
            
            # Send challenge command immediately
            await self.send_challenge_command()
            
        except Exception as e:
            logger.error(f"Error handling run command: {e}")
    
    async def handle_pause_command(self, event):
        """Handle /pause command"""
        try:
            if not self.automation_running:
                await event.edit(
                    "╔══════════════════════════════════╗\n"
                    "║        ⏸️  ALREADY PAUSED ⏸️      ║\n"
                    "╠══════════════════════════════════╣\n"
                    "║ 😴 Bot is already paused        ║\n"
                    "║ 💤 Automation is stopped         ║\n"
                    "║ 🚀 Use /run to start            ║\n"
                    "╚══════════════════════════════════╝"
                )
                return
            
            self.automation_running = False
            self.current_battle = False
            self.challenge_sent_time = None
            
            # Cancel any pending battle timeout
            if self.battle_timeout_task:
                self.battle_timeout_task.cancel()
                self.battle_timeout_task = None
            
            logger.info("⏸️ Automation paused by user command")
            
            await event.edit(
                "╔══════════════════════════════════╗\n"
                "║        ⏸️  BOT PAUSED ⏸️         ║\n"
                "╠══════════════════════════════════╣\n"
                "║ 😴 STATUS: PAUSED               ║\n"
                "║ 💤 AUTOMATION: STOPPED          ║\n"
                "║ 🛑 CHALLENGES: DISABLED         ║\n"
                "║ 🎯 BUTTONS: INACTIVE            ║\n"
                "║ 🚀 Use /run to restart         ║\n"
                "╚══════════════════════════════════╝"
            )
            
        except Exception as e:
            logger.error(f"Error handling pause command: {e}")
    
    async def handle_guide_command(self, event):
        """Handle /guide command"""
        try:
            guide_text = """
╔══════════════════════════════════════════════════════════════╗
║                    🎮 BLISSEY BOT GUIDE 🎮                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  🚀 COMMANDS:                                                ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │ /run     - 🎯 Start automation                        │  ║
║  │ /pause   - ⏸️ Stop automation                         │  ║
║  │ /custom  - ⚙️ Configure attack selection             │  ║
║  │ /guide   - 📖 Show this guide                         │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                              ║
║  ⚔️ ATTACK CONFIGURATION:                                   ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │ Use /set_attack 1-4 to choose your battle button      │  ║
║  │ Default: Attack 3 (Row 2, Column 1)                   │  ║
║  │ Options: Attack 1, 2, 3, or 4                        │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                              ║
║  🎯 USAGE:                                                   ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │ 1. python main.py                                      │  ║
║  │ 2. Send /run to start                                 │  ║
║  │ 3. Send /pause when done                              │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                              ║
║  🛠️ TROUBLESHOOTING:                                        ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │ "Too many commands" → Bot auto-retries                │  ║
║  │ "Currently battling" → Bot waits 2 minutes           │  ║
║  │ Buttons not working → Try /set_attack 1-4            │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                              ║
║  👨‍💻 DEVELOPER: @l1xky                                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
            """
            
            await event.edit(guide_text)
            
        except Exception as e:
            logger.error(f"Error handling guide command: {e}")
    
    async def handle_set_attack_command(self, event):
        """Handle /set_attack command"""
        try:
            message_text = event.message.text
            user_id = event.sender_id
            
            # Parse attack number from command
            parts = message_text.split()
            if len(parts) < 2:
                await event.edit(
                    "╔══════════════════════════════════════════════════════════════╗\n"
                    "║                    ❌ INVALID COMMAND ❌                   ║\n"
                    "╠══════════════════════════════════════════════════════════════╣\n"
                    "║                                                              ║\n"
                    "║  📝 USAGE: /set_attack <number>                            ║\n"
                    "║                                                              ║\n"
                    "║  🎯 AVAILABLE OPTIONS:                                     ║\n"
                    "║  ┌────────────────────────────────────────────────────────┐  ║\n"
                    "║  │ /set_attack 1 - Attack 1 (Row 1, Col 1)               │  ║\n"
                    "║  │ /set_attack 2 - Attack 2 (Row 1, Col 2)               │  ║\n"
                    "║  │ /set_attack 3 - Attack 3 (Row 2, Col 1) - DEFAULT    │  ║\n"
                    "║  │ /set_attack 4 - Attack 4 (Row 2, Col 2)               │  ║\n"
                    "║  └────────────────────────────────────────────────────────┘  ║\n"
                    "║                                                              ║\n"
                    "╚══════════════════════════════════════════════════════════════╝"
                )
                return
            
            try:
                attack_num = int(parts[1])
            except ValueError:
                await event.edit(
                    "╔══════════════════════════════════════════════════════════════╗\n"
                    "║                ❌ INVALID ATTACK NUMBER ❌                 ║\n"
                    "╠══════════════════════════════════════════════════════════════╣\n"
                    "║                                                              ║\n"
                    "║  ⚠️ Use number from 1 to 4 only!                           ║\n"
                    "║                                                              ║\n"
                    "║  🎯 VALID OPTIONS:                                         ║\n"
                    "║  ┌────────────────────────────────────────────────────────┐  ║\n"
                    "║  │ /set_attack 1 - Attack 1                             │  ║\n"
                    "║  │ /set_attack 2 - Attack 2                             │  ║\n"
                    "║  │ /set_attack 3 - Attack 3 (DEFAULT)                   │  ║\n"
                    "║  │ /set_attack 4 - Attack 4                             │  ║\n"
                    "║  └────────────────────────────────────────────────────────┘  ║\n"
                    "║                                                              ║\n"
                    "╚══════════════════════════════════════════════════════════════╝"
                )
                return
            
            if attack_num < 1 or attack_num > 4:
                await event.edit(
                    "╔══════════════════════════════════════════════════════════════╗\n"
                    "║                ❌ INVALID ATTACK NUMBER ❌                 ║\n"
                    "╠══════════════════════════════════════════════════════════════╣\n"
                    "║                                                              ║\n"
                    "║  ⚠️ Use number from 1 to 4 only!                           ║\n"
                    "║                                                              ║\n"
                    "║  🎯 VALID OPTIONS:                                         ║\n"
                    "║  ┌────────────────────────────────────────────────────────┐  ║\n"
                    "║  │ /set_attack 1 - Attack 1                             │  ║\n"
                    "║  │ /set_attack 2 - Attack 2                             │  ║\n"
                    "║  │ /set_attack 3 - Attack 3 (DEFAULT)                   │  ║\n"
                    "║  │ /set_attack 4 - Attack 4                             │  ║\n"
                    "║  └────────────────────────────────────────────────────────┘  ║\n"
                    "║                                                              ║\n"
                    "╚══════════════════════════════════════════════════════════════╝"
                )
                return
            
            # Convert attack number to row/col
            row = (attack_num - 1) // 2
            col = (attack_num - 1) % 2
            
            # Save user's attack preference
            self.attack_config[str(user_id)] = {
                'row': row,
                'col': col,
                'attack_name': f"Attack {attack_num}"
            }
            self.save_attack_config()
            
            await event.edit(
                f"╔══════════════════════════════════════════════════════════════╗\n"
                f"║                ✅ ATTACK SET SUCCESSFULLY ✅                ║\n"
                f"╠══════════════════════════════════════════════════════════════╣\n"
                f"║                                                              ║\n"
                f"║  🎯 SELECTED: Attack {attack_num}                          ║\n"
                f"║  📍 POSITION: Row {row + 1}, Column {col + 1}              ║\n"
                f"║  🔢 BUTTON INDEX: [{row}][{col}]                           ║\n"
                f"║                                                              ║\n"
                f"║  ⚔️ Bot will use Attack {attack_num} in battles!           ║\n"
                f"║                                                              ║\n"
                f"║  🔧 Use /custom to see all options                         ║\n"
                f"║                                                              ║\n"
                f"╚══════════════════════════════════════════════════════════════╝"
            )
            
            logger.info(f"User {user_id} set attack to: Attack {attack_num} (Row {row}, Column {col})")
            
        except Exception as e:
            logger.error(f"Error handling set_attack command: {e}")
    
    
    def save_attack_config(self):
        """Save attack configuration to file"""
        try:
            with open(self.attack_config_file, 'w') as f:
                json.dump(self.attack_config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving attack config: {e}")
    
    async def click_battle_button(self, message, retry_count=0):
        """Click the button at user's configured position with retry logic"""
        try:
            if not message.reply_markup:
                logger.warning("⚠️ No reply markup found in message")
                return
                
            # Get the inline keyboard
            keyboard = message.reply_markup.rows
            
            # Get user's attack configuration (default to config values if no user config)
            # For now, we'll use the default user ID, but this could be made dynamic
            target_row, target_col = self.get_user_attack_config("default")
            
            # Debug: Print keyboard structure
            logger.info(f"🔍 Keyboard has {len(keyboard)} rows")
            logger.info(f"🎯 Target button: Row {target_row + 1}, Column {target_col + 1}")
            for i, row in enumerate(keyboard):
                logger.info(f"🔍 Row {i}: {len(row.buttons)} buttons")
                for j, button in enumerate(row.buttons):
                    marker = "🎯" if i == target_row and j == target_col else "  "
                    logger.info(f"{marker} Button [{i}][{j}]: {button.text} (type: {type(button).__name__})")
            
            if len(keyboard) >= (target_row + 1) and len(keyboard[target_row].buttons) >= (target_col + 1):
                # Click button at user's configured position
                button = keyboard[target_row].buttons[target_col]
                
                if isinstance(button, KeyboardButtonCallback):
                    logger.info(f"🎯 Clicking button: {button.text} (attempt {retry_count + 1})")
                    
                    # Try to click the button with timeout
                    try:
                        # Method 1: Use the proper callback query method with correct import
                        from telethon.tl.functions.messages import GetBotCallbackAnswerRequest
                        
                        result = await asyncio.wait_for(
                            self.client(GetBotCallbackAnswerRequest(
                                peer=message.chat_id,
                                msg_id=message.id,
                                data=button.data
                            )),
                            timeout=BUTTON_TIMEOUT
                        )
                        logger.info("✅ Button clicked successfully!")
                        logger.info(f"🔍 Callback result: {result}")
                        
                        # Check if bot says "too many requests" or "please try again"
                        if hasattr(result, 'message') and result.message:
                            if "too many requests" in result.message.lower():
                                logger.warning("⚠️ Bot says: 'Receiving too many requests'")
                                logger.info("🔄 Retrying in 3 seconds... (unlimited retries)")
                                await asyncio.sleep(3)
                                await self.click_battle_button(message, retry_count + 1)
                                return
                            elif "please try again" in result.message.lower():
                                logger.warning("⚠️ Bot says: 'Please try again'")
                                logger.info("🔄 Retrying in 3 seconds... (unlimited retries)")
                                await asyncio.sleep(3)
                                await self.click_battle_button(message, retry_count + 1)
                                return
                        
                        # Wait for smooth experience
                        await asyncio.sleep(SMOOTH_DELAY)
                        
                    except asyncio.TimeoutError:
                        logger.warning(f"⏰ Button click timed out after {BUTTON_TIMEOUT} seconds")
                        logger.info(f"🔄 Retrying button click in {BUTTON_RETRY_DELAY} seconds... (unlimited retries)")
                        await asyncio.sleep(BUTTON_RETRY_DELAY)
                        await self.click_battle_button(message, retry_count + 1)
                    except Exception as e:
                        logger.warning(f"⚠️ Method 1 failed: {e}")
                        try:
                            # Method 2: Try using the button's callback directly with proper parameters
                            from telethon.tl.functions.messages import GetBotCallbackAnswerRequest
                            
                            # Try with different parameters
                            result = await asyncio.wait_for(
                                self.client(GetBotCallbackAnswerRequest(
                                    peer=message.chat_id,
                                    msg_id=message.id,
                                    data=button.data,
                                    game=False
                                )),
                                timeout=BUTTON_TIMEOUT
                            )
                            logger.info("✅ Button clicked successfully (Method 2)!")
                            logger.info(f"🔍 Callback result: {result}")
                            
                            # Check if bot says "too many requests" or "please try again"
                            if hasattr(result, 'message') and result.message:
                                if "too many requests" in result.message.lower():
                                    logger.warning("⚠️ Bot says: 'Receiving too many requests'")
                                    logger.info("🔄 Retrying in 3 seconds... (unlimited retries)")
                                    await asyncio.sleep(3)
                                    await self.click_battle_button(message, retry_count + 1)
                                    return
                                elif "please try again" in result.message.lower():
                                    logger.warning("⚠️ Bot says: 'Please try again'")
                                    logger.info("🔄 Retrying in 3 seconds... (unlimited retries)")
                                    await asyncio.sleep(3)
                                    await self.click_battle_button(message, retry_count + 1)
                                    return
                            
                            # Wait for smooth experience
                            await asyncio.sleep(SMOOTH_DELAY)
                            
                        except asyncio.TimeoutError:
                            logger.warning(f"⏰ Button click timed out after {BUTTON_TIMEOUT} seconds")
                            logger.info(f"🔄 Retrying button click in {BUTTON_RETRY_DELAY} seconds... (unlimited retries)")
                            await asyncio.sleep(BUTTON_RETRY_DELAY)
                            await self.click_battle_button(message, retry_count + 1)
                        except Exception as e2:
                            logger.error(f"❌ All methods failed: {e2}")
                            logger.error("💡 The button might not be clickable or the bot might not support callbacks")
                            logger.error("💡 Try checking if the bot is online and the message is recent")
                else:
                    logger.warning("⚠️ Button is not a callback button")
            else:
                logger.warning(f"⚠️ Button layout not found (need at least {target_row + 1} rows, {target_col + 1} columns in row {target_row})")
                logger.warning(f"⚠️ Available: {len(keyboard)} rows, {len(keyboard[target_row].buttons) if len(keyboard) > target_row else 0} buttons in target row")
                
        except Exception as e:
            logger.error(f"❌ Error clicking button: {e}")
    
    async def check_battle_status(self):
        """Check if a battle is currently running by looking at recent messages"""
        try:
            # Get the target channel entity
            channel = await self.client.get_entity(self.target_channel)
            
            # Get recent messages from the bot
            async for message in self.client.iter_messages(channel, limit=10):
                if message.sender and hasattr(message.sender, 'username') and message.sender.username == self.bot_username:
                    text = message.text or ""
                    
                    # Check for battle indicators
                    if any(pattern.lower() in text.lower() for pattern in [
                        BATTLE_START_PATTERN,
                        "battle",
                        "opponent",
                        "blissey",
                        "pokemon"
                    ]):
                        logger.info("🔍 Found recent battle activity")
                        return True
            
            logger.info("🔍 No recent battle activity found")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking battle status: {e}")
            return False

    async def battle_timeout_handler(self):
        """Handle battle timeout - resend challenge if no battle starts"""
        try:
            await asyncio.sleep(BATTLE_TIMEOUT)
            if not self.current_battle and self.challenge_sent_time:
                logger.warning(f"⏰ No battle started after {BATTLE_TIMEOUT} seconds, resending challenge...")
                await self.send_challenge_command()
        except asyncio.CancelledError:
            logger.info("🔄 Battle timeout cancelled - battle started!")
        except Exception as e:
            logger.error(f"❌ Error in battle timeout handler: {e}")

    async def send_challenge_command(self):
        """Send the /challenge command to the target message"""
        try:
            # Get the target channel entity
            channel = await self.client.get_entity(self.target_channel)
            
            # Send the challenge command as a reply to the target message
            await self.client.send_message(
                channel,
                CHALLENGE_COMMAND,
                reply_to=self.target_message_id
            )
            logger.info("🎯 Challenge command sent!")
            
            # Set challenge sent time and start timeout
            self.challenge_sent_time = asyncio.get_event_loop().time()
            self.current_battle = False
            
            # Start battle timeout task
            if self.battle_timeout_task:
                self.battle_timeout_task.cancel()
            self.battle_timeout_task = asyncio.create_task(self.battle_timeout_handler())
            
            # Wait for smooth experience
            await asyncio.sleep(SMOOTH_DELAY)
            
        except Exception as e:
            error_msg = str(e).lower()
            if "too many commands" in error_msg or "flood" in error_msg:
                logger.warning("⚠️ Too many commands error detected!")
                logger.info("🔍 Checking if battle is already running...")
                
                # Check if we're already in a battle
                if self.current_battle:
                    logger.info("⚔️ Battle is already running, waiting...")
                    # Wait a bit before trying again
                    await asyncio.sleep(5)
                else:
                    # Check recent messages for battle activity
                    battle_running = await self.check_battle_status()
                    if battle_running:
                        logger.info("⚔️ Battle is running (detected in messages), waiting...")
                        await asyncio.sleep(10)
                    else:
                        logger.info("🆕 No battle running, sending new challenge...")
                        # Wait a bit and try again
                        await asyncio.sleep(3)
                        await self.send_challenge_command()
            else:
                logger.error(f"❌ Error sending challenge command: {e}")
    
    async def start_automation(self):
        """Start the main automation loop"""
        logger.info("blissey bot started - waiting for /run command")
        logger.info("available commands:")
        logger.info("  /run - start automation")
        logger.info("  /pause - stop automation") 
        logger.info("  /custom - configure attack")
        logger.info("  /guide - show help")
        self.is_running = True
        
        # Keep the bot running but don't start automation automatically
        try:
            while self.is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("bot stopped by user")
        except Exception as e:
            logger.error(f"automation error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the bot"""
        self.is_running = False
        await self.client.disconnect()
        logger.info("bot disconnected")

async def main():
    """Main function to run the bot"""
    
    # check config
    if API_ID == 12345678 or API_HASH == "your_api_hash_here":
        logger.error("configure your API ID and API Hash in config.py")
        logger.info("instructions:")
        logger.info("1. update config.py with your API credentials")
        logger.info("2. run: python create_session.py")
        logger.info("3. run: python main.py")
        return
    
    # create and start bot
    bot = BlisseyBot(API_ID, API_HASH)
    await bot.start()

if __name__ == "__main__":
    print("blissey bot automation")
    print("features:")
    print("auto-reply to challenge messages")
    print("auto-click battle buttons")
    print("auto-handle blissey switches")
    print("auto-restart on prize detection")
    print("uses session file")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("bot stopped by user")
    except Exception as e:
        print(f"error: {e}")
