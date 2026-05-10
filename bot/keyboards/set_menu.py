from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeAllPrivateChats

from bot.lexicon.menu import DEFAULT_COMMANDS, ADMIN_COMMANDS


async def set_default_menu(bot: Bot):
    commands = [
        BotCommand(command=cmd, description=desc)
        for cmd, desc in DEFAULT_COMMANDS.items()
    ]
    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeAllPrivateChats()
    )

async def set_user_menu(bot: Bot, user_id: int, is_admin: bool):
    if is_admin:
        cmds = ADMIN_COMMANDS
    else:
        cmds = DEFAULT_COMMANDS

    commands = [
        BotCommand(command=cmd, description=desc)
        for cmd, desc in cmds.items()
    ]
    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeChat(chat_id=user_id)
    )