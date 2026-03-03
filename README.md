> **Disclaimer:** This is an AI-generated Python script. Review the code before running it in your environment. The author is not responsible for any damages this script may cause.

# watcher

A Python script that keeps [changedetection.io](https://changedetection.io) and [FlexGet](https://flexget.com) in sync by appending keywords to both in a single run.

## What it does

| Variable | FlexGet task | changedetection.io watch |
|---|---|---|
| `KEYWORDS_MR` | appends to `jav_mr` | appends to `CD_WATCH_UUID_MR` |
| `KEYWORDS_VR` | appends to `jav_vr` | appends to `CD_WATCH_UUID_VR` |

- Skips duplicate keywords in both changedetection and FlexGet
- Adds a dated comment in `config.yml` above each batch of new keywords
- FlexGet's `config.yml` is accessed over SSH since it lives on a remote Debian LXC
- Either keyword list can be left blank — that side will simply be skipped

## Requirements

```
pip install requests ruamel.yaml python-dotenv paramiko
```

## Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your values
3. Run the script

```bash
python main.py
```

## .env reference

```env
# changedetection.io
CD_BASE_URL=https://your-changedetection-url.com
CD_API_KEY=your_api_key_here
CD_WATCH_UUID_MR=your-mr-watch-uuid-here
CD_WATCH_UUID_VR=your-vr-watch-uuid-here

# FlexGet (remote Debian LXC via SSH)
SSH_HOST=192.168.x.x
SSH_PORT=22
SSH_USER=your_ssh_user
SSH_KEY_PATH=/home/youruser/.ssh/id_rsa
FLEXGET_CONFIG_PATH=/path/on/remote/to/flexget/config.yml

# Keywords — comma-separated, can be left blank
KEYWORDS_MR=ABF-319,ABF-328
KEYWORDS_VR=VRKM-1234,SAVR-001
```

> **Note:** Never commit your `.env` file. It is excluded via `.gitignore`.

## How keywords are added to FlexGet config.yml

Each new batch is stamped with a date comment directly above the first appended entry:

```yaml
    regexp:
      accept:
        # added Mar 03, 2026
        - ABF-319
        - ABF-328
```