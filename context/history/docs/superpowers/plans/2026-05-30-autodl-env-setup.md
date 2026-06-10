# AutoDL Environment Setup Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up a fully configured AutoDL pod with mihomo proxy, Claude Code + superpowers plugin, and ML training environment for the CAD Sketch Retriever project.

**Architecture:** Root installs mihomo (proxy) and creates `cc` user. `cc` user gets Claude Code, Node.js, Python ML stack (PyTorch + OpenCLIP + FAISS-GPU + Blender), and project repo. SSH key auth configured for passwordless access from local Windows machine.

**Tech Stack:** mihomo v1.19.22, Claude Code CLI, Node.js LTS (nvm), Python 3.11+, PyTorch 2.x, OpenCLIP, FAISS-GPU, Blender 4.x headless

**Connection:**
```
ssh -p 50610 root@connect.bjb2.seetacloud.com
Password: JtM2QbBZMUyA
```

---

## Task 1: Configure SSH Key Auth (Local Windows)

**Purpose:** Set up passwordless SSH from local machine to AutoDL pod.

- [ ] **Step 1: Generate SSH key if not exists**

```powershell
# On local Windows — check if key exists
if (-not (Test-Path "$env:USERPROFILE\.ssh\id_ed25519.pub")) {
    ssh-keygen -t ed25519 -C "strix@autodl" -f "$env:USERPROFILE\.ssh\id_ed25519" -N ""
}
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
```

- [ ] **Step 2: Copy public key to AutoDL pod**

```powershell
# Copy key to remote (will prompt for password: JtM2QbBZMUyA)
type "$env:USERPROFILE\.ssh\id_ed25519.pub" | ssh -p 50610 root@connect.bjb2.seetacloud.com "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

- [ ] **Step 3: Verify passwordless login**

```powershell
ssh -p 50610 root@connect.bjb2.seetacloud.com "echo 'SSH key auth OK'"
```

Expected: `SSH key auth OK` without password prompt.

- [ ] **Step 4: Add SSH config entry for convenience**

```powershell
Add-Content "$env:USERPROFILE\.ssh\config" @"

Host autodl
    HostName connect.bjb2.seetacloud.com
    Port 50610
    User root
    IdentityFile ~/.ssh/id_ed25519
"@
```

Verify: `ssh autodl "hostname"` should work without password.

---

## Task 2: Create User & Install Mihomo (Root)

- [ ] **Step 1: Create cc user**

```bash
# SSH as root
useradd -m -s /bin/bash cc
usermod -aG sudo cc
chown -R cc:cc /home/cc
echo "cc ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
```

- [ ] **Step 2: Copy SSH key to cc user too**

```bash
mkdir -p /home/cc/.ssh
cp /root/.ssh/authorized_keys /home/cc/.ssh/authorized_keys
chown -R cc:cc /home/cc/.ssh
chmod 700 /home/cc/.ssh
chmod 600 /home/cc/.ssh/authorized_keys
```

- [ ] **Step 3: Download and install mihomo**

```bash
cd /tmp
curl -L --connect-timeout 30 --max-time 600 --retry 3 \
  "https://gh-proxy.com/https://github.com/MetaCubeX/mihomo/releases/download/v1.19.22/mihomo-linux-amd64-v1.19.22.gz" \
  -o mihomo.gz
gzip -d mihomo.gz
chmod +x mihomo
mkdir -p ~/mihomo
mv /tmp/mihomo ~/mihomo/mihomo
~/mihomo/mihomo -v
```

Expected: `Mihomo Meta v1.19.22` or similar version string.

- [ ] **Step 4: Download geo databases**

```bash
mkdir -p ~/.config/mihomo
cd ~/.config/mihomo
curl -L --connect-timeout 30 --max-time 120 \
  "https://gh-proxy.com/https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip.metadb" \
  -o geoip.metadb
curl -L --connect-timeout 30 --max-time 120 \
  "https://gh-proxy.com/https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geosite.dat" \
  -o geosite.dat
ls -la ~/.config/mihomo/
```

Expected: `geoip.metadb` and `geosite.dat` both non-empty.

---

## Task 3: Configure & Start Mihomo (Root)

VPN subscription: `https://dash.xn--cp3a08l.com/api/v1/pq/8beec87101a19033dceaed20133bd993`

- [ ] **Step 1: Write mihomo config with proxy-providers**

```bash
cat > /root/.config/mihomo/config.yaml << 'MEOF'
mixed-port: 7890
external-controller: 127.0.0.1:9090
mode: rule
log-level: info

proxy-providers:
  my-sub:
    type: http
    url: "https://api.dler.io/sub?target=clash&url=https%3A%2F%2Fdash.xn--cp3a08l.com%2Fapi%2Fv1%2Fpq%2F8beec87101a19033dceaed20133bd993&config=https%3A%2F%2Fraw.githubusercontent.com%2FACL4SSR%2FACL4SSR%2Fmaster%2FClash%2Fconfig%2FACL4SSR_Online.ini"
    interval: 3600
    path: ./proxy-provider.yaml
    health-check:
      enable: true
      url: http://www.gstatic.com/generate_204
      interval: 300

proxy-groups:
  - name: PROXY
    type: select
    use:
      - my-sub

rules:
  - GEOIP,CN,DIRECT
  - MATCH,PROXY
MEOF
```

- [ ] **Step 2: Start mihomo in background**

```bash
unset http_proxy https_proxy
nohup ~/mihomo/mihomo -d ~/.config/mihomo > /tmp/mihomo.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:9090/
```

Expected: JSON response from mihomo API (e.g. `{"hello":"clash"}`).

- [ ] **Step 3: Verify proxy works**

```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
curl -s http://httpbin.org/ip
curl -s https://www.google.com -o /dev/null -w "%{http_code}"
```

Expected: Non-Chinese IP from httpbin, `200` from Google.

- [ ] **Step 4: If proxy-providers fails (403 from AutoDL IP), use local download fallback**

On local Windows PowerShell:
```powershell
$sub = [uri]::EscapeDataString("https://dash.xn--cp3a08l.com/api/v1/pq/8beec87101a19033dceaed20133bd993")
curl.exe -L "https://api.dler.io/sub?target=clash&url=$sub&config=https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/ACL4SSR_Online.ini" -o "config.yaml"
```

Then upload via `scp -P 50610 config.yaml root@connect.bjb2.seetacloud.com:/root/.config/mihomo/config.yaml` and restart mihomo.

---

## Task 4: Install Claude Code & Superpowers (cc user)

- [ ] **Step 1: Switch to cc user and set proxy**

```bash
su - cc
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
```

- [ ] **Step 2: Install Claude Code**

```bash
curl -fsSL https://claude.ai/install.sh | bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
claude --version
```

Expected: Claude Code version string (e.g. `2.1.x`).

- [ ] **Step 3: Write persistent environment variables to .bashrc**

```bash
cat >> ~/.bashrc << 'EOF'
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
export ANTHROPIC_BASE_URL="https://api.ikuncode.cc"
export ANTHROPIC_AUTH_TOKEN="sk-fumg5WK5yHWYV4OJaabjrABvQvO2eslfMda47gPtUs5iV9QX"
export ANTHROPIC_MODEL="claude-opus-4-6"
EOF
source ~/.bashrc
```

- [ ] **Step 4: Configure Claude Code permissions (bypass mode)**

```bash
mkdir -p ~/.claude
cat > ~/.claude/settings.json << 'EOF'
{
  "permissions": {
    "defaultMode": "bypassPermissions"
  }
}
EOF
```

- [ ] **Step 5: Install Node.js via nvm**

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc
nvm install --lts
node -v
npm -v
```

Expected: Node.js v22.x+ and npm v10.x+.

- [ ] **Step 6: Launch Claude Code and install superpowers plugin**

```bash
cd /home/cc
claude --dangerously-skip-permissions
```

Inside Claude Code session, run:
```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

Then exit with `/exit`.

- [ ] **Step 7: Verify Claude Code works**

```bash
claude --version
claude -p "echo hello"
```

Expected: Claude responds without errors.

---

## Task 5: Mount Data Disk & Configure Git (cc user)

- [ ] **Step 1: Mount data disk (as root)**

```bash
# Exit to root first, then:
chmod o+x /root
ln -s /root/autodl-tmp /home/cc/data
chown -R cc:cc /root/autodl-tmp
su - cc -c "df -h /home/cc/data && touch /home/cc/data/.test && rm /home/cc/data/.test && echo 'Data disk OK'"
```

Expected: `Data disk OK` and shows ~2TB available.

- [ ] **Step 2: Configure git (as cc user)**

```bash
su - cc
cat >> ~/.bashrc << 'EOF'
export GITHUB_PAT="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"
export HF_TOKEN="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"
EOF
source ~/.bashrc

git config --global user.name "Pthahnix"
git config --global user.email "temp.bringer@gmail.com"
git config --global url."https://${GITHUB_PAT}@github.com/".insteadOf "https://github.com/"
```

- [ ] **Step 3: Clone cad-retriever project**

```bash
cd /home/cc
git clone https://github.com/Pthahnix/cad-retriever.git
cd cad-retriever
ls
```

Expected: Project files visible (pyproject.toml, src/, etc. once implemented).

---

## Task 6: Install ML Training Environment (cc user)

- [ ] **Step 1: Create conda/venv environment**

```bash
cd /home/cc/cad-retriever
python3 -m venv .venv
source .venv/bin/activate
echo 'source /home/cc/cad-retriever/.venv/bin/activate' >> ~/.bashrc
pip install --upgrade pip
```

- [ ] **Step 2: Install PyTorch with CUDA support**

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0)}')"
```

Expected: `PyTorch 2.x.x, CUDA: True, Device: NVIDIA GeForce RTX 5090` (or whatever GPU the pod has).

- [ ] **Step 3: Install OpenCLIP and FAISS-GPU**

```bash
pip install open-clip-torch faiss-gpu
python -c "import open_clip; print(f'OpenCLIP OK: {open_clip.__version__}')"
python -c "import faiss; print(f'FAISS OK: {faiss.__version__}, GPU: {faiss.get_num_gpus()}')"
```

Expected: Both imports succeed, FAISS reports >=1 GPU.

- [ ] **Step 4: Install remaining project dependencies**

```bash
pip install fastapi uvicorn pydantic tqdm Pillow numpy wandb opencv-python-headless
pip install pytest pytest-cov  # dev deps
```

- [ ] **Step 5: Install Blender headless**

```bash
# Download Blender 4.x for Linux
cd /tmp
curl -L "https://mirror.clarkson.edu/blender/release/Blender4.1/blender-4.1.1-linux-x64.tar.xz" -o blender.tar.xz
tar -xf blender.tar.xz -C /opt/
ln -s /opt/blender-4.1.1-linux-x64/blender /usr/local/bin/blender
blender --version
```

Expected: `Blender 4.1.1` (run as root for /opt install, or adjust path).

- [ ] **Step 6: Install project in editable mode**

```bash
cd /home/cc/cad-retriever
pip install -e ".[dev,train]"
python -c "from cad_retriever.config import Config; print('Project import OK')"
```

Expected: `Project import OK`.

- [ ] **Step 7: Verify full stack**

```bash
python -c "
import torch, open_clip, faiss, numpy, PIL, cv2, fastapi
print(f'torch={torch.__version__} cuda={torch.cuda.is_available()}')
print(f'open_clip={open_clip.__version__}')
print(f'faiss={faiss.__version__} gpus={faiss.get_num_gpus()}')
print(f'numpy={numpy.__version__}')
print(f'PIL={PIL.__version__}')
print(f'cv2={cv2.__version__}')
print(f'fastapi={fastapi.__version__}')
print('ALL OK')
"
```

Expected: All versions printed, ending with `ALL OK`.

---

## Execution Order

1. Task 1 (SSH key) — from local Windows
2. Task 2 (user + mihomo install) — as root on pod
3. Task 3 (mihomo config + start) — as root on pod
4. Task 4 (Claude Code + superpowers) — as cc user
5. Task 5 (data disk + git) — root then cc
6. Task 6 (ML environment) — as cc user

**After completion:** The pod is ready for the main implementation plan (`2026-05-30-cad-sketch-retriever.md`). Proceed to Task 7 to launch remote CC and execute it.

---

## Task 7: Launch Remote Claude Code via /tmux-cc

**Prerequisites:** All previous tasks complete. The `cad-retriever` repo has been pushed with plan files committed.

- [ ] **Step 1: Ensure plan files are committed and pushed (on local Windows)**

```bash
cd G:\.workshop\cad-retrieve
git add docs/superpowers/plans/ docs/superpowers/specs/
git commit -m "docs: add design spec and implementation plans"
git push origin main
```

- [ ] **Step 2: Pull latest on AutoDL (as cc user)**

```bash
cd /home/cc/cad-retriever
git pull origin main
ls docs/superpowers/plans/
```

Expected: `2026-05-30-cad-sketch-retriever.md` visible.

- [ ] **Step 3: Use /tmux-cc skill to launch remote Claude Code session**

From local Claude Code, invoke:
```
/tmux-cc
```

Connection details:
- Host: `connect.bjb2.seetacloud.com`
- Port: `50610`
- User: `cc`
- Auth: SSH key (configured in Task 1)
- Working directory: `/home/cc/cad-retriever`

- [ ] **Step 4: In the remote CC session, execute the retriever plan**

The remote Claude Code session should run:
```
/superpowers:executing-plans docs/superpowers/plans/2026-05-30-cad-sketch-retriever.md
```

This will execute all 13 tasks of the retriever plan autonomously on the AutoDL pod.
