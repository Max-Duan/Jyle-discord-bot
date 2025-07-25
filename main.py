from dotenv import load_dotenv
load_dotenv()
import discord
from discord.ext import commands
import openai
from openai import OpenAI
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
        
        # Set up OpenAI client
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        
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
        
        # Store recent teacher DMs to track context (Guild ID, Channel ID)
        # This will map teacher DM message ID to context: {dm_message_id: {'guild_id': ..., 'channel_id': ..., 'student_id': ...}}
        # For simplicity, we'll rely on the teacher including IDs in their !reply command,
        # but a persistent storage could map the teacher's DM message to context for easier replies.
        
        self.setup_events()
        self.setup_commands()
    
    async def send_teacher_dm(self, user, channel, question, command_used):
        """Send a DM to the teacher with the student's question and context."""
        if not self.teacher_id or not self.teacher_dm_enabled:
            return
        
        try:
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
                
                guild_id = channel.guild.id if isinstance(channel, discord.TextChannel) else None # Store guild_id
                channel_id = channel.id # Store channel_id
                
                guild_name = channel.guild.name if isinstance(channel, discord.TextChannel) else "Direct Message"
                channel_name = channel.name if isinstance(channel, discord.TextChannel) else "Direct Message"
                
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
                
                # Add hidden fields for context. Using a specific format in footer.
                # This makes it easier for the teacher to copy-paste or for the bot to parse.
                embed.set_footer(text=f"Teacher Alert System | GuildID:{guild_id} | ChannelID:{channel_id} | StudentID:{user.id}")
                
                await teacher.send(embed=embed)
                logger.info(f"Teacher DM sent for question from {user.name} to GuildID:{guild_id}, ChannelID:{channel_id}")
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
            
            # --- NEW: Handle DM replies from the teacher ---
            if isinstance(message.channel, discord.DMChannel) and str(message.author.id) == self.teacher_id:
                logger.info(f"Received DM from teacher: {message.content}")
                
                # Teacher reply command format: !reply <guild_id> <channel_id> <message>
                # Example: !reply 1234567890 9876543210 This is the answer to your question.
                if message.content.lower().startswith('!reply'):
                    parts = message.content.split(' ', 3) # Split into 4 parts: !reply, guild_id, channel_id, message
                    if len(parts) >= 4:
                        try:
                            guild_id = int(parts[1])
                            channel_id = int(parts[2])
                            teacher_response_text = parts[3]
                            
                            guild = self.bot.get_guild(guild_id)
                            if not guild:
                                guild = await self.bot.fetch_guild(guild_id) # Try to fetch if not in cache
                            
                            if guild:
                                channel = guild.get_channel(channel_id)
                                if not channel:
                                    channel = await guild.fetch_channel(channel_id) # Try to fetch if not in cache
                                
                                if channel and isinstance(channel, discord.TextChannel):
                                    response_embed = discord.Embed(
                                        title="👨‍🏫 Teacher's Response",
                                        description=teacher_response_text,
                                        color=0xffa500, # Orange color for teacher response
                                        timestamp=datetime.utcnow()
                                    )
                                    response_embed.set_footer(text=f"Sent by {message.author.display_name}")
                                    await channel.send(embed=response_embed)
                                    await message.channel.send(f"✅ Your response has been sent to #{channel.name} in {guild.name}.")
                                    logger.info(f"Teacher's response sent to Guild:{guild_id}, Channel:{channel_id}")
                                else:
                                    await message.channel.send("❌ Could not find the specified channel. Make sure the Channel ID is correct and I have access to it.")
                                    logger.warning(f"Teacher DM reply: Channel {channel_id} not found or not a text channel in Guild {guild_id}.")
                            else:
                                await message.channel.send("❌ Could not find the specified server. Make sure the Guild ID is correct.")
                                logger.warning(f"Teacher DM reply: Guild {guild_id} not found.")
                        except ValueError:
                            await message.channel.send("❌ Invalid Guild ID or Channel ID format. Please use `!reply <guild_id> <channel_id> <your message>`.")
                        except Exception as e:
                            logger.error(f"Error processing teacher DM reply: {e}")
                            await message.channel.send(f"An unexpected error occurred: {e}")
                    else:
                        await message.channel.send("❌ Invalid `!reply` command format. Please use `!reply <guild_id> <channel_id> <your message>`.")
                return # Stop processing if it's a teacher DM command

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
                
                try:
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
                    logger.error(f"Error getting AI response for question command: {e}")
                    await ctx.send("Sorry, Jyle couldn't generate a quick response right now. But your teacher has still been notified!")
        
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
                name="!roast @
