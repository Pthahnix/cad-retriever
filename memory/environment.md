---
name: environment
description: Hardware, software, and path configuration for this AutoDL pod
metadata:
  type: reference
---
- GPU: NVIDIA RTX 5090, 31GB VRAM, CUDA 12.8
- Python: /root/miniconda3/bin/python3 (3.12.3)
- PATH: /root/miniconda3/bin:/home/cc/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
- Proxy: http://127.0.0.1:7890 (mihomo, required for all internet access)
- Data disk: /home/cc/data → /root/autodl-tmp (2TB, symlink)
- Blender: /home/cc/data/blender-4.5.4-linux-x64/blender-wrapper.sh (needs LD_LIBRARY_PATH from conda pkgs)
- Key packages: torch 2.8.0+cu128, open_clip_torch 3.3.0, faiss 1.12.0, numpy 1.26.4, cv2 4.13.0
- OCP (OpenCASCADE): installed via cadquery, available as `from OCP.STEPControl import ...`
- py7zr: installed for 7z extraction (no system 7z available)
- NEVER write data to /home/cc/cad-retriever/data/ or /tmp/ — use /home/cc/data/ only
