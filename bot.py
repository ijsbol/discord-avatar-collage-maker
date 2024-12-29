import asyncio
from io import BytesIO
import math
from os import getenv

from discord import File, Intents, Message, NotFound
from discord.ext.commands import Bot, Context, when_mentioned
from dotenv import load_dotenv
from PIL import Image
from PIL.Image import Image as ImageType


load_dotenv()


AVATAR_SIZE: int = int(str(getenv("AVATAR_DISPLAY_SIZE")))
DISCORD_BOT_TOKEN: str = str(getenv("DISCORD_BOT_TOKEN"))


intents = Intents()
intents.members = True
intents.guild_messages = True


bot = Bot(
    command_prefix=when_mentioned,
    intents=intents,
)


def create_progress_bar(progress: int, total: int, resolution: int) -> str:
    percent_progress = (progress / total)
    ticks = int(resolution * percent_progress)
    return ('#' * ticks) + '-' * (resolution-ticks)


async def dispatch_update_message(message: Message, image: ImageType, name: str, progress: int, total: int) -> None:
    image.save(name)
    await message.edit(
        content=f":diamond_shape_with_a_dot_inside: | Progress: (~{progress}/{total}) **`{round(progress/total*100)}%`**.",
        attachments=[File(name)],
    )


@bot.command('create')
async def create(ctx: Context[Bot]) -> None:
    update_message = await ctx.reply(":diamond_shape_with_a_dot_inside: | Fetching all server members.")

    members = await ctx.guild.chunk(cache=False)
    avatars_per_row = int(round(math.sqrt(len(members))))
    square_size = avatars_per_row * AVATAR_SIZE
    avatar_collation = Image.new('RGBA', (square_size, square_size))
    x, y = 0 , 0

    await update_message.edit(content=f":diamond_shape_with_a_dot_inside: | `{len(members)}` members fetched, image will be (`{square_size}x{square_size}`).")

    file_name = f"{ctx.guild.id}-avatars.png"

    for num, member in enumerate(members):
        progress_bar = create_progress_bar(num, len(members), 100)
        print(f"{member.id}: (x: {x}, y: {y}) (~{num}/{len(members)})\t({round(num/len(members)*100)}%) [{progress_bar}]{' '*5}", end="\r")
        try:
            avatar_bytes = await member.display_avatar.read()
        except NotFound:
            avatar_bytes = await member.default_avatar.read()
        avatar_bytes_io = BytesIO(avatar_bytes)
        avatar_bytes_io.seek(0)
        member_avatar = Image.open(avatar_bytes_io).resize((
            AVATAR_SIZE, AVATAR_SIZE
        ))
        avatar_collation.paste(member_avatar, (x * AVATAR_SIZE, y * AVATAR_SIZE))

        if num % (len(members) // 20) == 0:
            task = asyncio.create_task(
                dispatch_update_message(update_message, avatar_collation, file_name, num, len(members))
            )
            asyncio.gather(task)

        if x < avatars_per_row - 1:
            x += 1
        else:
            x = 0
            y += 1

    await update_message.edit(content=f":diamond_shape_with_a_dot_inside: | Saving image.")
    await update_message.edit(
        content=f":diamond_shape_with_a_dot_inside: | Image saved as `{file_name}`.",
        attachments=[File(file_name)],
    )


bot.run(DISCORD_BOT_TOKEN)
