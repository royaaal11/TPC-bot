import discord
from discord.ext import commands
import re
import json
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

REVIEW_CHANNEL_ID = 1528778361361534986
MOD_LOG_CHANNEL_ID = 1528989369526915163

LINK_REGEX = r"(https?://\S+|discord\.gg/\S+|discord\.com/invite/\S+)"

# -----------------------------
# JSON Helpers
# -----------------------------

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


servers = load_json("vendors.json", {})

pending_links = load_json("pending_links.json", {})

stats_data = load_json(
    "stats.json",
    {
        "approved": 0,
        "rejected": 0
    }
)

submission_counter = (
    max([int(x) for x in pending_links.keys()], default=0) + 1
)

# -----------------------------
# Bot Setup
# -----------------------------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="?",
    intents=intents,
    help_command=None
)

# -----------------------------
# Events
# -----------------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message):
    global submission_counter

    if message.author.bot:
        return

    # Allow commands through
    if message.content.startswith("?"):
        await bot.process_commands(message)
        return

    # Allow mods/admins to post links freely
    if (
        message.author.guild_permissions.administrator
        or message.author.guild_permissions.manage_messages
    ):
        await bot.process_commands(message)
        return

    # Check links
    if re.search(LINK_REGEX, message.content, re.IGNORECASE):

        original_content = message.content
        original_channel = message.channel

        try:
            await message.delete()
        except discord.Forbidden:
            pass

        try:
            await message.author.send(
                "Thanks! Your link has been received and is awaiting moderator review ;>."
            )
        except discord.Forbidden:
            notice = await original_channel.send(
                f"{message.author.mention} Your link has been submitted for moderator review."
            )
            await notice.delete(delay=10)

        submission_id = str(submission_counter)
        submission_counter += 1

        pending_links[submission_id] = {
            "user_id": message.author.id,
            "channel_id": original_channel.id,
            "content": original_content
        }

        save_json("pending_links.json", pending_links)

        review_channel = bot.get_channel(REVIEW_CHANNEL_ID)

        if review_channel:
            await review_channel.send(
                f"**New Link Submission #{submission_id}**\n\n"
                f"User: {message.author}\n"
                f"Channel: {original_channel.mention}\n\n"
                f"{original_content}\n\n"
                f"`?approve {submission_id}`\n"
                f"`?reject {submission_id}`"
            )

        return

    await bot.process_commands(message)
    
# -----------------------------
# Vendor Management
# -----------------------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def addvendor(ctx, *, name):
    name = name.lower()

    if name in servers:
        await ctx.send("Vendor already exists.")
        return

    servers[name] = {}

    save_json("vendors.json", servers)

    await ctx.send("Vendor `{name}` added.")


@bot.command()
@commands.has_permissions(manage_messages=True)
async def setvendor(ctx, vendor, field, *, value):
    vendor = vendor.lower()
    field = field.lower()

    if vendor not in servers:
        await ctx.send("Vendor not found.")
        return

    servers[vendor][field] = value

    save_json("vendors.json", servers)

    await ctx.send(
        f"Updated `{field}` for vendor `{vendor}`."
    )


@bot.command()
@commands.has_permissions(manage_messages=True)
async def removevendor(ctx, *, vendor):
    vendor = vendor.lower()

    if vendor not in servers:
        await ctx.send("Vendor not found.")
        return

    del servers[vendor]

    save_json("vendors.json", servers)

    await ctx.send(f"Vendor `{vendor}` removed.")


@bot.command()
@commands.has_permissions(manage_messages=True)
async def removefield(ctx, vendor, field):
    vendor = vendor.lower()
    field = field.lower()

    if vendor not in servers:
        await ctx.send("Vendor not found.")
        return

    if field not in servers[vendor]:
        await ctx.send("Field not found.")
        return

    del servers[vendor][field]

    save_json("vendors.json", servers)

    await ctx.send(
        f"Removed `{field}` from `{vendor}`."
    )

# -----------------------------
# User Commands
# -----------------------------

@bot.command()
async def help(ctx):
    await ctx.send(
        "**Vendor Bot Commands**\n"
        "```"
        "?list                                  Show all available vendors\n"
        "?server <vendor>                       Get a vendor's Discord server\n"
        "```\n"
        "**Moderator Commands**\n"
        "```"
        "?addvendor <name>                      Add Vendor Information\n"
        "?setvendor <vendor> <field> <value>    Set Vendor Info\n"
        "?removevendor <name>                   Remove Vendor entirely\n"                
        "?removefield <vendor> <field>          Remove Vendor Info\n"
        "?pending                               View pending submissions\n"
        "?approve <id>                          Approve a submission\n"
        "?reject <id>                           Reject a submission\n"
        "?purge <amount>                        Delete messages [e.g. ?purge 10]\n"
        "?stats                                 View bot statistics\n"
        "```"
    )


@bot.command(name="list")
async def vendor_list(ctx):

    if not servers:
        await ctx.send("No vendors found.")
        return

    message = "**Vetted Vendors**\n\n"

    for name, info in servers.items():
        message += (
            f"• **{name.title()}**\n"
            f"🔗 {info.get('invite', 'No invite')}\n\n"
        )

    await ctx.send(message)


@bot.command()
async def server(ctx, *, name):

    vendor = servers.get(name.lower())

    if not vendor:
        await ctx.send("Vendor not found.")
        return

    message = f"📌 **{name.title()}**\n\n"

    for field, value in vendor.items():
        message += f"**{field.title()}:** {value}\n"

    await ctx.send(message)

# -----------------------------
# Stats
# -----------------------------

@bot.command()
async def stats(ctx):

    await ctx.send(
        f"**Server Stats**\n\n"
        f"Vendors: {len(servers)}\n"
        f"Pending: {len(pending_links)}\n"
        f"Approved: {stats_data['approved']}\n"
        f"Rejected: {stats_data['rejected']}"
    )

# -----------------------------
# Purge
# -----------------------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):

    if amount < 1:
        await ctx.send("Please enter a number greater than 0.")
        return

    if amount > 100:
        await ctx.send("Maximum purge amount is 100.")
        return

    await ctx.channel.purge(limit=amount + 1)

    log_channel = bot.get_channel(MOD_LOG_CHANNEL_ID)

    if log_channel:
        await log_channel.send(
            f"{ctx.author.mention} purged {amount} messages in {ctx.channel.mention}"
        )


@purge.error
async def purge_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need Manage Messages permission.")

# -----------------------------
# Pending Queue
# -----------------------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def pending(ctx):

    if not pending_links:
        await ctx.send("No pending submissions.")
        return

    message = "**Pending Submissions**\n\n"

    for submission_id, data in pending_links.items():
        message += f"#{submission_id} - {data['content'][:60]}\n"

    await ctx.send(message)

# -----------------------------
# Approve
# -----------------------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def approve(ctx, submission_id: int):

    submission_id = str(submission_id)

    if submission_id not in pending_links:
        await ctx.send("Submission not found.")
        return

    data = pending_links.pop(submission_id)

    save_json("pending_links.json", pending_links)

    stats_data["approved"] += 1
    save_json("stats.json", stats_data)

    channel = bot.get_channel(data["channel_id"])

    if channel:
        await channel.send(
            f"**Link shared by** <@{data['user_id']}>\n\n"
            f"{data['content']}"
        )

    try:
        user = await bot.fetch_user(data["user_id"])
        await user.send(
            f"Your link #{submission_id} has been approved and published."
        )
    except:
        pass

    log_channel = bot.get_channel(MOD_LOG_CHANNEL_ID)

    if log_channel:
        await log_channel.send(
            f"{ctx.author.mention} approved submission #{submission_id}"
        )

    await ctx.send(f"Approved submission #{submission_id}")

# -----------------------------
# Reject
# -----------------------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def reject(ctx, submission_id: int):

    submission_id = str(submission_id)

    if submission_id not in pending_links:
        await ctx.send("Submission not found.")
        return

    data = pending_links.pop(submission_id)

    save_json("pending_links.json", pending_links)

    stats_data["rejected"] += 1
    save_json("stats.json", stats_data)

    try:
        user = await bot.fetch_user(data["user_id"])
        await user.send(
            f"Your link #{submission_id} was not approved because it doesn't meet our rules."
        )
    except:
        pass

    log_channel = bot.get_channel(MOD_LOG_CHANNEL_ID)

    if log_channel:
        await log_channel.send(
            f"{ctx.author.mention} rejected submission #{submission_id}"
        )

    await ctx.send(f"Rejected submission #{submission_id}")
    
bot.run(TOKEN)