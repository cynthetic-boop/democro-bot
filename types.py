import shelve
from dataclasses import dataclass
from typing import Optional, Dict

from util.errors import *


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
