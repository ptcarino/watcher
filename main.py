"""
main.py

KEYWORDS_MR  →  FlexGet jav_mr task  +  changedetection watch (CD_WATCH_UUID_MR)
KEYWORDS_VR  →  FlexGet jav_vr task  +  changedetection watch (CD_WATCH_UUID_VR)

FlexGet config.yml lives on a remote Debian LXC — accessed via SSH key.

Requirements:
    pip install requests ruamel.yaml python-dotenv paramiko
"""

import io
import os
import requests
import sys
from datetime import datetime
from dotenv import load_dotenv
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq
import paramiko

load_dotenv()

# ── Config from .env ────────────────────────────────────────────────────────

CD_BASE_URL      = os.getenv("CD_BASE_URL", "").rstrip("/")
CD_API_KEY       = os.getenv("CD_API_KEY", "")
CD_WATCH_UUID_MR = os.getenv("CD_WATCH_UUID_MR", "")
CD_WATCH_UUID_VR = os.getenv("CD_WATCH_UUID_VR", "")

SSH_HOST            = os.getenv("SSH_HOST", "")
SSH_PORT            = int(os.getenv("SSH_PORT", "22"))
SSH_USER            = os.getenv("SSH_USER", "")
SSH_KEY_PATH        = os.getenv("SSH_KEY_PATH", "")
FLEXGET_CONFIG_PATH = os.getenv("FLEXGET_CONFIG_PATH", "")

KEYWORDS_MR = [
    k.strip() for k in os.getenv("KEYWORDS_MR", "").split(",") if k.strip()
]
KEYWORDS_VR = [
    k.strip() for k in os.getenv("KEYWORDS_VR", "").split(",") if k.strip()
]


# ── Validation ───────────────────────────────────────────────────────────────

def validate_env():
    missing = []
    for var in ["CD_BASE_URL", "CD_API_KEY", "CD_WATCH_UUID_MR", "CD_WATCH_UUID_VR",
                "SSH_HOST", "SSH_USER", "SSH_KEY_PATH", "FLEXGET_CONFIG_PATH"]:
        if not os.getenv(var):
            missing.append(var)
    if missing:
        print(f"[ERROR] Missing required .env variables: {', '.join(missing)}")
        sys.exit(1)
    if not os.path.exists(SSH_KEY_PATH):
        print(f"[ERROR] SSH key not found: {SSH_KEY_PATH}")
        sys.exit(1)
    if not KEYWORDS_MR and not KEYWORDS_VR:
        print("No keywords provided — nothing to do.")
        sys.exit(0)


# ── SSH helpers ──────────────────────────────────────────────────────────────

def get_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=SSH_HOST,
        port=SSH_PORT,
        username=SSH_USER,
        key_filename=SSH_KEY_PATH,
    )
    return client


def read_remote_file(sftp, path):
    with sftp.open(path, "r") as f:
        return f.read()


def write_remote_file(sftp, path, content):
    with sftp.open(path, "w") as f:
        f.write(content)


# ── changedetection.io ───────────────────────────────────────────────────────

def update_changedetection_watch(uuid, keywords, label):
    headers = {"x-api-key": CD_API_KEY, "Content-Type": "application/json"}
    url = f"{CD_BASE_URL}/api/v1/watch/{uuid}"

    print(f"[CD] [{label}] Fetching watch {uuid}...")
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    watch = resp.json()

    existing = watch.get("trigger_text") or []
    added = [k for k in keywords if k not in existing]
    if not added:
        print(f"[CD] [{label}] All keywords already present, nothing to update.")
        return

    updated = existing + added
    print(f"[CD] [{label}] Appending: {added}")
    put_resp = requests.put(url, headers=headers, json={"trigger_text": updated}, timeout=10)
    put_resp.raise_for_status()
    print(f"[CD] [{label}] Done. trigger_text now has {len(updated)} entries.")


def update_changedetection():
    if KEYWORDS_MR:
        update_changedetection_watch(CD_WATCH_UUID_MR, KEYWORDS_MR, "jav_mr")
    else:
        print("[CD] [jav_mr] KEYWORDS_MR is empty, skipping.")

    if KEYWORDS_VR:
        update_changedetection_watch(CD_WATCH_UUID_VR, KEYWORDS_VR, "jav_vr")
    else:
        print("[CD] [jav_vr] KEYWORDS_VR is empty, skipping.")


# ── FlexGet config.yml (remote) ──────────────────────────────────────────────

def append_to_task(config, task_name, keywords):
    tasks = config.get("tasks", {})
    if task_name not in tasks:
        print(f"[FG] [ERROR] Task '{task_name}' not found in config.")
        print(f"[FG] Available tasks: {list(tasks.keys())}")
        sys.exit(1)

    task = tasks[task_name]
    if "regexp" not in task:
        task["regexp"] = {}
    if "accept" not in task["regexp"]:
        task["regexp"]["accept"] = []

    accept_list = task["regexp"]["accept"]
    added = [k for k in keywords if k not in accept_list]
    if not added:
        print(f"[FG] [{task_name}] All keywords already present, nothing to update.")
        return

    date_str = datetime.now().strftime("%b %d, %Y")
    insert_pos = len(accept_list)
    for keyword in added:
        accept_list.append(keyword)

    if isinstance(accept_list, CommentedSeq):
        accept_list.yaml_set_comment_before_after_key(insert_pos, before=f"added {date_str}", indent=6)

    print(f"[FG] [{task_name}] Appending: {added} (# added {date_str})")
    print(f"[FG] [{task_name}] regexp.accept now has {len(accept_list)} entries.")


def update_flexget():
    print(f"[FG] Connecting to {SSH_USER}@{SSH_HOST}:{SSH_PORT}...")
    ssh = get_ssh_client()
    sftp = ssh.open_sftp()

    try:
        print(f"[FG] Reading remote config: {FLEXGET_CONFIG_PATH}")
        raw = read_remote_file(sftp, FLEXGET_CONFIG_PATH)

        yaml = YAML()
        yaml.preserve_quotes = True
        config = yaml.load(raw)

        if KEYWORDS_MR:
            append_to_task(config, "jav_mr", KEYWORDS_MR)
        else:
            print("[FG] [jav_mr] KEYWORDS_MR is empty, skipping.")

        if KEYWORDS_VR:
            append_to_task(config, "jav_vr", KEYWORDS_VR)
        else:
            print("[FG] [jav_vr] KEYWORDS_VR is empty, skipping.")

        buf = io.StringIO()
        yaml.dump(config, buf)
        write_remote_file(sftp, FLEXGET_CONFIG_PATH, buf.getvalue())
        print("[FG] Remote config saved.")

    finally:
        sftp.close()
        ssh.close()


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    validate_env()
    update_changedetection()
    update_flexget()
    print("\n✓ All updates complete.")