from dataclasses import dataclass
from typing import Optional, List
import json

SEPARATOR_TOKEN = "<|endoftext|>"


@dataclass(frozen=True)
class Message:
    user: str
    text: Optional[str] = None

    def render(self):
        result = self.user + ":"
        if self.text is not None:
            result += " " + self.text
        return result

@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
        }

    def render(self):
        result = self.role + ":"
        if self.content is not None:
            result += " " + self.content
        return result

@dataclass
class Conversation:
    messages: List[Message]

    def prepend(self, message: Message):
        self.messages.insert(0, message)
        return self

    def render(self):
        return f"\n{SEPARATOR_TOKEN}".join(
            [message.render() for message in self.messages]
        )

@dataclass
class ChatConversation:
    messages: List[ChatMessage]

    def __init__(self, messages: List[Message]) -> None:
        self.messages = [self.message_to_chat_message(message) for message in messages]

    def message_to_chat_message(self, message: Message):
        role = message.user
        if message.user == "小鱼儿":
            role = "assistant"
        elif message.user == "system":
            role = "system"
        else:
            role = "user"

        return ChatMessage(role=role, content=message.text)

    def prepend(self, message: ChatMessage):
        self.messages.insert(0, message)
        return self

    def to_dict_list(self):
        return [message.to_dict() for message in self.messages]

    def render(self):
         return f"\n{SEPARATOR_TOKEN}".join(
            [message.render() for message in self.messages]
    )

@dataclass(frozen=True)
class Config:
    name: str
    instructions: str
    example_conversations: List[Conversation]


@dataclass(frozen=True)
class Prompt:
    header: Message
    examples: List[Conversation]
    convo: Conversation

    def render(self):
        return f"\n{SEPARATOR_TOKEN}".join(
            [self.header.render()]
            + [Message("System", "Example conversations:").render()]
            + [conversation.render() for conversation in self.examples]
            + [Message("System", "Current conversation:").render()]
            + [self.convo.render()],
        )
