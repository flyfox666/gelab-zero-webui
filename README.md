
<img width="1920" height="1606" alt="Stepfun-ai-gelab-zero-12-21-2025_09_05_PM" src="https://github.com/user-attachments/assets/b8f2227b-56c6-4f60-ba86-4dcbe7b49835" />

> 👋 Hi, everyone! We are proud to present the first fully open-source GUI Agent with both model and infrastructure.

<p align="center">
  <a href="https://arxiv.org/abs/2512.15431"><img src="https://img.shields.io/badge/arXiv-Step--GUI Technical Report-B31B1B.svg?logo=arxiv&logoColor=white" alt="arXiv" /></a>
  <a href="https://opengelab.github.io/"><img src="https://img.shields.io/badge/🌐%20Website-Project%20Page-blue" alt="Website" /></a>
  <a href="https://huggingface.co/stepfun-ai/GELab-Zero-4B-preview"><img src="https://img.shields.io/badge/🤗%20Hugging%20Face-GELab--Zero--4B--preview-orange" alt="Hugging Face Model" /></a>
</p>

<p align="center">
  <a href="./README.md">English</a> |
  <a href="./README_CN.md">简体中文</a>
</p>

---

# 🚀 Fork Enhancements

> **This project is enhanced from [stepfun-ai/gelab-zero](https://github.com/stepfun-ai/gelab-zero)**
> 
> The following content describes new features added in this Fork. For original content, see [Official Original Content](#-official-original-content) section.

## 🖥️ Web UI Features

Launch: `python start_web_ui.py`, then visit `http://localhost:8866`

**Left Panel - Control**

| Module | Features |
|--------|----------|
| **📱 Device Management** | Check device status, view device list, restart ADB service |
| **📶 Wireless Debugging** | Connect device via IP address, enable TCP/IP mode |
| **📊 Task Monitoring** | View task status, ⏸️ **Pause/Inject/Resume**, select historical Sessions |
| **💬 Command/Reply** | Enter task instructions or reply to Agent, supports `Ctrl+Enter` |
| **⚙️ Model Configuration** | Select model provider, 🔍 **Check model connection**, configure API |
| **🛠 Utilities** | Launch scrcpy, get app list, 📄 **Export PDF trajectory** |

**Right Panel - Display**

| Module | Features |
|--------|----------|
| **📱 Task Trajectory** | Visual replay of each step with screenshots, thought process, action details |
| **📋 Real-time Logs** | Real-time task execution output, with clear and copy buttons |

## ✨ New Features

### ⏸️ Pause / Inject / Resume

During task execution, you can:
- **Instant Pause**: Click pause button to immediately terminate current execution
- **Inject Instructions**: Enter correction instructions (e.g., "search for xxx instead")
- **Seamless Resume**: Continue from the same Session, maintaining trajectory integrity

> 💡 Solves the pain point of not being able to manually intervene during Agent execution

### 🔍 Model Connection Check

One-click test in configuration panel:
- Quickly test if local/online model is available
- Automatically distinguish local (Ollama) vs online API
- Display connection status and model name

### 📋 Multi-Provider Configuration

Auto-loaded from `model_config.yaml`, each provider configures:

```yaml
local:
    display_name: "Local Model (Ollama)"
    api_base: "http://localhost:11434/v1"
    api_key: "EMPTY"
    default_model: "gelab-zero-4b-preview"

stepfun:
    display_name: "StepFun"
    api_base: "https://api.stepfun.com/v1"
    api_key: "YOUR_API_KEY"
    default_model: "step-gui"
```

### 📄 PDF Trajectory Export

- Export task execution trajectory to PDF file
- Includes screenshots, thought process, action details
- Auto-download support

### 🎨 UI Improvements

- **Three-line Configuration**: Base URL, API Key, Model Name on separate rows for easier input
- **Improved Status Display**: Clearer task status feedback (Ready/Running/Waiting/Paused)
- **Reply Interaction Fix**: Properly detects waiting for input state when Agent asks questions

---

# 📖 Official Original Content

> The following content is from [stepfun-ai/gelab-zero](https://github.com/stepfun-ai/gelab-zero) original README

## 📑 Table of Contents

- [📖 Background](#-background)
- [🎥 Application Demonstrations](#-application-demonstrations)
- [🏆 Open Benchmark](#-open-benchmark)
- [🚀 Installation & Quick Start](#-installation--quick-start)
- [📝 Citation](#-citation)


## 📖 Background

As AI experiences increasingly penetrate consumer-grade devices, Mobile Agent research is at a critical juncture. GELab-Zero is designed to dismantle these barriers.

* **⚡️ Out-of-the-Box Full-Stack Infrastructure** - Unified one-click inference pipeline
* **🖥️ Consumer-Grade Local Deployment** - Built-in 4B GUI Agent model, optimized for Mac (M-series) and RTX 4060
* **📱 Flexible Task Distribution** - Supports ReAct loops, multi-agent collaboration, and scheduled tasks
* **🚀 Accelerate Prototype to Production** - Rapid validation of interaction strategies

## 🎥 Application Demonstrations

| Task Type | Example |
|-----------|---------|
| Recommendation - Sci-Fi Movies | Help me find good recent sci-fi movies |
| Recommendation - Travel | Find a weekend place for kids |
| Practical - Claim Subsidy | Claim meal vouchers on enterprise platform |
| Practical - Metro Query | Check if Metro Line 1 is operating |
| Complex - Multi-Item Shopping | Purchase multiple items on Ele.me |
| Complex - Conditional Search | Find canvas shoes under 100 yuan on Taobao |

See `images/` directory for demo videos and GIFs.

## 🏆 Open Benchmark

![Open Benchmark Comparison Results](./images/Result.jpeg)

GELab-Zero-4B-preview shows exceptional performance across multiple benchmarks, especially in Android World real mobile scenarios.

## 🚀 Installation & Quick Start

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/stepfun-ai/gelab-zero
cd gelab-zero

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch Web UI
python start_web_ui.py
```

### Full Installation Steps

1. **Python Environment** - Recommended: miniforge, Python 3.12+
2. **LLM Inference** - Install Ollama and deploy gelab-zero-4b-preview model
3. **Android Device Setup** - Enable developer mode and USB debugging, install ADB tool
4. **Run Agent** - Use Web UI or command line

### Ollama Model Deployment

```bash
pip install huggingface_hub
hf download --no-force-download stepfun-ai/GELab-Zero-4B-preview --local-dir gelab-zero-4b-preview

cd gelab-zero-4b-preview
ollama create gelab-zero-4b-preview -f Modelfile
```

Test model:
```bash
curl -X POST http://localhost:11434/v1/chat/completions \
 -H "Content-Type: application/json" \
 -d '{"model": "gelab-zero-4b-preview", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### Wireless Debugging

1. Phone and computer on same WiFi
2. Phone: Settings → Developer Options → Wireless Debugging
3. Enter phone IP address in Web UI to connect

---

## 📝 Citation

```bibtex
@misc{yan2025stepguitechnicalreport,
      title={Step-GUI Technical Report}, 
      author={Haolong Yan and Jia Wang and Xin Huang and ...},
      year={2025},
      url={https://arxiv.org/abs/2512.15431}, 
}
```

## ⭐ Star History
<div align="center">
  <a href="https://star-history.com/#stepfun-ai/gelab-zero&Date">
    <img src="https://api.star-history.com/svg?repos=stepfun-ai/gelab-zero&type=Date" alt="Star History Chart" width="600">
  </a>
</div>
