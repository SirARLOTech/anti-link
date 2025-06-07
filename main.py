import os
from dotenv import load_dotenv
load_dotenv()


import discord
from discord.ext import commands
from discord import app_commands
import re
import datetime

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
guild_configs = {}

def is_admin():
    def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync failed: {e}")

@bot.tree.command(name="config-anti-link")
@is_admin()
@app_commands.describe(channel="Channel to monitor", punishment="Timeout, Kick, or Ban", duration="Timeout duration in minutes", enabled="Enable or disable anti-link")
async def config_anti_link(interaction: discord.Interaction, channel: discord.TextChannel, punishment: str, duration: int, enabled: bool):
    guild_configs[interaction.guild_id] = guild_configs.get(interaction.guild_id, {})
    guild_configs[interaction.guild_id]["anti_link"] = {
        "channel_id": channel.id,
        "punishment": punishment.lower(),
        "duration": duration,
        "enabled": enabled
    }
    await interaction.response.send_message(f"Anti-link set for {channel.mention}. Enabled: {enabled}, Punishment: {punishment}, Duration: {duration} mins")

@bot.tree.command(name="config-logs")
@is_admin()
@app_commands.describe(channel="Log channel", enabled="Enable or disable logging")
async def config_logs(interaction: discord.Interaction, channel: discord.TextChannel, enabled: bool):
    guild_configs[interaction.guild_id] = guild_configs.get(interaction.guild_id, {})
    guild_configs[interaction.guild_id]["logs"] = {
        "channel_id": channel.id,
        "enabled": enabled
    }
    await interaction.response.send_message(f"Logs set to {channel.mention}. Enabled: {enabled}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    config = guild_configs.get(message.guild.id, {}).get("anti_link", {})
    if config.get("enabled") and message.channel.id == config.get("channel_id"):
        if re.search(r"(https?://|discord\.gg/|gg/)", message.content):
            try:
                await message.delete()
            except Exception as e:
                print(f"Failed to delete message: {e}")

            await message.channel.send(
                f"Hello {message.author.mention}. Sending links is not allowed in this channel. "
                "Please refrain from sending anymore or it could result in a more severe punishment."
            )

            punishment = config.get("punishment")
            if punishment == "timeout":
                timeout_duration = datetime.timedelta(minutes=config.get("duration", 5))
                try:
                    await message.author.timeout(timeout_duration, reason="Sent link in restricted channel")
                except Exception as e:
                    print(f"Failed to timeout: {e}")

            elif punishment == "kick":
                try:
                    await message.author.kick(reason="Sent link in restricted channel")
                except Exception as e:
                    print(f"Failed to kick: {e}")

            elif punishment == "ban":
                try:
                    await message.author.ban(reason="Sent link in restricted channel")
                except Exception as e:
                    print(f"Failed to ban: {e}")

            logs_config = guild_configs.get(message.guild.id, {}).get("logs", {})
            if logs_config.get("enabled"):
                log_channel = bot.get_channel(logs_config.get("channel_id"))
                if log_channel:
                    await log_channel.send(
                        f"**User:** {message.author.name}\n"
                        f"**Channel:** {message.channel.name}\n"
                        f"**Time:** {message.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"**Link:** {message.content}\n"
                        f"**Punishment:** {punishment.capitalize()}"
                    )

    await bot.process_commands(message)  # ← This is the key line you were missing

bot.run(os.getenv("DISCORD_TOKEN"))
