import os
import logging
import discord
import asyncio
import re
import shelve

from discord.ext import commands
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional, Dict

load_dotenv()
token = os.getenv('DEV')
joke_pattern = os.getenv('JOKE')
owner = os.getenv('OWNER')
bot = commands.Bot(command_prefix='d!', owner_id=owner)
logging.basicConfig(level=logging.WARN)
try:
    os.mkdir('./db/')
except FileExistsError:
    pass
d = shelve.open('./db/id_shelf')
d.close()


class ChannelNotFoundError(Exception):
    pass

class DBKeyNotFoundError(Exception):
    pass


class Cogs(commands.Cog):
    """Cog for bot's Commands"""

    def __init__(self, bot):
        self.bot = bot
        self._last_member = None
        self.states = {}

    def get_state(self, guild):
        """Gets the state for guild, and creates a new instance if it doesn't exist."""
        for guild.id in self.states:
            return self.states[guild.id]
        else:
            self.states[guild.id] = GuildState()
            return self.states[guild.id]

    async def _shelve(self, key, id):
        with shelve.open('./db/id_shelf') as shelf:
            shelf[key] = id

    async def _shelf_read(self, key):
        with shelve.open('./db/id_shelf') as shelf:
            return shelf[key]

    @commands.command()
    @commands.guild_only()
    async def ping(self, ctx):
        await ctx.send("pong")

    @commands.command()
    @commands.guild_only()
    async def startvote(self, ctx, *, vote_name):
        state = self.get_state(ctx.guild)
        if state.discuss_ch is None or state.vote_ch is None:
            try:
                await state.update_cache(ctx.guild.id)
            except DBKeyNotFoundError:
                return await ctx.send("You first need to establish which channels votes are held in with the 'setchannels' command")
        linked_thread = await state.discuss_ch.create_thread(name=f"{vote_name}", type=discord.ChannelType.public_thread, reason=f"Discussion thread for topic: {vote_name}")
        await linked_thread.join()
        await linked_thread.add_user(ctx.message.author)
        linked_message = await linked_thread.send(content="Discuss...")
        embed = discord.Embed(title=f"Vote on \"{vote_name}\"", description=f"✅ for yes\n❌ for no\n⬛ for no opinion\n❔ to ask vote author to discuss more")
        embed.set_author(name=f"Vote started by: {ctx.message.author.name}")
        embed.add_field(name="Link to thread", value=f"[Click Here]({linked_message.jump_url})")
        embed.set_footer(text="Remember not to send messages in this channel.")
        vote_message = await state.vote_ch.send(embed=embed)
        await vote_message.add_reaction(emoji='✅')
        await vote_message.add_reaction(emoji='❌')
        await vote_message.add_reaction(emoji='⬛')
        await vote_message.add_reaction(emoji='❔')
        thread_embed = discord.Embed(title=f"Thread topic: {vote_name}", description=f"[Vote here]({vote_message.jump_url})")
        await linked_thread.send(embed=thread_embed)
        await ctx.message.delete(delay=1.0)

    @commands.command()
    @commands.guild_only()
    async def startsimplevote(self, ctx, *, vote_name):
        state = self.get_state(ctx.guild)
        if state.vote_ch is None:
            try:
                await state.update_cache(ctx.guild.id)
            except DBKeyNotFoundError:
                return await ctx.send("You first need to establish which channels votes are held in with the 'setchannels' command.")
        embed = discord.Embed(title=f"Vote on \"{vote_name}\"", description=f"✅ for yes\n❌ for no\n⬛ for no opinion\n❔ to ask vote author to discuss more")
        embed.set_author(name=f"Vote started by: {ctx.message.author.name}")
        embed.set_footer(text="Remember not to send messages in this channel.")
        vote_message = await state.vote_ch.send(embed=embed)
        await vote_message.add_reaction(emoji='✅')
        await vote_message.add_reaction(emoji='❌')
        await vote_message.add_reaction(emoji='⬛')
        await vote_message.add_reaction(emoji='❔')
        await linked_thread.send(embed=thread_embed)
        await ctx.message.delete(delay=1.0)

    @commands.command()
    @commands.guild_only()
    @commands.has_role("vote-operator")
    async def setchannels(self, ctx, discuss_channel, vote_channel):
        state = self.get_state(ctx.guild)
        standard = re.compile('<#[0-9]{16,20}>')
        joke = re.compile(joke_pattern)
        if joke.match(str(discuss_channel) + str(vote_channel)):
            return await ctx.send("Haha, very funny.  Those are some cute channel IDs you have there.")
        if standard.match(discuss_channel):
            discuss_channel = int(re.sub('[<#>]', '', discuss_channel))
            if standard.match(vote_channel):
                vote_channel = int(re.sub('[<#>]', '', vote_channel))
                try:
                    state.discuss_ch = discuss_channel
                    state.vote_ch = vote_channel
                except:
                    raise ChannelNotFoundError
            else:
                await ctx.send(f"Please provide both channels in the same format.")
        else:
            discuss_channel = int(discuss_channel)
            vote_channel = int(vote_channel)
            try:
                state.discuss_ch = discuss_channel
                state.vote_ch = vote_channel
            except:
                raise ChannelNotFoundError
        await state.store(ctx.guild)
        await ctx.send(f"Thread channel updated to <#{bot.get_channel(discuss_channel)}>.  Vote channel updated to <#{bot.get_channel(vote_channel)}>")


    @commands.command()
    async def open_dm(self, ctx):
        await ctx.message.author.create_dm()
        await ctx.message.author.dm_channel.send("Opened dm")
        print(f"Opened DM with user {ctx.message.author}")
        await self.send_owner(f"Opened DM with user {ctx.message.author}")

    @commands.command()
    @commands.is_owner()
    @commands.dm_only()
    async def status(self, ctx, type, *, status):
        if "play" in type:
            type = discord.ActivityType.playing
        elif "streaming" in type:
            type = discord.ActivityType.streaming
        elif "listening" in type:
            type = discord.ActivityType.listening
        elif "watching" in type:
            type = discord.ActivityType.watching
        elif "competing" in type:
            type = discord.ActivityType.competing
        elif "custom" in type:
            type = discord.ActivityType.custom
        else:
            return
        activity = discord.Activity(name=str(status), type=type)
        await bot.change_presence(activity=activity)

    @commands.command()
    @commands.is_owner()
    @commands.dm_only()
    async def listIDs(self, ctx, number: int):
        msg = []
        PAGE_SIZE = 10
        start = number * PAGE_SIZE
        end = start + PAGE_SIZE
        for key in list(self.states)[start:end]:
            msg.append(f"{key}")
        await self.send_owner("\n".join(msg))


    @commands.command()
    @commands.is_owner()
    @commands.dm_only()
    async def statedebug(self, ctx, id):
        guild = bot.get_guild(id)
        state = self.get_state(guild)
        print("Sending owner debug info...")
        await self.send_owner(f"""Debug info for **{guild.name} [{guild.id}]**
```Cached Info:
{state}\n
Stored DB info:
Discussion Channel:{await self._shelf_read(f"{ctx.guild.id}-d")}
Vote Channel:{await self._shelf_read(f"{ctx.guild.id}-v")}```""")

    @commands.command()
    @commands.is_owner()
    @commands.dm_only()
    async def shudown(self, ctx, confirm):
        await ctx.message.delete()
        if confirm == str(os.getenv('CODE')):
            exit()


    async def send_owner(self, message: str):
        owner = await bot.fetch_user(bot.owner_id)
        await owner.create_dm()
        await owner.dm_channel.send(message)

    @setchannels.error
    async def on_command_error(self, ctx, error):
        print(f"Type {type(error)} with message {error}")
        if isinstance(error, discord.ext.commands.errors.MissingRole):
            return await ctx.send(f"{error}")
        elif isinstance (error, discord.ext.commands.errors.MissingRequiredArgument):
            return await ctx.send("You must provide two channels using #'s or channel IDs as numbers in the order:\n1st: thread channel (the channel where discussion threads get sent),\n2nd: voting channel (the channel where only votes take place).")
        elif isinstance(error.original, ChannelNotFoundError):
            return await ctx.send("One or more of the channel IDs provided were invalid")
        elif isinstance(error.original, ValueError):
            return await ctx.send("One or more of the channel IDs provided were invalid")
        elif isinstance(error.original, AttributeError):
            return await ctx.send("One or more of the channel IDs provided were invalid")
        return await ctx.send("You must provide two channels using #'s or channel IDs as numbers in the order:\n1st: thread channel (the channel where discussion threads get sent),\n2nd: voting channel (the channel where only votes take place).")


@dataclass
class GuildState:
    """Class that manages the state in each guild the bot is connected to."""
    id: int
    discuss_ch: Optional[str]
    vote_ch: Optional[str]
    current_votes: Dict[str, int]

    def __repr__(self):
        return f"Discussion channel: {self.discuss_ch}\nVote Channel: {self.vote_ch}"

    async def store(self, guild):
        with shelve.open('./db/id_shelf') as shelf:
            shelf[f"{guild.id}-d"] = self.discuss_ch.id
            shelf[f"{guild.id}-v"] = self.vote_ch.id
        print(f"Stored persistent data for server{guild.name}[ID: {guild.id}]")

    async def update_cache(self, id):
        with shelve.open('./db/id_shelf') as shelf:
            try:
                self.discuss_ch = shelf[f"{id}-d"]
                self.vote_ch = shelf[f"{id}-v"]
            except KeyError:
                raise DBKeyNotFoundError

@dataclass
class VoteItem:
    """A vote/poll that currently exists in a server, with all vote information stored."""
    yes_votes: int
    no_votes: int
    abstain_votes: int
    question_votes: int
    embed: discord.Embed
    message: discord.Message


@bot.event
async def on_ready():
    print(f"CONNECTED!\nBot client: [{bot.user}]\n~~~~~~~~")
    activity = discord.Activity(name='the voting booth.', type=discord.ActivityType.watching)
    await bot.change_presence(activity=activity)


bot.add_cog(Cogs(bot))

bot.run(token)
