# ChangoFilm — Python Package

**changofilm is the official Python distribution of ChangoFilm, a local-first
studio for professional series short dramas.**

Install the package with **`python -m pip install changofilm`**.

ChangoFilm turns a topic or a prepared script into a finished episode: it writes
the copy, sources or generates visuals, adds voice narration, subtitles, and
background music, then composes the video on your own machine. Use the WebUI
interactively or run the same pipeline from the CLI.

## Install

Requires Python 3.11 or later. A virtual environment is recommended:

```sh
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install changofilm
```

## Start the WebUI

```sh
changofilm webui
```

The WebUI listens on localhost and opens in your browser. To select a port or run
without opening a browser:

```sh
changofilm webui --port 8503 --headless
```

## Generate a video from the CLI

```sh
changofilm cli --help
changofilm cli --video-script "Your complete script." \
  --video-source local --video-materials /absolute/path/clip.mp4 \
  --custom-audio-file /absolute/path/narration.wav \
  --no-subtitle-enabled --bgm-type none
```

Local images and videos are supported. Online language models, stock media,
and speech providers require the appropriate configuration and network access.
Choose providers and enter credentials in the WebUI settings or `config.toml`.

The package includes default fonts, background music, and an FFmpeg binary through
imageio-ffmpeg. An installed system FFmpeg takes precedence. Whisper models are
loaded on demand.

## Configuration and generated files

The installed application keeps configuration, credentials, uploads, and generated
videos in your user directory:

| System | Default directory |
| --- | --- |
| macOS | `~/Library/Application Support/ChangoFilm` |
| Windows | `%LOCALAPPDATA%\ChangoFilm` |
| Linux | `~/.local/share/ChangoFilm` (or `$XDG_DATA_HOME/ChangoFilm`) |

Set `CHANGOFILM_HOME` before starting the application to choose another directory.
Configuration is stored in `config.toml`; generated videos are under
`storage/tasks/<task-id>/`. Existing user configuration and resources are preserved
when the application starts or upgrades.

See the [project documentation](https://github.com/wyg5208/changofilm)
for supported providers and advanced options. Report problems through
[GitHub Issues](https://github.com/wyg5208/changofilm/issues).
