import os
import json
import base64
import urllib.request
import urllib.error
import sys
import subprocess
import time

# Get token from gh
gh_paths = [
    r"C:\Users\r9000p\bin\gh.exe",
    r"C:\Users\r9000p\.workbuddy\binaries\gh\gh.exe",
    "gh",
]
token = None
for p in gh_paths:
    try:
        result = subprocess.run([p, "auth", "token"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            token = result.stdout.strip()
            break
    except:
        continue

if not token:
    print("ERROR: 无法获取gh token")
    sys.exit(1)

repo_owner = "fight1n"
repo_name = "customer-service-agent"
project_dir = "D:/WorkBuddyWork/2026-08-09-16-04-55/customer-service-agent"

# Collect files
exclude_dirs = {'.venv', '.idea', '.git', '__pycache__', '.pytest_cache', '.temp_push.py'}
files_to_push = []
for root, dirs, files in os.walk(project_dir):
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    for f in files:
        if f.endswith('.pyc'):
            continue
        full_path = os.path.join(root, f)
        rel_path = os.path.relpath(full_path, project_dir).replace('\\', '/')
        files_to_push.append((rel_path, full_path))

print(f"找到 {len(files_to_push)} 个文件待推送")

api_base = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "push-script",
}

# Push each file using Contents API
success = 0
failed = []
for i, (rel_path, full_path) in enumerate(files_to_push, 1):
    with open(full_path, 'rb') as fh:
        content_bytes = fh.read()

    if b'\x00' in content_bytes[:8192]:
        print(f"[{i}/{len(files_to_push)}] SKIP binary: {rel_path}")
        continue

    if len(content_bytes) > 100 * 1024 * 1024:
        print(f"[{i}/{len(files_to_push)}] SKIP too large: {rel_path}")
        continue

    content_b64 = base64.b64encode(content_bytes).decode('ascii')

    # Check if file already exists to get sha (needed for updates)
    get_url = f"{api_base}/contents/{rel_path}"
    get_req = urllib.request.Request(get_url, headers=headers)
    existing_sha = None
    try:
        with urllib.request.urlopen(get_req) as resp:
            existing = json.loads(resp.read())
            existing_sha = existing.get("sha")
    except urllib.error.HTTPError:
        pass  # File doesn't exist yet

    data = {
        "message": f"feat: add {rel_path}" if i == 1 else f"chore: add {rel_path}",
    }
    if existing_sha:
        data["sha"] = existing_sha
        data["message"] = f"update {rel_path}"

    data["content"] = content_b64

    put_url = f"{api_base}/contents/{rel_path}"
    put_req = urllib.request.Request(
        put_url,
        data=json.dumps(data).encode('utf-8'),
        headers={**headers, "Content-Type": "application/json"},
        method="PUT",
    )

    try:
        with urllib.request.urlopen(put_req) as resp:
            result = json.loads(resp.read())
            commit_url = result.get("commit", {}).get("html_url", "")
            print(f"[{i}/{len(files_to_push)}] OK: {rel_path}")
            success += 1
        time.sleep(0.3)  # Rate limit protection
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        failed.append((rel_path, e.code, err_body[:200]))
        print(f"[{i}/{len(files_to_push)}] FAIL {e.code}: {rel_path}")

print()
print(f"成功: {success}/{len(files_to_push)}")
if failed:
    print(f"失败: {len(failed)}")
    for path, code, msg in failed[:5]:
        print(f"  {code} {path}: {msg}")

print()
print(f"仓库地址: https://github.com/{repo_owner}/{repo_name}")