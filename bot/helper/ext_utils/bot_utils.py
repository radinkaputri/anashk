from httpx import AsyncClient
from random import choice
from asyncio import (
    create_subprocess_exec,
    create_subprocess_shell,
    run_coroutine_threadsafe,
    sleep,
)
from asyncio.subprocess import PIPE
from pyrogram.types import BotCommand
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps

from bot import bot, user_data, config_dict, bot_loop, LOGGER, OWNER_ID
from bot.helper.ext_utils.help_messages import (
    YT_HELP_DICT,
    MIRROR_HELP_DICT,
    CLONE_HELP_DICT,
)
from bot.helper.ext_utils.telegraph_helper import telegraph
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.bot_commands import BotCommands

THREADPOOL = ThreadPoolExecutor(max_workers=3000)

COMMAND_USAGE = {}


class setInterval:
    def __init__(self, interval, action, *args, **kwargs):
        self.interval = interval
        self.action = action
        self.task = bot_loop.create_task(self._set_interval(*args, **kwargs))

    async def _set_interval(self, *args, **kwargs):
        while True:
            await sleep(self.interval)
            await self.action(*args, **kwargs)

    def cancel(self):
        self.task.cancel()

async def delete_links(message):
    if message.from_user.id == OWNER_ID and message.chat.type == message.chat.type.PRIVATE:
        return

    if config_dict['DELETE_LINKS']:
        try:
            if reply_to := message.reply_to_message:
                await sleep(2)
                await reply_to.delete()
                await message.delete()
            else:
                await sleep(2)
                await message.delete()
        except Exception as e:
            LOGGER.error(str(e))

def create_help_buttons():
    buttons = ButtonMaker()
    for name in list(MIRROR_HELP_DICT.keys())[1:]:
        buttons.ibutton(name, f"help mirror {name}")
    buttons.ibutton("Close", "help close")
    COMMAND_USAGE["mirror"] = [MIRROR_HELP_DICT["main"], buttons.build_menu(3)]
    buttons.reset()
    for name in list(YT_HELP_DICT.keys())[1:]:
        buttons.ibutton(name, f"help yt {name}")
    buttons.ibutton("Close", "help close")
    COMMAND_USAGE["yt"] = [YT_HELP_DICT["main"], buttons.build_menu(3)]
    buttons.reset()
    for name in list(CLONE_HELP_DICT.keys())[1:]:
        buttons.ibutton(name, f"help clone {name}")
    buttons.ibutton("Close", "help close")
    COMMAND_USAGE["clone"] = [CLONE_HELP_DICT["main"], buttons.build_menu(3)]


async def set_commands(bot):
    if config_dict['SET_COMMANDS']:
        await bot.set_bot_commands(commands=[
            BotCommand(BotCommands.StartCommand, "Start the bot"),
            BotCommand(BotCommands.MirrorCommand[0], "Start mirroring (or " + BotCommands.MirrorCommand[1] + ")"),
            BotCommand(BotCommands.LeechCommand[0], "Start leeching (or " + BotCommands.LeechCommand[1] + ")"),
            BotCommand(BotCommands.QbMirrorCommand[0], "Start torrent mirroring (or " + BotCommands.QbMirrorCommand[1] + ")"),
            BotCommand(BotCommands.QbLeechCommand[0], "Start torrent leeching (or " + BotCommands.QbLeechCommand[1] + ")"),
            BotCommand(BotCommands.YtdlCommand[0], "Mirror with ytdlp (or " + BotCommands.YtdlCommand[1] + ")"),
            BotCommand(BotCommands.YtdlLeechCommand[0], "Leech with ytdlp (or " + BotCommands.YtdlLeechCommand[1] + ")"),
            BotCommand(BotCommands.ListCommand, "Search files in mirror Drive"),
            BotCommand(BotCommands.CloneCommand, "Cloning files to mirror Drive"),
            BotCommand(BotCommands.SearchCommand, "Search something from torrents site"),
            BotCommand(BotCommands.CancelTaskCommand, "Cancel one task"),
            BotCommand(BotCommands.CancelAllCommand, "Cancel all tasks"),
            BotCommand(BotCommands.PingCommand, "Ping the bot"),
            BotCommand(BotCommands.HelpCommand, "Get help"),
            BotCommand(BotCommands.UserSetCommand[0], "Open user setting menu (or " + BotCommands.UserSetCommand[1] + ")"),
            BotCommand(BotCommands.RestartCommand, "Restart the bot (only owner)"),
        ])


def bt_selection_buttons(id_):
    gid = id_[:12] if len(id_) > 20 else id_
    pincode = "".join([n for n in id_ if n.isdigit()][:4])
    buttons = ButtonMaker()
    BASE_URL = config_dict["BASE_URL"]
    if config_dict["WEB_PINCODE"]:
        buttons.ubutton("Select Files", f"{BASE_URL}/app/files/{id_}")
        buttons.ibutton("Pincode", f"btsel pin {gid} {pincode}")
    else:
        buttons.ubutton(
            "Select Files", f"{BASE_URL}/app/files/{id_}?pin_code={pincode}"
        )
    buttons.ibutton("Done Selecting", f"btsel done {gid} {id_}")
    buttons.ibutton("Cancel", f"btsel cancel {gid}")
    return buttons.build_menu(2)


async def get_telegraph_list(telegraph_content):
    path = [
        (
            await telegraph.create_page(
                title="Drive Search", content=content
            )
        )["path"]
        for content in telegraph_content
    ]
    if len(path) > 1:
        await telegraph.edit_telegraph(path, telegraph_content)
    buttons = ButtonMaker()
    buttons.ubutton("🔎 VIEW", f"https://telegra.ph/{path[0]}")
    return buttons.build_menu(1)


def arg_parser(items, arg_base):
    if not items:
        return
    bool_arg_set = {
        "-b",
        "-e",
        "-z",
        "-s",
        "-j",
        "-d",
        "-sv",
        "-ss",
        "-f",
        "-fd",
        "-fu",
        "-sync",
        "-ml",
        "-doc",
        "-med"
    }
    t = len(items)
    i = 0
    arg_start = -1

    while i + 1 <= t:
        part = items[i]
        if part in arg_base:
            if arg_start == -1:
                arg_start = i
            if (
                i + 1 == t
                and part in bool_arg_set
                or part in ["-s", "-j", "-f", "-fd", "-fu", "-sync", "-ml", "-doc", "-med"]
            ):
                arg_base[part] = True
            else:
                sub_list = []
                for j in range(i + 1, t):
                    item = items[j]
                    if item in arg_base:
                        if part in bool_arg_set and not sub_list:
                            arg_base[part] = True
                        break
                    sub_list.append(item)
                    i += 1
                if sub_list:
                    arg_base[part] = " ".join(sub_list)
        i += 1
    if "link" in arg_base and items[0] not in arg_base:
        link = []
        if arg_start == -1:
            link.extend(iter(items))
        else:
            link.extend(items[r] for r in range(arg_start))
        if link:
            arg_base["link"] = " ".join(link)


def getSizeBytes(size):
    size = size.lower()
    if size.endswith("mb"):
        size = size.split("mb")[0]
        size = int(float(size) * 1048576)
    elif size.endswith("gb"):
        size = size.split("gb")[0]
        size = int(float(size) * 1073741824)
    else:
        size = 0
    return size


async def get_content_type(url):
    try:
        async with AsyncClient() as client:
            response = await client.get(url, allow_redirects=True, verify=False)
            return response.headers.get("Content-Type")
    except:
        return None


def update_user_ldata(id_, key, value):
    user_data.setdefault(id_, {})
    user_data[id_][key] = value


async def retry_function(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except:
        return await retry_function(func, *args, **kwargs)


async def cmd_exec(cmd, shell=False):
    if shell:
        proc = await create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE)
    else:
        proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    try:
        stdout = stdout.decode().strip()
    except:
        stdout = "Unable to decode the response!"
    try:
        stderr = stderr.decode().strip()
    except:
        stderr = "Unable to decode the error!"
    return stdout, stderr, proc.returncode


def new_task(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return bot_loop.create_task(func(*args, **kwargs))

    return wrapper


async def sync_to_async(func, *args, wait=True, **kwargs):
    pfunc = partial(func, *args, **kwargs)
    future = bot_loop.run_in_executor(THREADPOOL, pfunc)
    return await future if wait else future


def async_to_sync(func, *args, wait=True, **kwargs):
    future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
    return future.result() if wait else future


def new_thread(func):
    @wraps(func)
    def wrapper(*args, wait=False, **kwargs):
        future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
        return future.result() if wait else future

    return wrapper
