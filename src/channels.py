import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    PUBLIC = "public"
    PRIVATE = "private"


@dataclass
class Message:
    sender: str
    content: str
    channel_id: str


@dataclass
class Channel:
    id: str
    name: str
    type: ChannelType
    members: Optional[List[str]] = None  # None means all agents (public)

    def can_read(self, agent_id: str) -> bool:
        if self.type == ChannelType.PUBLIC:
            return True
        return self.members is not None and agent_id in self.members

    def can_write(self, agent_id: str) -> bool:
        return self.can_read(agent_id)


class ChannelManager:
    """
    Manages public and private communication channels between agents
    within a single simulation project.

    Uses an in-memory message log per channel. In Release 2 this will
    be replaced by Redis Pub/Sub to support async workers and WebSocket
    broadcast to the frontend.
    """

    def __init__(self):
        self._channels: Dict[str, Channel] = {}
        # channel_id -> list of Message
        self._log: Dict[str, List[Message]] = {}

    def register_channel(self, channel_def: dict) -> None:
        ch_type = ChannelType(channel_def.get("type", "public"))
        members = channel_def.get("members", None)
        channel = Channel(
            id=channel_def["id"],
            name=channel_def["name"],
            type=ch_type,
            members=members,
        )
        self._channels[channel.id] = channel
        self._log[channel.id] = []
        logger.info(f"Channel registered: [{channel.type.value}] {channel.id}")

    def post(self, sender_id: str, channel_id: str, content: str) -> bool:
        """Post a message to a channel. Returns False if the agent has no write access."""
        channel = self._channels.get(channel_id)
        if channel is None:
            logger.error(f"Channel '{channel_id}' does not exist.")
            return False
        if not channel.can_write(sender_id):
            logger.warning(f"Agent '{sender_id}' attempted to write to '{channel_id}' without permission.")
            return False

        msg = Message(sender=sender_id, content=content, channel_id=channel_id)
        self._log[channel_id].append(msg)
        logger.debug(f"[{channel_id}] {sender_id}: {content[:80]}")
        return True

    def get_readable_messages(self, agent_id: str, channel_id: str, last_n: int = 10) -> List[Message]:
        """Return the last N messages from a channel readable by the agent."""
        channel = self._channels.get(channel_id)
        if channel is None or not channel.can_read(agent_id):
            return []
        return self._log[channel_id][-last_n:]

    def get_agent_channels(self, agent_id: str) -> List[Channel]:
        """Return all channels an agent belongs to."""
        return [ch for ch in self._channels.values() if ch.can_read(agent_id)]

    def format_context_for_agent(self, agent_id: str, channel_id: str, last_n: int = 5) -> str:
        """
        Returns a formatted string of recent messages usable as context
        prefix in an agent's user message.
        """
        messages = self.get_readable_messages(agent_id, channel_id, last_n)
        if not messages:
            return ""
        lines = [f"[{m.sender}]: {m.content}" for m in messages]
        return "--- Ultimi messaggi nel canale ---\n" + "\n".join(lines) + "\n---\n"
