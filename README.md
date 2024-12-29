# Discord avatar collage maker

## Hosting

- Create a Python environment and install `requirements.txt`.
- Ensure that the bot has the "Server Members Intent".
- Invite the bot to your server (duh).
- Run `python collage.py --token YOUR_BOT_TOKEN --target THE_TARGET_GUILD_ID --ar 16:9`
- Wait for the image to be generated.

## Script arguments

| Argument            | Type   | Required | Default        | Description                                                                                      |
|---------------------|--------|----------|----------------|--------------------------------------------------------------------------------------------------|
| `--token`           | `str`  | Yes      | None           | Your Discord bot token.                                                                          |
| `--target`          | `int`  | Yes      | None           | The guild ID you wish to create the avatar collage for.                                          |
| `--ar`              | `str`  | No       | `"1:1"`        | Aspect ratio in the format `WIDTH:HEIGHT` (e.g., `16:9`).                                        |
| `--size`            | `int`  | No       | `100`          | Each avatar size in pixels as an integer (e.g., `100`).                                          |
| `--name`            | `str`  | No       | `"output.png"` | Output file name (e.g., `output.png`).                                                           |
| `--skip-download`   | `bool` | No       | `False`        | Should the program skip the downloading process? (useful if already downloaded all images).      |
| `--by-age`          | `bool` | No       | `False`        | Should the members be rendered by account age rather than in a random order?                     |
| `--exclude-default` | `bool` | No       | `False`        | Should default avatars be excluded from the rendering process?                                   |

## Example image

![image](example-image.png)
