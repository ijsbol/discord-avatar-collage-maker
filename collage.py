import argparse
import asyncio
import glob
from io import BytesIO
import itertools
from pathlib import Path
import sys
import time
from typing import Any, Callable

import aiohttp
from PIL import Image


type MemberRecord = tuple[int, str, str]


DISCORD_API_URL: str = "https://discord.com/api/v10/"
USER_AGENT: str = "DiscordBot (https://git.uwu.gal/discord-avatar-collage-maker, 2.0.0)"
FETCH_MEMBERS_PER_PAGE: int = 1000
RATELIMIT_JITTER_PERCENT: float = 1.10
DOWNLOAD_SIZE: int = 256
COOLDOWN_UPDATE_TICKS: int = 20
NUMBER_OF_AVATARS_PER_DOWNLOAD_PROCESS: int = 500
MAX_NUMBER_OF_CONCURRENT_DOWNLOAD_PROCESSES: int = 10
AVATAR_SAVE_DIRECTORY: str = "avatars/"


display: Callable[[str], None] = lambda string: print(string + ' ' * 50, end="\r")


def _generate_member_record(member: dict[str, Any]) -> MemberRecord:
    # Server avatar
    avatar_hash = member["avatar"]
    user_id = int(member["user"]["id"])

    # Server avatar not found, user global user avatar.
    if avatar_hash is None:
        avatar_hash = member["user"]["avatar"]

    # Both server avatar and global avatar not found, use default avatar.
    if avatar_hash is None:
        avatar_hash = str(int(user_id % 5))
        avatar_url =  f"https://cdn.discordapp.com/embed/avatars/{avatar_hash}.png"

    else:
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png?format=png&quality=lossless&width={DOWNLOAD_SIZE}&height={DOWNLOAD_SIZE}"
    return (user_id, avatar_url, avatar_hash)


async def handle_cooldown(cooldown: float) -> None:
    # Just gives interactive cooldown visualisations.
    cooldown *= RATELIMIT_JITTER_PERCENT
    cooldown_start_time = time.time()
    cooldown_per_tick = (cooldown / COOLDOWN_UPDATE_TICKS)
    for _ in range(COOLDOWN_UPDATE_TICKS):
        cooldown_delta = time.time() - cooldown_start_time
        display(f"Fetching members (on cooldown for {round(cooldown - cooldown_delta, 2):,}s)")
        await asyncio.sleep(cooldown_per_tick)


async def fetch_members(*, token: str, target_id: int) -> list[MemberRecord]:
    members: list[MemberRecord] = []

    async with aiohttp.ClientSession(
        base_url=DISCORD_API_URL,
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": USER_AGENT,
        },
    ) as session:
        current_after = 0
        while True:
            display(f"Fetching members (fetched {len(members)}).")
            async with session.get(
                url=f"guilds/{target_id}/members",
                params={
                    "limit": FETCH_MEMBERS_PER_PAGE,
                    "after": current_after,
                },
            ) as request:
                # Handle rate limits.
                x_ratelimit_remaining = float(request.headers.get("x-ratelimit-remaining", None) or 0)
                ratelimit_reset_after = float(request.headers.get("x-ratelimit-reset-after", None) or 0)
                if x_ratelimit_remaining == 0:
                    await handle_cooldown(ratelimit_reset_after)
                    continue

                # Handle returned information.
                raw_members = await request.json()

                if len(raw_members) == 0:
                    break

                members.extend([_generate_member_record(member) for member in raw_members])
                current_after = max([member[0] for member in members])

    return members


async def _download_avatar_batch(*, semaphore: asyncio.Semaphore, members: list[MemberRecord], target_id: int, avatar_size: int) -> None:
    async with semaphore:
        async with aiohttp.ClientSession(
            headers={
                "User-Agent": USER_AGENT,
            },
            timeout=aiohttp.ClientTimeout(total=60),
        ) as session:
            for member in members:
                display(f"Downloading {member[0]} - {member[2]}")
                member_id = member[0]
                member_avatar_url = member[1]
                avatar_hash = member[2]
                async with session.get(url=member_avatar_url) as response:
                    try:
                        # lol sometimes the CDN can 404.
                        response.raise_for_status()
                    except aiohttp.ClientResponseError:
                        continue
                    avatar_bytes_io = BytesIO(await response.read())
                    avatar_bytes_io.seek(0)
                    Image.open(avatar_bytes_io)\
                        .save(f"{AVATAR_SAVE_DIRECTORY}{target_id}/{member_id}-{avatar_hash}.png")


async def download_avatars(*, members: list[MemberRecord], target_id: int, avatar_size: int) -> None:
    avatar_batches = list(itertools.batched(members, NUMBER_OF_AVATARS_PER_DOWNLOAD_PROCESS))
    semaphore = asyncio.Semaphore(MAX_NUMBER_OF_CONCURRENT_DOWNLOAD_PROCESSES)
    tasks = [
        _download_avatar_batch(
            semaphore=semaphore,
            members=batched_avatars,
            target_id=target_id,
            avatar_size=avatar_size,
        ) for batched_avatars in avatar_batches
    ]
    await asyncio.gather(*tasks)


def generate_image(*, target_id: int, image_size: tuple[int, int], avatar_size: int, file_name: str) -> None:
    avatar_image_paths = glob.glob(AVATAR_SAVE_DIRECTORY + f"{target_id}/*.png")

    # ... there has to be a better way to do this, right? -kit
    scale = 1
    while True:
        avatars_per_row = int(scale * image_size[0])
        avatars_per_col = int(scale * image_size[1])
        if (avatars_per_col * avatars_per_row) >= len(avatar_image_paths):
            break
        scale *= 1.05

    avatar_collation = Image.new('RGBA', (avatars_per_row * avatar_size, avatars_per_col * avatar_size))
    x, y = 0 , 0
    display("")

    for num, avatar_path in enumerate(avatar_image_paths):
        display(f"(x: {x}, y: {y})\t(~{num}/{len(avatar_image_paths)})\t({round(num/len(avatar_image_paths)*100)}%)")
        avatar_collation.paste(Image.open(avatar_path).resize((avatar_size, avatar_size)), (x * avatar_size, y * avatar_size))

        if x < avatars_per_row - 1:
            x += 1
        else:
            x = 0
            y += 1
    display("Rendering image.")
    avatar_collation.save(file_name)


async def generate(*, token: str, target_id: int, image_size: tuple[int, int], avatar_size: int, file_name: str, skip_download: bool) -> None:
    Path(AVATAR_SAVE_DIRECTORY).joinpath(f"{target_id}/").mkdir(parents=True, exist_ok=True)
    if not skip_download:
        display("Fetching members.")
        members = await fetch_members(token=token, target_id=target_id)
        display("Downloading all avatars.")
        await download_avatars(members=members, target_id=target_id, avatar_size=avatar_size)
    display("Generating image.")
    generate_image(target_id=target_id, image_size=image_size, avatar_size=avatar_size, file_name=file_name)
    display(f"Image saved to {file_name}")
    print("")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A script to process and generate a Discord server avatar collage."
    )

    parser.add_argument(
        "--token",
        type=str,
        required=True,
        help="Your Discord bot token.",
    )
    parser.add_argument(
        "--target",
        type=int,
        required=True,
        help="The guild ID you wish to create the avatar collage for.",
    )
    parser.add_argument(
        "--ar",
        type=str,
        default="1:1",
        help="Aspect ratio in the format WIDTH:HEIGHT (e.g., 16:9)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default="100",
        help="Each avatar size in pixels as an integer (e.g., 100)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="output.png",
        help="Output file name (e.g., output.png)",
    )
    parser.add_argument(
        "--skip-download",
        type=bool,
        default=False,
        help="Should the program skip the downloading process? (useful if already downloaded all images).",
    )

    # Parse the arguments
    args = parser.parse_args()

    # Validate the aspect ratio format
    if ":" not in args.ar or len(args.ar.split(":")) != 2:
        print("Error: Aspect ratio must be in the format WIDTH:HEIGHT (e.g., 16:9).", file=sys.stderr)
        sys.exit(1)

    width, height = args.ar.split(":")

    try:
        width = int(width)
        height = int(height)
    except ValueError:
        print("Error: Aspect ratio values must be integers.", file=sys.stderr)
        sys.exit(1)

    # Print the parsed arguments (this is where you can integrate additional functionality)
    print(f"Discord bot token: {args.token}")
    print(f"Target Guild ID: {args.target}")
    print(f"Aspect Ratio: {args.ar} (Width: {width}, Height: {height})")
    print(f"Avatar Size: {args.size}")
    print(f"Output File Name: {args.name}")

    asyncio.run(
        generate(
            token=args.token,
            target_id=args.target,
            image_size=(width, height),
            avatar_size=args.size,
            file_name=args.name,
            skip_download=args.skip_download,
        )
    )


if __name__ == "__main__":
    main()
