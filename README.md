# VideoLink-to-Text 🎬 ➡️ 📝

> **本地运行、极速高效的视频转文字与智能章节排版工具**  
> 支持 B站 / YouTube 网络链接与本地音视频，优先秒提原片字幕，智能降级本地 Faster-Whisper GPU/CPU 离线听写，自动语义分段与段落排版，杜绝生硬切片，保护数据隐私，绝不占用系统 C 盘。

---

## 🌟 核心特性

### 1. 🎯 多源输入与批量并发队列
- **支持网络链接**：支持多行粘贴 **B 站视频**（BV号、av号、分P多P列表）、**YouTube 视频** 链接；
- **支持本地音视频**：支持输入本地文件绝对路径（如 `D:\Videos\meeting.mp4`、`录音.m4a`、`podcast.mp3` 等）；
- **批量处理队列**：后台自动排队顺序处理，前端通过 WebSocket 实时推送精准任务进度条与当前步骤描述。

### 2. ⚡ 双轨转录机制：秒级原片字幕 + 离线 ASR 听写
- **优先秒提原片字幕**：自动探测视频源是否存在官方 CC 字幕或平台内置 AI 字幕。若有，**数秒内直接下载解析字幕轨，无需下载音视频文件**，节省带宽与时间；
- **智能降级 ASR 离线听写**：若无原片字幕，自动使用 `ffmpeg` 抽取音频流，调用本地 **Faster-Whisper** 引擎离线转录，支持中英文混杂识别、VAD 静音切分与自动标点预测。

### 3. 🔒 100% 本地部署与隐私安全
- **零数据上云**：所有语音识别与文本处理均在本地电脑显卡/CPU 上离线执行，任何音频、字幕或转录产物绝不上传第三方服务器；
- **离线运行能力**：模型首次使用下载后永久缓存在本地。针对本地视频文件，**拔掉网线亦可 100% 离线脱机运行**。

### 4. 🚀 硬件自适应加速 (CUDA GPU / CPU)
- **NVIDIA 显卡加速**：自动检测 CUDA 环境并调用 NVIDIA GPU（如 RTX 3060 / 4060 等）进行 `float16` 高速并行计算；
- **CPU 平滑降级**：在无独立显卡或非 N 卡设备上，自动切换至 CPU `int8` 低开销模式，兼顾速度与内存占用。

### 5. ✍️ 智能内容分段与自然中文排版
- **彻底去除生硬空格**：针对语音识别常见的中文字符间空格、断词生硬问题，内置原生中文断句与平滑拼接算法；
- **优先对齐原片章节**：自动抓取 YouTube Chapters 或 B 站分P/简介时间轴（如 `03:15 架构演进`），保留作者原汁原味的章节划分；
- **基于语义转向智能探测**：无作者章节时，结合语音停顿与语篇标志词（*“首先 / 其次 / 第一点 / 接下来 / 总结一下”* 等）识别内容转折点；
- **无转向不强行切片**：通篇为单一主题或日常对话时，**绝不进行机械式的“5分钟硬切片”**，直接输出自然连贯的转录全文。

### 6. 📄 丰富的多格式导出与时间轴逐句稿
- **常规文档（默认）**：
  - `.MD`：格式优美的 Markdown，带元信息、目录导览（多章节时）与排版正文；
  - `.TXT`：干净无格式干扰的纯文本，适宜快速复制或喂给大模型（LLM）二次提炼；
  - `.SRT`：标准视频外挂字幕文件，方便剪辑软件（剪映、Premiere、Final Cut）导入。
- **带时间轴逐句稿（可选）**：
  - 可在设置中开启“**输出带时间轴的逐句稿**”；
  - 额外生成 `[00:01:23] 逐句内容` 格式的文本对照稿，方便对照音视频精准定位。

### 7. 💼 绿色便携与零 C 盘占用设计
- **相对路径设计**：默认存储于 `./outputs`、`./cache`、`./models`，程序放置在任何盘符或移动硬盘均可直接使用；
- **存储路径自定义**：支持在 Web 界面自由修改输出目录，便于与其他知识库管理工具（如 Obsidian、Logseq、Notion）无缝集成；
- **彻底隔离 C 盘**：启动时自动将 Python 临时目录、Hugging Face 缓存与 PyTorch 缓存重定向至当前项目目录下，绝不暗中吞噬 C 盘系统盘空间。

---

## 🖥️ 界面展示

- **简洁美观的 Web 控制看板**：支持暗色/亮色主题风格卡片、多源输入框、批量状态统计；
- **实时任务列表**：进度百分比、动态呼吸标签（解析中 / 听写中 / 分段排版 / 已完成）；
- **即时操作**：支持直接在线预览 Markdown 内容、一键复制全文、单文件快速下载（.MD / .TXT / .SRT / 逐句稿）、一键打开本地输出文件夹。

---

## 🛠️ 安装与快速启动

### 方式一：Windows 用户一键启动（推荐）

1. 确认本机已安装 **Python 3.10+** 并加入系统环境变量 PATH。
2. 双击运行根目录下的启动脚本：
   ```cmd
   run.bat
   ```
3. 脚本会自动初始化虚拟环境并拉起浏览器打开控制看板：
   👉 **http://127.0.0.1:8765**

---

### 方式二：手动安装运行

#### 1. 克隆代码仓库
```bash
git clone https://github.com/tauyu/videolink-to-text.git
cd videolink-to-text
```

#### 2. 创建并激活虚拟环境
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. 安装依赖包
```bash
pip install -r requirements.txt
```

> **提示（NVIDIA GPU 加速）**：  
> 若您在 Windows 下使用 NVIDIA 独立显卡进行 CUDA 加速，推荐安装 CUDA 12 运行支持库：
> ```bash
> pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-nvrtc-cu12
> ```
> 程序启动时会自动发现并注册上述动态链接库，无需手动配置系统级 CUDA Toolkit。

#### 4. 启动服务
```bash
python main.py
```
终端输出运行地址后，在浏览器访问 `http://127.0.0.1:8765` 即可。

---

## ⚙️ 配置说明

可以通过 Web 界面右上角「**设置**」进行可视化修改，设置项保存在本地 `config.json` 中：

| 配置项 | 默认值 | 作用说明 |
| :--- | :--- | :--- |
| `output_dir` | `./outputs` | 转录结果（.md / .txt / .srt / 逐句稿）的保存目录 |
| `cache_dir` | `./cache` | 临时音视频切片缓存，任务完成后自动清理 |
| `model_dir` | `./models` | Faster-Whisper 模型权重下载与缓存目录 |
| `model_size` | `large-v3-turbo` | 识别模型规格（可选 `tiny` / `base` / `small` / `medium` / `large-v3-turbo`） |
| `device` | `cuda` | 运算设备：`cuda`（N卡硬件加速）或 `cpu` |
| `compute_type` | `float16` | 计算精度：GPU 推荐 `float16`，CPU 推荐 `int8` |
| `export_timeline_transcript` | `false` | 是否额外生成 `[00:01:23] 逐句内容` 格式的时间轴逐句对照稿 |

---

## 📂 项目结构

```
videolink-to-text/
├── run.bat                 # Windows 一键启动脚本 (ASCII 编码，防乱码)
├── main.py                 # 主服务入口 (端口自检、浏览器自动唤起)
├── config.py               # 便携式路径管理与 CUDA DLL 自动发现
├── config.example.json     # 配置模板参考
├── requirements.txt        # 核心依赖清单
├── core/
│   ├── models.py           # Pydantic 数据实体 (Task, Metadata, Chapter, Segment)
│   ├── parser.py           # 音视频元数据与作者章节提取 (yt-dlp / ffprobe)
│   ├── subtitle.py         # 原片 CC 字幕探测与毫秒级时间轴解析
│   ├── audio.py            # 音频无损提取与采样率规范化 (16kHz Mono WAV)
│   ├── asr.py              # Faster-Whisper 推理封装 (带中文标点指引 prompt)
│   ├── segmenter.py        # 语篇标志词探测、中文去空格与智能章节聚类
│   └── exporter.py         # Markdown / TXT / SRT / 时间轴逐句稿生成器
├── queue_manager.py        # 批量异步任务调度管理器与 WebSocket 事件推送
├── web/
│   ├── app.py              # FastAPI 路由、下载接口与 WebSocket 广播
│   └── static/
│       ├── index.html      # 控制看板前端界面
│       └── app.js          # 前端状态机、长连接通信与即时预览交互
├── models/                 # AI 模型权重存储区 (默认本地隔离)
├── cache/                  # 临时缓存区 (任务完成后自动清理)
└── outputs/                # 最终产物存储区 (转录生成的所有文本)
```

---

## 🤝 常见问题 (FAQ)

<details>
<summary><b>Q1: 为什么有些视频几秒钟就转录完了，有些视频需要几分钟？</b></summary>
程序拥有双轨识别机制：如果该视频在平台上有官方或内置字幕，程序会直接秒级抓取字幕文件，几秒钟即可完成；如果视频本身没有字幕，程序才会抽取音轨调用本地 AI 显卡进行逐句语音听写。
</details>

<details>
<summary><b>Q2: 我的设备没有 NVIDIA 显卡可以使用吗？</b></summary>
完全可以。若没有检测到可用 CUDA 设备，程序会自动降级为 CPU 计算（默认采用 int8 量化），依然可以正常完成转录。
</details>

<details>
<summary><b>Q3: 输出的转录文件可以自动同步到我的笔记软件吗？</b></summary>
可以。在 Web 界面点击「设置」，将“结果输出目录”设置为您本地 Obsidian 仓库、Logseq 目录或网盘同步文件夹，每次转录完成的文件就会直接出现在您的笔记库中。
</details>

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。
