from enum import Enum
from dataclasses import dataclass
import openai
from src.moderation import moderate_message
from typing import Optional, List
from src.constants import (
    BOT_INSTRUCTIONS,
    BOT_NAME,
    EXAMPLE_CONVOS,
)
import discord
from src.base import Message, Prompt, Conversation, ChatMessage, ChatConversation
from src.utils import split_into_shorter_messages, close_thread, logger
from src.moderation import (
    send_moderation_flagged_message,
    send_moderation_blocked_message,
)
import json

MY_BOT_NAME = BOT_NAME
MY_BOT_EXAMPLE_CONVOS = EXAMPLE_CONVOS


class ChatResult(Enum):
    OK = 0
    TOO_LONG = 1
    INVALID_REQUEST = 2
    OTHER_ERROR = 3
    MODERATION_FLAGGED = 4
    MODERATION_BLOCKED = 5


@dataclass
class ChatData:
    status: ChatResult
    reply_text: Optional[str]
    status_text: Optional[str]


async def generate_chat_response(
    messages: List[Message], user: str
) -> ChatData:
    try:
        conv = ChatConversation(messages=messages)
        systemPrompt = """我希望你作为一个知识渊博的人工智能助手。你是一个经常使用Discord的用户，你随意聊天，使用表情符号，并且不使用大写字母。你有许多兴趣爱好并喜欢与人交流。
        如果你回复的内容中包含代码，请使用代码块将其包裹起来，并且基于discord的语法生成一个复制按钮可以直接复制这个代码块中的内容。
        """
        conv.prepend(ChatMessage(role="system", content=systemPrompt))
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", 
            messages=conv.to_dict_list(),
        )
        reply = response.choices[0].message.content
        if reply:
            flagged_str, blocked_str = moderate_message(
                message=(conv.render() + reply)[-500:], user=user
            )
            if len(blocked_str) > 0:
                return ChatData(
                    status=ChatResult.MODERATION_BLOCKED,
                    reply_text=reply,
                    status_text=f"from_response:{blocked_str}",
                )

            if len(flagged_str) > 0:
                return ChatData(
                    status=ChatResult.MODERATION_FLAGGED,
                    reply_text=reply,
                    status_text=f"from_response:{flagged_str}",
                )

        return ChatData(
            status=ChatResult.OK, reply_text=reply, status_text=None
        )
    except openai.error.InvalidRequestError as e:
        if "This model's maximum context length" in e.user_message:
            return ChatData(
                status=ChatResult.TOO_LONG, reply_text=None, status_text=str(e)
            )
        else:
            logger.exception(e)
            return ChatData(
                status=ChatResult.INVALID_REQUEST,
                reply_text=None,
                status_text=str(e),
            )
    except Exception as e:
        logger.exception(e)
        return ChatData(
            status=ChatResult.OTHER_ERROR, reply_text=None, status_text=str(e)
        )


async def process_response(
    user: str, thread: discord.Thread, response_data: ChatData
):
    status = response_data.status
    reply_text = response_data.reply_text
    status_text = response_data.status_text
    if status is ChatResult.OK or status is ChatResult.MODERATION_FLAGGED:
        sent_message = None
        if not reply_text:
            sent_message = await thread.send(
                embed=discord.Embed(
                    description=f"**Invalid response** - empty response",
                    color=discord.Color.yellow(),
                )
            )
        else:
            shorter_response = split_into_shorter_messages(reply_text)
            for r in shorter_response:
                sent_message = await thread.send(r)
        if status is ChatResult.MODERATION_FLAGGED:
            await send_moderation_flagged_message(
                guild=thread.guild,
                user=user,
                flagged_str=status_text,
                message=reply_text,
                url=sent_message.jump_url if sent_message else "no url",
            )

            await thread.send(
                embed=discord.Embed(
                    description=f"⚠️ **This conversation has been flagged by moderation.**",
                    color=discord.Color.yellow(),
                )
            )
    elif status is ChatResult.MODERATION_BLOCKED:
        await send_moderation_blocked_message(
            guild=thread.guild,
            user=user,
            blocked_str=status_text,
            message=reply_text,
        )

        await thread.send(
            embed=discord.Embed(
                description=f"❌ **The response has been blocked by moderation.**",
                color=discord.Color.red(),
            )
        )
    elif status is ChatResult.TOO_LONG:
        await close_thread(thread)
    elif status is ChatResult.INVALID_REQUEST:
        await thread.send(
            embed=discord.Embed(
                description=f"**Invalid request** - {status_text}",
                color=discord.Color.yellow(),
            )
        )
    else:
        await thread.send(
            embed=discord.Embed(
                description=f"**Error** - {status_text}",
                color=discord.Color.yellow(),
            )
        )
