import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re
import json
import os
from datetime import timedelta


# ===== CONFIG FILE SETUP =====
CONFIG_FILE = "config.json"
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "warn_role": "Staff",
            "warn_log_channel": "warnings",
            "anti_link_channel": "allowed-links",
            "anti_link_punishment": "None",
            "anti_link_duration": 0,
            "anti_link_message": "Links are not allowed here!"
        }, f, indent=4)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

WARN_LOGS_FILE = "warn_logs.json"
if not os.path.exists(WARN_LOGS_FILE):
    with open(WARN_LOGS_FILE, "w") as f:
        json.dump({}, f)

# ===== DISCORD SETUP =====
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# ===== /ro-warn =====
@bot.tree.command(name="ro-warn")
@app_commands.describe(
    user="User to warn",
    reason="Reason for the warning",
    punishment="None or Timeout",
    duration="Duration in minutes (if timeout)",
    dm_user="Send a DM with the warning"
)
async def ro_warn(interaction: discord.Interaction, user: discord.Member, reason: str, punishment: str, duration: int = 0, dm_user: str = "Yes"):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    warn_role = discord.utils.get(interaction.guild.roles, name=config["warn_role"])
    if warn_role not in interaction.user.roles:
        await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
        return

    embed = discord.Embed(title="⚠️ User Warned", color=discord.Color.orange())
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=True)
    embed.add_field(name="Punishment", value=punishment, inline=True)
    embed.set_footer(text=f"Warned by {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed)

    if dm_user.lower() == "yes":
        try:
            await user.send(f"You were warned in **{interaction.guild.name}** for: {reason}")
        except:
            pass

    if punishment.lower() == "timeout" and duration > 0:
        try:
            await user.timeout(discord.utils.utcnow() + timedelta(minutes=duration), reason=reason)
        except Exception as e:
            await interaction.followup.send(f"Failed to timeout: {e}")

    log_channel = discord.utils.get(interaction.guild.text_channels, name=config["warn_log_channel"])
    if log_channel:
        await log_channel.send(embed=embed)
    with open(WARN_LOGS_FILE, "r") as f:
        warn_logs = json.load(f)

    user_logs = warn_logs.get(str(user.id), [])
    user_logs.append({
        "moderator": interaction.user.name,
        "reason": reason,
        "punishment": punishment,
        "duration": duration
    })
    warn_logs[str(user.id)] = user_logs

    with open(WARN_LOGS_FILE, "w") as f:
        json.dump(warn_logs, f, indent=4)

# ===== /ro-warn-config =====
@bot.tree.command(name="ro-warn-config")
@app_commands.describe(
    role="Role that can use /ro-warn",
    log_channel="Channel to log warnings"
)
async def ro_warn_config(interaction: discord.Interaction, role: discord.Role, log_channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    config["warn_role"] = role.name
    config["warn_log_channel"] = log_channel.name

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

    await interaction.response.send_message("✅ Warn configuration updated.", ephemeral=True)

# ===== /ro-anti-link =====
@bot.tree.command(name="ro-anti-link")
@app_commands.describe(
    channel="Channel where links are allowed",
    punishment="None or Timeout",
    duration="If Timeout, how long (minutes)",
    message="Warn message to display"
)
async def ro_anti_link(interaction: discord.Interaction, channel: discord.TextChannel, punishment: str, duration: int, message: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    config["anti_link_channel"] = channel.name
    config["anti_link_punishment"] = punishment
    config["anti_link_duration"] = duration
    config["anti_link_message"] = message

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

    await interaction.response.send_message("✅ Anti-link configuration updated.", ephemeral=True)

# ===== /ro-official-message =====
@bot.tree.command(name="ro-official-message")
@app_commands.describe(
    channel="Channel to send the message in",
    pings="Any pings (e.g., @everyone)",
    header="Title of the message",
    message="Main content",
    sender="Who it's from"
)
async def ro_official_message(interaction: discord.Interaction, channel: discord.TextChannel, pings: str, header: str, message: str, sender: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    embed = discord.Embed(title=header, description=message, color=discord.Color.blue())
    embed.set_footer(text=f"From: {sender}")
    await channel.send(content=pings, embed=embed)
    await interaction.response.send_message("✅ Message sent.", ephemeral=True)

# ===== Anti-Link Event Listener =====
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    link_regex = r"(https?://\S+)"
    if re.search(link_regex, message.content):
        if message.channel.name != config["anti_link_channel"]:
            await message.delete()
            punishment = config.get("anti_link_punishment", "None")
            duration = config.get("anti_link_duration", 0)
            warn_message = config.get("anti_link_message", "Links are not allowed here!")

            if punishment == "Timeout":
                try:
                    await message.author.timeout(discord.utils.utcnow() + timedelta(minutes=duration))
                except Exception as e:
                    print(f"Failed to timeout: {e}")

            await message.channel.send(f"{message.author.mention}, {warn_message}", delete_after=5)

    await bot.process_commands(message)


### Warn Logs

@bot.tree.command(name="ro-warn-logs")
@app_commands.describe(user="User to view warn logs for")
async def ro_warn_logs(interaction: discord.Interaction, user: discord.Member):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    warn_role = discord.utils.get(interaction.guild.roles, name=config["warn_role"])
    if warn_role not in interaction.user.roles:
        await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
        return

    with open(WARN_LOGS_FILE, "r") as f:
        warn_logs = json.load(f)

    user_logs = warn_logs.get(str(user.id), [])
    if not user_logs:
        await interaction.response.send_message("✅ No warnings found for this user.", ephemeral=True)
        return

    embed = discord.Embed(title=f"Warnings for {user.display_name}", color=discord.Color.orange())
    for i, log in enumerate(user_logs, 1):
        embed.add_field(
            name=f"Warning #{i}",
            value=f"**Reason:** {log['reason']}\n**Punishment:** {log['punishment']} ({log['duration']} min)\n**Moderator:** {log['moderator']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

### Remove Warn

@bot.tree.command(name="ro-warn-remove")
@app_commands.describe(user="User to remove warnings from")
async def ro_warn_remove(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return

    with open(WARN_LOGS_FILE, "r") as f:
        warn_logs = json.load(f)

    user_logs = warn_logs.get(str(user.id), [])
    if not user_logs:
        await interaction.response.send_message("✅ No warnings found for this user.", ephemeral=True)
        return

    class RemoveWarning(discord.ui.View):
        def __init__(self, logs):
            super().__init__(timeout=60)
            self.logs = logs
            for i, log in enumerate(self.logs):
                self.add_item(RemoveButton(index=i, label=f"#{i+1}: {log['reason'][:20]}"))

    class RemoveButton(discord.ui.Button):
        def __init__(self, index, label):
            super().__init__(label=label, style=discord.ButtonStyle.red, custom_id=str(index))
            self.index = index

        async def callback(self, interaction2: discord.Interaction):
            if interaction.user != interaction2.user:
                await interaction2.response.send_message("❌ You're not allowed to use this.", ephemeral=True)
                return

            removed = user_logs.pop(self.index)
            warn_logs[str(user.id)] = user_logs

            with open(WARN_LOGS_FILE, "w") as f:
                json.dump(warn_logs, f, indent=4)

            await interaction2.response.edit_message(content=f"✅ Removed warning: **{removed['reason']}**", view=None)

    view = RemoveWarning(user_logs)
    await interaction.response.send_message("⚠️ Select a warning to remove:", view=view, ephemeral=True)


# ===== RUN BOT =====
import os
bot.run(os.environ["DISCORD_TOKEN"])
