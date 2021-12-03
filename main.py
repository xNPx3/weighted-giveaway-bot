import discord
import discord.ext.commands as commands
import datetime
import time
import numpy as np
import json
import asyncio

#load config
with open('config.json', 'r') as f:
    config = json.load(f)

intents = discord.Intents.default()
intents.members = True
client = discord.ext.commands.Bot(
    command_prefix=config['prefix'], case_insensitive=True, intents=intents, help_command=None)

#help command
class Help(commands.MinimalHelpCommand):
    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            embed = discord.Embed(description=page, color=discord.Color.gold())
            await destination.send(embed=embed)
    

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

    activity = discord.Activity(
        name=config['status'], type=discord.ActivityType.playing)
    await client.change_presence(activity=activity)

    client.help_command = Help(no_category="Commands")


@client.event
async def on_reaction_add(reaction, user):
    try:
        with open(f'data/{str(reaction.message.guild.id)}.json', 'r') as f:
            give = json.load(f)
    except FileNotFoundError:
        with open(f'data/{str(reaction.message.guild.id)}.json', 'a+') as f:
            f.write("{}")
        with open(f'data/{str(reaction.message.guild.id)}.json', 'r') as f:
            give = json.load(f)

    #check if message is a giveaway
    if (str(reaction.message.id) in give) and (reaction.emoji == '🍉') and (user.bot == False) and (give[str(reaction.message.id)]['ended'] == False):
        # calculate entries
        entries = 1
        for r in config['roles']:
            role = reaction.message.guild.get_role(int(r))
            if role in user.roles:
                entries = entries + config['roles'][str(r)]

        # set entries
        give[str(reaction.message.id)]['reactions'][str(user.id)] = entries
        embed = discord.Embed(title=f'Entries confirmed for giveaway in `{reaction.message.guild.name}`', description=f'You have {entries} entries.', color=discord.Colour.gold())
        await user.send(embed=embed)

    with open(f'data/{str(reaction.message.guild.id)}.json', 'w') as f:
        json.dump(give, f, sort_keys=True, indent=4, default=str)


@client.event
async def on_message(message):
    await client.process_commands(message)

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.channel.send(content="YInsufficient permissions to use that.", delete_after=10)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.channel.send(content="Add missing parameters and try again.", delete_after=10)
    else:
        print(error)
    pass


@client.command(brief="Starts a giveaway.")
@commands.has_permissions(manage_messages=True)
async def giveaway(ctx, duration: float, winners: int, *, prize="no prize"):
    author = ctx.message.author
    await ctx.message.delete()

    if winners < 1:
        await ctx.send('`winners` has to be at least 1')
        return
    if duration <= 0:
        await ctx.send('`duration` has to be more than 0')
        return

    rolelist = '\n'.join(
        f"{ctx.message.guild.get_role(int(r)).mention} ─ {config['roles'][r]} entries" for r in config['roles'])

    desc = f"""React with :watermelon: to get your entries!
Author: {author.mention}

**{winners}** winners
Duration: **{duration} hours**

Prize: **{prize}**

─────
These roles increase your odds of winning:
{rolelist}
    """

    aika = (datetime.datetime.now() + datetime.timedelta(hours=duration))

    embed = discord.Embed(
        title=f"🎁  Giveaway ─ {prize}", description=desc, color=discord.Colour.gold())
    embed.set_footer(
        text=f"React with 🍉 to get your entries! | Ends at {aika.date()} {aika.strftime('%H:%M')}")

    msg = await ctx.send(embed=embed)
    await msg.add_reaction('\N{WATERMELON}')

    try:
        with open(f'data/{str(ctx.message.guild.id)}.json', 'r') as f:
            give = json.load(f)
    except FileNotFoundError:
        with open(f'data/{str(ctx.message.guild.id)}.json', 'a+') as f:
            f.write("{}")
        with open(f'data/{str(ctx.message.guild.id)}.json', 'r') as f:
            give = json.load(f)

    give[str(msg.id)] = {}
    give[str(msg.id)]['start'] = datetime.datetime.now()
    give[str(msg.id)]['end'] = datetime.datetime.now() + \
        datetime.timedelta(hours=duration)
    give[str(msg.id)]['duration'] = duration
    give[str(msg.id)]['ended'] = False
    give[str(msg.id)]['reactions'] = {}
    give[str(msg.id)]['winners'] = []
    give[str(msg.id)]['prize'] = prize

    with open(f'data/{str(ctx.message.guild.id)}.json', 'w') as f:
        json.dump(give, f, sort_keys=True, indent=4, default=str)

    await asyncio.sleep(duration * 60 * 60)
    if give[str(msg.id)]['ended'] == False:
        await calculate_winners(ctx, msg, duration, 0, winners, prize)


async def calculate_winners(ctx, msg, duration, extra, winners, prize):
    with open(f'data/{str(ctx.message.guild.id)}.json', 'r') as f:
        give = json.load(f)

    if len(give[str(msg.id)]['reactions']) < winners:
        await ctx.send('Not enough participants, extending by 1 hour.')
        await asyncio.sleep(60 * 60)
        if give[str(msg.id)]['ended'] == False:
            await calculate_winners(ctx, msg, duration, 1, winners, prize)
        return

    # randomize winner(s)
    p = []
    a = []
    for key, value in give[str(msg.id)]['reactions'].items():
        p.append(value)
        a.append(key)

    norm = [float(i)/sum(p) for i in p]
    print(norm)

    win = np.random.choice(a=a, size=winners, replace=False, p=norm)
    w = ''
    for user in win:
        fetch = client.get_user(int(user))
        give[str(msg.id)]['winners'].append(int(user))
        print(fetch.display_name, 'won', prize)
        w += fetch.mention + '\n'
        e = discord.Embed(title=f"🎁    You have won a giveaway in `{ctx.message.guild.name}`!    🎁", description=f"""The moderators will contact you soon. *Remember to respond to the mods or you will lose the prize.*\n\nYou won: ***{prize}***""", color=discord.Colour.gold())
        await fetch.send(embed=e)

    aika = (datetime.datetime.now() + datetime.timedelta(hours=duration+extra))

    embed = discord.Embed(title=f"🎁  Giveaway ─ {prize} (ended)", description=f"""**The giveaway has ended!**

**{winners}** winners
Duration: **{duration} hours**
Ended at {aika.date()} {aika.strftime('%H:%M')}

Winner(s): {w}

The moderators will contact the winners shortly. *If you don't respond in 24 hours, you will lose the prize.*""", color=discord.Colour.dark_gold())

    embed.set_footer(text=f"Author: {ctx.message.author.display_name}")

    await msg.edit(embed=embed)

    give[str(msg.id)]['ended'] = True
    with open(f'data/{str(ctx.message.guild.id)}.json', 'w') as f:
        json.dump(give, f, sort_keys=True, indent=4, default=str)


@client.command()
@commands.has_permissions(manage_messages=True)
async def reroll(ctx, msg_id, winners: int):
    try:
        with open(f'data/{str(ctx.message.guild.id)}.json', 'r') as f:
            give = json.load(f)
    except FileNotFoundError:
        await ctx.send("Giveaway does not exist.")
        return

    p = []
    a = []

    for key, value in give[str(msg_id)]['reactions'].items():
        p.append(value)
        a.append(key)

    norm = [float(i)/sum(p) for i in p]
    print(norm)

    win = np.random.choice(a=a, size=winners, replace=False, p=norm)

    w = "New winners:\n"
    for user in win:
        fetch = await client.fetch_user(int(user))
        give[str(msg_id)]['winners'].append(int(user))
        print(fetch.display_name, 'won', give[str(msg_id)]['prize'])
        w += fetch.mention + '\n'
        e = discord.Embed(title=f"🎁    You have won a giveaway in `{ctx.message.guild.name}`!    🎁", description=f"""The moderators will contact you soon. *Remember to respond to the mods or you will lose the prize.*\n\nYou won: ***{give[str(msg_id)]['prize']}***""", color=discord.Colour.gold())
        await fetch.send(embed=e)

    await ctx.send(w)

@client.command()
@commands.has_permissions(manage_messages=True)
async def cancel (ctx, msg_id):
    try:
        with open(f'data/{str(ctx.message.guild.id)}.json', 'r') as f:
            give = json.load(f)
    except FileNotFoundError:
        await ctx.send("Giveaway does not exist.")
        return
    
    give[str(msg_id)]['ended'] = True

    with open(f'data/{str(ctx.message.guild.id)}.json', 'w') as f:
        json.dump(give, f, sort_keys=True, indent=4, default=str)

    await ctx.send("Giveaway cancelled.")

client.run(config['token'])
