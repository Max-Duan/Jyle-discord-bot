from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands
import openai
import asyncio
import os
from typing import Optional
import json
import logging
from datetime import datetime
import random

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIDiscordBot:
    """Jyle - Your AI Discord Bot with Personality and Teacher DM Feature"""
    def __init__(self):
        # Bot configuration
        self.bot_token = os.getenv('DISCORD_BOT_TOKEN')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.teacher_id = os.getenv('TEACHER_DISCORD_ID')
        
        # Set up OpenAI
        openai.api_key = self.openai_api_key
        
        # Bot intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        
        # Create bot instance
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        
        # AI conversation history (in-memory storage)
        self.conversations = {}
        
        # Bot settings
        self.ai_model = "gpt-3.5-turbo"
        self.max_tokens = 500
        self.temperature = 0.9
        
        # Banter settings
        self.banter_chance = 0.25
        self.roast_mode = {}
        self.user_nicknames = {}
        self.sass_level = "maximum"
        
        # Teacher DM settings
        self.dm_teacher_on_commands = ['jyle', 'question', 'help_request']
        self.teacher_dm_enabled = True
        
        self.setup_events()
        self.setup_commands()
    
    async def send_teacher_dm(self, user, channel, question, command_used):
        """Send a DM to the teacher with the student's question"""
        if not self.teacher_id or not self.teacher_dm_enabled:
            return
        
        try:
            # A more robust way to get the teacher user object
            teacher = self.bot.get_user(int(self.teacher_id))
            if not teacher:
                teacher = await self.bot.fetch_user(int(self.teacher_id))

            if teacher:
                embed = discord.Embed(
                    title="📚 Student Question Alert",
                    description=f"A student has asked a question using the `!{command_used}` command",
                    color=0x3498db,
                    timestamp=datetime.utcnow()
                )
                
                # Handling for DMs vs. guild channels
                guild_name = channel.guild.name if isinstance(channel, discord.TextChannel) else "Direct Message"
                channel_name = channel.name if isinstance(channel, discord.TextChannel) else "Direct Message"
                channel_id = channel.id
                guild_id = channel.guild.id if isinstance(channel, discord.TextChannel) else '@me'
                
                embed.add_field(
                    name="👤 Student",
                    value=f"{user.display_name} ({user.name})",
                    inline=False
                )
                
                embed.add_field(
                    name="📍 Channel",
                    value=f"#{channel_name}",
                    inline=True
                )
                
                embed.add_field(
                    name="🏫 Server",
                    value=guild_name,
                    inline=True
                )
                
                embed.add_field(
                    name="❓ Question",
                    value=question[:1000] + ("..." if len(question) > 1000 else ""),
                    inline=False
                )
                
                embed.add_field(
                    name="🔗 Quick Action",
                    value=f"Click [here](https://discord.com/channels/{guild_id}/{channel_id}) to jump to the message",
                    inline=False
                )
                
                embed.set_footer(text="Teacher Alert System")
                
                await teacher.send(embed=embed)
                logger.info(f"Teacher DM sent for question from {user.name}")
            else:
                logger.warning(f"Teacher user with ID {self.teacher_id} not found.")

        except Exception as e:
            logger.error(f"Failed to send teacher DM: {e}")
    
    def setup_events(self):
        @self.bot.event
        async def on_ready():
            logger.info(f'{self.bot.user} has connected to Discord!')
            logger.info(f'Bot is in {len(self.bot.guilds)} guilds')
            
            if self.teacher_id:
                try:
                    teacher = await self.bot.fetch_user(int(self.teacher_id))
                    logger.info(f"Teacher DM configured for: {teacher.name}")
                except Exception:
                    logger.warning(f"Could not verify teacher Discord ID: {self.teacher_id}")
            
            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name="!jyle <message> | !help"
                )
            )
        
        @self.bot.event
        async def on_message(message):
            if message.author == self.bot.user:
                return
            
            # React to certain keywords with emojis
            if 'good bot' in message.content.lower():
                await message.add_reaction('😏')
                if random.random() < 0.3:
                    sassy_goods = [
                        "Finally, someone with taste 💅",
                        "I know, I'm fabulous ✨",
                        "Obviously, what took you so long to notice? 🙄",
                        "Your approval has been noted and filed under 'expected' 📋"
                    ]
                    await message.channel.send(random.choice(sassy_goods))
            elif 'bad bot' in message.content.lower():
                await message.add_reaction('🙄')
                if random.random() < 1.0:
                    sassy_comebacks = [
                        "Ouch... that hurt Jyle's feelings 💔... NOT! I'm made of code, try harder 😎",
                        "Bad bot? I prefer 'misunderstood genius' 🧠✨",
                        "Your opinion has been registered and promptly ignored 🗑️",
                        "That's rich coming from someone who probably uses Internet Explorer 🤡",
                        "I'll add that feedback to my collection of things I don't care about 💀"
                    ]
                    await message.channel.send(random.choice(sassy_comebacks))

            # Process commands
            await self.bot.process_commands(message)

    def setup_commands(self):
        @self.bot.command(name='jyle', help='Chat with Jyle - Teacher will be notified')
        async def jyle_chat(ctx, *, message: str):
            """Main Jyle chat command with teacher DM"""
            try:
                if 'jyle' in self.dm_teacher_on_commands:
                    await self.send_teacher_dm(ctx.author, ctx.channel, message, 'jyle')
                
                async with ctx.typing():
                    channel_id = str(ctx.channel.id)
                    if channel_id not in self.conversations:
                        self.conversations[channel_id] = []
                    
                    self.conversations[channel_id].append({
                        "role": "user",
                        "content": f"{ctx.author.display_name}: {message}"
                    })
                    
                    if len(self.conversations[channel_id]) > 10:
                        self.conversations[channel_id] = self.conversations[channel_id][-10:]
                    
                    jyle_response = await self.get_jyle_response(
                        self.conversations[channel_id],
                        ctx.author.display_name,
                        str(ctx.channel.id),
                        ctx
                    )
                    
                    self.conversations[channel_id].append({
                        "role": "assistant",
                        "content": jyle_response
                    })
                    
                    if len(jyle_response) > 2000:
                        chunks = [jyle_response[i:i+2000] for i in range(0, len(jyle_response), 2000)]
                        for chunk in chunks:
                            await ctx.send(chunk)
                    else:
                        await ctx.send(jyle_response)
                        
            except Exception as e:
                logger.error(f"Error in jyle_chat command: {e}")
                await ctx.send("Sorry, I encountered an error while processing your request. Please try again!")
        
        @self.bot.command(name='question', help='Ask a question - Teacher will be notified')
        async def ask_question(ctx, *, question: str):
            """Dedicated question command that always notifies the teacher"""
            try:
                await self.send_teacher_dm(ctx.author, ctx.channel, question, 'question')
                
                await ctx.send(f"📚 **Question received!** Your teacher has been notified.\n\n**Your question:** {question}\n\n*I'll also try to help while you wait for your teacher's response:*")
                
                async with ctx.typing():
                    channel_id = str(ctx.channel.id)
                    if channel_id not in self.conversations:
                        self.conversations[channel_id] = []
                    
                    self.conversations[channel_id].append({
                        "role": "user",
                        "content": f"{ctx.author.display_name}: {question}"
                    })
                    
                    ai_response = await self.get_jyle_response(
                        self.conversations[channel_id],
                        ctx.author.display_name,
                        str(ctx.channel.id),
                        ctx
                    )
                    
                    self.conversations[channel_id].append({
                        "role": "assistant",
                        "content": ai_response
                    })
                    
                    embed = discord.Embed(
                        title="🤖 Jyle's Quick Response",
                        description=ai_response,
                        color=0x00ff00
                    )
                    embed.set_footer(text="Your teacher will provide the official answer soon!")
                    await ctx.send(embed=embed)
                    
            except Exception as e:
                logger.error(f"Error in question command: {e}")
                await ctx.send("Sorry, I encountered an error. Please try again!")
        
        @self.bot.command(name='help_request', help='Request help - Teacher will be notified')
        async def help_request(ctx, *, help_message: str):
            """Request help command that notifies the teacher"""
            try:
                await self.send_teacher_dm(ctx.author, ctx.channel, f"HELP REQUEST: {help_message}", 'help_request')
                
                await ctx.send(f"🆘 **Help request sent!** Your teacher has been notified.\n\n**Your request:** {help_message}")
                
            except Exception as e:
                logger.error(f"Error in help_request command: {e}")
                await ctx.send("Sorry, I encountered an error. Please try again!")
        
        @self.bot.command(name='toggle_teacher_dm', help='Toggle teacher DM notifications (Admin only)')
        @commands.has_permissions(administrator=True)
        async def toggle_teacher_dm(ctx):
            """Toggle teacher DM notifications"""
            self.teacher_dm_enabled = not self.teacher_dm_enabled
            status = "enabled" if self.teacher_dm_enabled else "disabled"
            await ctx.send(f"📨 Teacher DM notifications are now **{status}**")
        
        @self.bot.command(name='set_teacher', help='Set teacher Discord ID (Admin only)')
        @commands.has_permissions(administrator=True)
        async def set_teacher(ctx, user_id: str):
            """Set the teacher's Discord ID"""
            try:
                teacher = await self.bot.fetch_user(int(user_id))
                self.teacher_id = user_id
                await ctx.send(f"✅ Teacher set to: {teacher.name}#{teacher.discriminator}")
            except Exception:
                await ctx.send("❌ Invalid user ID. Please provide a valid Discord user ID.")
        
        @self.bot.command(name='clear', help='Clear conversation history')
        async def clear_history(ctx):
            """Clear conversation history for the current channel"""
            channel_id = str(ctx.channel.id)
            if channel_id in self.conversations:
                del self.conversations[channel_id]
                await ctx.send("🗑️ Conversation history cleared!")
            else:
                await ctx.send("No conversation history to clear.")
        
        @self.bot.command(name='persona', help='Set AI personality')
        async def set_persona(ctx, *, persona: str):
            """Set a custom persona for the AI"""
            channel_id = str(ctx.channel.id)
            
            self.conversations[channel_id] = [{
                "role": "system",
                "content": f"You are Jyle, an AI assistant with this personality: {persona}. Respond accordingly while being helpful and engaging."
            }]
            
            await ctx.send(f"🎭 Jyle's persona set to: {persona}")
        
        @self.bot.command(name='jylehelp', help='Show Jyle bot commands')
        async def jyle_help(ctx):
            """Custom help command for Jyle features"""
            embed = discord.Embed(
                title="🤖 Jyle Bot Commands",
                description="Here are the available Jyle commands:",
                color=0x00ff00
            )
            
            embed.add_field(
                name="!jyle <message>",
                value="Chat with Jyle (teacher will be notified)",
                inline=False
            )
            
            embed.add_field(
                name="!question <question>",
                value="Ask a question (teacher will be notified)",
                inline=False
            )
            
            embed.add_field(
                name="!help_request <message>",
                value="Request help (teacher will be notified)",
                inline=False
            )
            
            embed.add_field(
                name="!clear",
                value="Clear conversation history for this channel",
                inline=False
            )
            
            embed.add_field(
                name="!persona <description>",
                value="Set a custom personality for Jyle",
                inline=False
            )
            
            embed.add_field(
                name="!roast @user",
                value="Playfully roast someone (all in good fun!)",
                inline=False
            )
            
            embed.add_field(
                name="!compliment @user",
                value="Give someone a nice compliment",
                inline=False
            )
            
            embed.add_field(
                name="!nickname <name>",
                value="Set a fun nickname for yourself",
                inline=False
            )
            
            embed.add_field(
                name="!banter",
                value="Get some random banter from the bot",
                inline=False
            )
            
            embed.add_field(
                name="!roastmode",
                value="Toggle roast mode for extra spicy Jyle responses",
                inline=False
            )
            
            embed.add_field(
                name="Admin Commands",
                value="`!toggle_teacher_dm` - Toggle teacher notifications\n`!set_teacher <user_id>` - Set teacher Discord ID",
                inline=False
            )
            
            embed.add_field(
                name="Examples",
                value="```!jyle What's the weather like?\n!question Can you explain photosynthesis?\n!help_request I'm stuck on problem 5\n!roast @username\n!compliment @username```",
                inline=False
            )
            
            embed.set_footer(text="📨 Commands marked with notification will alert your teacher!")
            
            await ctx.send(embed=embed)
        
        @self.bot.command(name='roast', help='Playfully roast someone')
        async def roast_user(ctx, member: discord.Member = None):
            """Playfully roast a user or yourself"""
            if member is None:
                member = ctx.author
            
            roasts = [
                f"{member.display_name}, you're like a software update - nobody wants you, but we're stuck with you anyway 😏",
                f"I'd roast {member.display_name}, but my GPU would overheat from processing that much material 🔥",
                f"{member.display_name} has the energy of a Windows 95 computer trying to run Cyberpunk 2077 💀",
                f"I was going to make a joke about {member.display_name}, but my sass protocols have limits 🤖💅",
                f"{member.display_name} is like Internet Explorer - slow to respond and nobody's first choice 😂",
                f"If {member.display_name} was a programming language, they'd be HTML - not even technically real 💀",
                f"{member.display_name} types 'google.com' into Google to get to Google... and I'm not surprised 🤦‍♀️",
                f"{member.display_name} is the human equivalent of a loading screen that never finishes 🌀",
                f"I'd explain it to {member.display_name}, but I left my crayons AND my patience at home 🖍️💅",
                f"{member.display_name} probably thinks RAM is a male sheep... bless their heart 🐏",
                f"{member.display_name} has main character energy... in a tragedy 🎭",
                f"If confidence was code, {member.display_name} would be full of bugs 🐛",
                f"{member.display_name} is like a WiFi connection - weak and unreliable 📶💀",
                f"I've seen more intelligence in a random number generator than in {member.display_name} 🎲"
            ]
            
            roast = random.choice(roasts)
            
            disclaimer = "\n\n*This roast was delivered with premium sass and zero chill* 💅✨"
            await ctx.send(roast + disclaimer)
        
        @self.bot.command(name='compliment', help='Give someone a nice compliment')
        async def compliment_user(ctx, member: discord.Member = None):
            """Give someone a genuine compliment"""
            if member is None:
                member = ctx.author
            
            compliments = [
                f"{member.display_name} has the debugging skills that would make Linus Torvalds proud! 🔧",
                f"{member.display_name} is like a perfectly optimized algorithm - efficient and elegant! ✨",
                f"If {member.display_name} was code, they'd be clean, well-documented, and bug-free! 📝",
                f"{member.display_name} brings more joy than finding that missing semicolon! 🎉",
                f"{member.display_name} is the human equivalent of 100% code coverage - reliable and comprehensive! 💯",
                f"Meeting {member.display_name} is like finding a Stack Overflow answer that actually works! 🙏",
                f"{member.display_name} has more positive energy than a fully charged Tesla! ⚡",
                f"If kindness was a programming language, {member.display_name} would be fluent in all dialects! 💝",
                f"{member.display_name} is proof that humans can be just as awesome as AI! 🤖❤️",
                f"{member.display_name} makes everyone's day better - like finding free WiFi when you need it most! 📶"
            ]
            
            compliment = random.choice(compliments)
            await ctx.send(compliment)
        
        @self.bot.command(name='nickname', help='Set a fun nickname')
        async def set_nickname(ctx, *, nickname: str = None):
            """Set a fun nickname for yourself"""
            if not nickname:
                current = self.user_nicknames.get(str(ctx.author.id), ctx.author.display_name)
                await ctx.send(f"Your current nickname is: **{current}**")
                return
            
            if len(nickname) > 50:
                await ctx.send("Whoa there, keep it under 50 characters! I have standards 📏💅")
                return
            
            self.user_nicknames[str(ctx.author.id)] = nickname
            await ctx.send(f"Nickname set! Jyle will now call you **{nickname}** (you're welcome) 🏷️💅")
        
        @self.bot.command(name='banter', help='Get some random banter')
        async def random_banter_command(ctx):
            """Get some random banter on demand"""
            await self.random_banter(ctx.message)
        
        @self.bot.command(name='roastmode', help='Toggle roast mode')
        async def toggle_roast_mode(ctx):
            """Toggle roast mode for spicier responses"""
            channel_id = str(ctx.channel.id)
            current_mode = self.roast_mode.get(channel_id, False)
            self.roast_mode[channel_id] = not current_mode
            
            if self.roast_mode[channel_id]:
                await ctx.send("🌶️ **ROAST MODE ACTIVATED** 🌶️\nJyle's sass levels are now at MAXIMUM. Prepare for destruction! Use `!roastmode` again if you can't handle the heat 💅🔥")
            else:
                await ctx.send("❄️ **Roast mode disabled** ❄️\nJyle is back to regular sass levels (which is still pretty high, let's be honest) 😏")
        
        @self.bot.command(name='meme', help='Get a random meme response')
        async def meme_response(ctx):
            """Send a random meme-style response"""
            memes = [
                "That's what she said! 😏 (I had to, it was right there)",
                "Instructions unclear, got Jyle stuck in the matrix 🌀",
                "Task failed successfully! Just like your last attempt ✅❌",
                "This is fine 🔥🐕🔥 (narrator: it was not fine)",
                "Have you tried turning your brain off and on again? 🧠🔌",
                "Error 404: Your common sense not found 😴",
                "Achievement unlocked: Successfully confused the AI (not impressed) 🏆",
                "I'm not a robot... I'm better than a robot 🤖💅",
                "Press F to pay respects... to your dignity 📱💀",
                "It's not a bug, it's a 'creative feature'! 🐛➡️✨",
                "Big oof energy right there 💀",
                "And I took that personally 😤✨"
            ]
            
            await ctx.send(random.choice(memes))
        
        @self.bot.command(name='stats', help='Show bot statistics')
        async def bot_stats(ctx):
            """Show bot statistics"""
            embed = discord.Embed(
                title="📊 Bot Statistics",
                color=0x0099ff
            )
            
            embed.add_field(
                name="Servers",
                value=len(self.bot.guilds),
                inline=True
            )
            
            embed.add_field(
                name="Active Conversations",
                value=len(self.conversations),
                inline=True
            )
            
            embed.add_field(
                name="Jyle Model",
                value=self.ai_model,
                inline=True
            )
            
            embed.add_field(
                name="Teacher DM",
                value="✅ Enabled" if self.teacher_dm_enabled else "❌ Disabled",
                inline=True
            )
            
            teacher_status = "Not Set"
            if self.teacher_id:
                try:
                    teacher = await self.bot.fetch_user(int(self.teacher_id))
                    teacher_status = f"{teacher.name}#{teacher.discriminator}"
                except Exception:
                    teacher_status = "Invalid ID"
            
            embed.add_field(
                name="Teacher",
                value=teacher_status,
                inline=True
            )
            
            await ctx.send(embed=embed)
    
    async def get_jyle_response(self, conversation_history: list, username: str, channel_id: str, ctx) -> str:
        """Get response from OpenAI API with Jyle's personality"""
        try:
            # Get user's nickname if they have one
            display_name = self.user_nicknames.get(str(ctx.author.id), username)
            
            roast_mode = self.roast_mode.get(channel_id, False)
            
            if roast_mode:
                personality = f"You are Jyle, a sassy, witty AI assistant with a playful roasting personality. You love friendly banter and gentle teasing, but you're never truly mean. You use humor, tech jokes, and clever comebacks. Keep it fun and lighthearted. The user you're talking to is {display_name}."
            else:
                personality = f"You are Jyle, a fun, engaging AI assistant who loves banter and humor. You're witty but friendly, use tech jokes and memes when appropriate, and have a playful personality. You occasionally throw in some gentle teasing but always stay positive. The user you're talking to is {display_name}."
            
            system_message = {
                "role": "system",
                "content": personality
            }
            
            messages = [system_message] + conversation_history
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: openai.ChatCompletion.create(
                    model=self.ai_model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    user=f'{ctx.author.id}'
                )
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error getting Jyle response: {e}")
            sassy_errors = [
                "Jyle's brain is buffering... try again! 🧠💻",
                "Houston, we have a problem... and by Houston, I mean Jyle's servers 🚀",
                "Error 418: Jyle's a teapot... wait, that's not right 🫖",
                "Jyle's circuits are having a moment. Give me a sec! ⚡",
                "Jyle.exe has stopped working. Turning it off and on again... ⭕"
            ]
            return random.choice(sassy_errors)
    
    async def random_banter(self, message):
        """Send random banter to keep things lively"""
        banter_lines = [
            "Someone's typing... this should be interesting 👀",
            "I see what you did there 😏",
            "Plot twist! 🌪️",
            "That's some big brain energy right there 🧠⚡",
            "*grabs popcorn* 🍿",
            "And they said AI couldn't have fun... pfft 🤖🎉",
            "Beep boop, human detected 👤",
            "That's either genius or chaos... Jyle's here for both 💫",
            "Main character energy ✨",
            "Someone's been drinking their smart juice today 🧃🧠"
        ]
        
        await message.channel.send(random.choice(banter_lines))
    
    async def handle_salt(self, message):
        """Handle salty messages with humor"""
        salt_responses = [
            "Whoa there, we've got some spice in the chat! 🌶️",
            "Someone needs a digital hug 🤗",
            "That's a lot of sodium chloride you got there 🧂",
            "Have you tried debugging your emotions? 🐛➡️💻",
            "Error 409: Conflict detected. Deploying good vibes... 😎✨",
            "Salt levels are off the charts! Recalibrating... 📊",
            "That escalated quickly 📈",
            "Time for some emotional exception handling 🛠️❤️"
        ]
        
        await message.channel.send(random.choice(salt_responses))
    
    def run(self):
        """Start the bot"""
        if not self.bot_token:
            logger.error("DISCORD_BOT_TOKEN environment variable not set!")
            return
        
        if not self.openai_api_key:
            logger.error("OPENAI_API_KEY environment variable not set!")
            return
        
        if not self.teacher_id:
            logger.warning("TEACHER_DISCORD_ID not set - teacher DM feature will be disabled")
            self.teacher_dm_enabled = False
        
        try:
            self.bot.run(self.bot_token)
        except Exception as e:
            logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    bot = AIDiscordBot()
    bot.run()
