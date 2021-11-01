import os
import logging
import discord
import asyncio
import re
import shelve

from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('DEV')
joke_pattern = os.getenv('JOKE')
bot = commands.Bot(command_prefix='$')
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
        await state.store(ctx.guild.id)
        await ctx.send(f"Thread channel updated to <#{bot.get_channel(discuss_channel)}>.  Vote channel updated to <#{bot.get_channel(vote_channel)}>")

    @commands.command()
    @commands.is_owner()
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
    async def statedebug(self, ctx):
        state = self.get_state(ctx.guild)
        print("Sending owner debug info...")
        owner = await bot.fetch_user(bot.owner_id)
        await owner.create_dm()
        await owner.dm_channel.send(f"""Debug info for **{ctx.guild.name} [{ctx.guild.id}]**
```Cached Info:
{state}\n
Stored DB info:
Discussion Channel:{await self._shelf_read(f"{ctx.guild.id}-d")}
Vote Channel:{await self._shelf_read(f"{ctx.guild.id}-v")}```""")

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


class GuildState:
    """Class that manages the state in each guild the bot is connected to."""
    def __init__(self):
        self._discuss_ch = None
        self._vote_ch = None
        self._current_votes = {} #stores current votes

    def __repr__(self):
        return f"Discussion channel: {self.discuss_ch}\nVote Channel: {self.vote_ch}"

    @property
    def discuss_ch(self):
        return self._discuss_ch

    @discuss_ch.setter
    def discuss_ch(self, channel_id: int):
        self._discuss_ch = bot.get_channel(channel_id)

    @property
    def vote_ch(self):
        return self._vote_ch

    @vote_ch.setter
    def vote_ch(self, channel_id: int):
        self._vote_ch = bot.get_channel(channel_id)

    async def store(self, id):
        with shelve.open('./db/id_shelf') as shelf:
            shelf[f"{id}-d"] = self.discuss_ch.id
            shelf[f"{id}-v"] = self.vote_ch.id

    async def update_cache(self, id):
        with shelve.open('./db/id_shelf') as shelf:
            try:
                self.discuss_ch = shelf[f"{id}-d"]
                self.vote_ch = shelf[f"{id}-v"]
            except KeyError:
                raise DBKeyNotFoundError


class VoteItem:
    """A vote/poll that currently exists in a server, with all vote information stored."""
    def __init__(self):
        self.yes_votes = 0
        self.no_votes = 0
        self.abstain_votes = 0
        self.question_votes = 0
        self.embed = None
        self.message = None

    @property
    def yes_votes(self):
        return self.yes_votes

    @yes_votes.setter
    def yes_votes(self, votes: int):
        self.yes_votes = votes

    @property
    def no_votes(self):
        return self.no_votes

    @no_votes.setter
    def discuss_ch(self, votes: int):
        self.no_votes = votes

    @property
    def abstain_votes(self):
        return self.discuss_ch

    @abstain_votes.setter
    def abstain_votes(self, votes: int):
        self.abstain_votes = votes

    @property
    def question_votes(self):
        return self.question_votes

    @question_votes.setter
    def question_votes(self, votes: int):
        self.question_votes = votes

    @property
    def embed(self):
        return self.question_votes

    @embed.setter
    def embed(self, embed: int):
        self.embed = embed


@bot.event
async def on_ready():
    print(f"CONNECTED!\nBot client: [{bot.user}]\n~~~~~~~~")
    activity = discord.Activity(name='the voting booth.', type=discord.ActivityType.watching)
    await bot.change_presence(activity=activity)



bot.add_cog(Cogs(bot))

bot.run(token)
