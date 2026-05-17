# seedance2-cli 接入指南

| 版本 | 更新时间 | 更新内容 | 作者 |
|------|----------|----------|------|
| 2.0.0 | 2026-05-17 | 重构为标准 CLI 工具，支持 npx/GitHub 安装 | @li-neo |
| 1.0.0 | 2026-05-11 | 初稿 | @许建华 |

---

## 引言

`seedance2-cli` 是一套标准化的 Seedance 2.0 视频生成命令行工具。它将端到端的视频生成过程封装为统一的 CLI 入口，支持多模式自动识别、本地素材自动上云、合规兜底重试等完整流水线。

**核心目标：**

- **一键安装运行**：通过 `npx` 或 `npm install` 即可使用，零配置门槛
- **智能流水线**：自动识别生成模式、自动上传素材、自动合规兜底
- **原子化工具链**：各功能模块可独立调用，灵活组合

---

## 快速上手

### 安装

**方式一：npx 直接运行（推荐，无需安装）**

```bash
npx github:li-neo/seedance2-cli generate --text "一只赛博朋克小猫"
```

**方式二：全局安装**

```bash
npm install -g github:li-neo/seedance2-cli
seedance generate --text "一只赛博朋克小猫"
```

**方式三：克隆源码**

```bash
git clone https://github.com/li-neo/seedance2-cli.git
cd seedance2-cli
npm install
npx seedance generate --text "一只赛博朋克小猫"
```

> 安装时会自动检测 Node.js 和 Python3 环境，并创建虚拟环境安装 Python 依赖。

---

### 环境变量配置

首次运行前需配置火山引擎相关环境变量：

#### 国内环境

```bash
# AK/SK
export VOLC_ACCESS_KEY="YOUR_ACCESS_KEY"
export VOLC_SECRET_KEY="YOUR_SECRET_KEY"

# Ark API
export VOLC_ARK_API_URL="https://ark.cn-beijing.volces.com/api/v3"
export VOLC_ARK_API_KEY="YOUR_ARK_API_KEY"
export VOLC_ARK_SEEDANCE_MODEL="doubao-seedance-2-0-pro-260215"
export VOLC_ARK_LLM_MODEL="doubao-pro-32k"
export VOLC_ARK_VLM_MODEL="doubao-pro-32k"

# TOS
export VOLC_TOS_REGION="cn-beijing"
export VOLC_TOS_ENDPOINT="tos-cn-beijing.volces.com"
export VOLC_TOS_BUCKET="your-bucket"

# Assets
export VOLC_ASSETS_HOST="ark.cn-beijing.volcengineapi.com"
export VOLC_ASSETS_REGION="cn-beijing"
export VOLC_ASSETS_SERVICE="ark"
export VOLC_ASSETS_VERSION="2024-01-01"
export VOLC_ASSETS_GROUP="seedance-pipeline-group"
export VOLC_ASSETS_PROJECT="default"
```

#### 海外 BytePlus 环境

```bash
export VOLC_ACCESS_KEY="YOUR_ACCESS_KEY"
export VOLC_SECRET_KEY="YOUR_SECRET_KEY"

export VOLC_ARK_API_URL="https://ark.ap-southeast-1.byteplusapi.com/api/v3"
export VOLC_ARK_API_KEY="YOUR_ARK_API_KEY"
export VOLC_ARK_SEEDANCE_MODEL="dreamina-seedance-2-0-260128"

export VOLC_TOS_REGION="ap-southeast-1"
export VOLC_TOS_ENDPOINT="tos-ap-southeast-1.bytepluses.com"
export VOLC_TOS_BUCKET="your-bucket"

export VOLC_ASSETS_HOST="ark.ap-southeast-1.byteplusapi.com"
export VOLC_ASSETS_REGION="ap-southeast-1"
export VOLC_ASSETS_SERVICE="ark"
export VOLC_ASSETS_VERSION="2024-01-01"
```

---

## CLI 命令体系

```
seedance <command> [options]
```

| 命令 | 说明 |
|------|------|
| `generate` | **核心命令**：一键生成视频（自动模式识别 + TOS + Assets 兜底） |
| `seedance` | 直接调用 Seedance API（需手动指定 `--mode`） |
| `tos` | TOS 文件上传工具 |
| `assets` | Assets 素材库工具 |
| `llm` | LLM 文本生成工具 |
| `vlm` | VLM 多模态理解工具 |
| `download` | 文件下载工具 |

---

## 命令详解

### generate — 一键视频生成

自动识别输入素材组合，选择最优生成模式，自动处理本地文件上传和合规兜底。

```bash
seedance generate \
  --text "一只可爱的赛博朋克风格小猫在下雨的霓虹街道上奔跑" \
  --resolution "1080p" \
  --download \
  --output-path "./outputs/cyber_cat.mp4"
```

**参数说明：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--text` | 提示词文本 | - |
| `--first-frame` | 首帧图片路径/URL | - |
| `--last-frame` | 尾帧图片路径/URL | - |
| `--reference-image` | 参考图片（可多次指定） | - |
| `--reference-video` | 参考视频（可多次指定） | - |
| `--reference-audio` | 参考音频（可多次指定） | - |
| `--duration` | 视频时长（4~15 秒） | 15 |
| `--ratio` | 宽高比 | 9:16 |
| `--resolution` | 分辨率（480p/720p/1080p） | 720p |
| `--generate-audio` | 是否生成音频 | true |
| `--seed` | 随机种子 | -1 |
| `--download` | 完成后自动下载 | false |
| `--output-path` | 下载保存路径 | - |

**自动模式识别：**

| 输入特征 | 自动判定模式 |
|----------|-------------|
| 仅文本 | `t2v` |
| 1 张图片 | `i2v` |
| 2 张图片 | `fl2v` |
| 视频/音频/多图组合 | `multimodal_ref2v` |

---

### seedance — 底层 API 调用

直接调用 Seedance API，需手动指定模式。适用于调试和特定场景。

```bash
seedance seedance \
  --mode multimodal_ref2v \
  --text "请将人物风格转换为赛博朋克场景" \
  --reference-image "https://example.com/character.png" \
  --reference-image "https://example.com/scene.png"
```

---

### tos — 文件上传

将本地文件上传至 TOS，返回签名 URL。

```bash
# 上传单个文件
seedance tos --files "/path/to/video.mp4"

# 上传多个文件（JSON 输出）
seedance tos --files "image1.jpg" "image2.png" --json
```

**特性：**

- 基于 MD5 内容寻址，相同文件自动秒传
- 默认 URL 有效期 24 小时

---

### assets — 素材库管理

将 URL 入库到私域素材库，获取 `asset://` ID。

```bash
seedance assets \
  --urls "https://your-bucket.tos-cn-beijing.volces.com/xxx" \
  --group "seedance-pipeline-group"
```

> 通常无需手动调用，`generate` 命令会在合规触发时自动兜底。

---

### llm — 文本生成

调用大语言模型润色提示词、扩写脚本。

```bash
seedance llm \
  --system-file "./prompts/seedance-2.0-director.md" \
  --text "用户原始意图：做一个女孩在海边走路的视频，伤感一点"
```

---

### vlm — 多模态理解

分析图片/视频内容，生成描述文本。

```bash
seedance vlm \
  --media "./reference_scene.jpg" \
  --text "请详细描述这幅画面的构图、光影、色调和风格"
```

---

### download — 文件下载

从 URL 下载文件到本地。

```bash
seedance download \
  "https://some-video-url/generated_video.mp4" \
  --output "./final_video.mp4"
```

---

## 典型工作流

### 工作流一：文生视频（最简单）

```bash
seedance generate \
  --text "一只可爱的赛博朋克风格小猫在下雨的霓虹街道上奔跑" \
  --resolution "1080p" \
  --download
```

### 工作流二：首尾帧生视频

```bash
seedance generate \
  --first-frame "/path/to/start.png" \
  --last-frame "https://example.com/end.png" \
  --text "画面从白天渐变到黑夜" \
  --duration 10
```

### 工作流三：多模态参考（视频续写）

```bash
seedance generate \
  --reference-video "https://example.com/source.mp4" \
  --reference-image "https://example.com/style.png" \
  --text "请在参考视频基础上续写，保持人物风格一致"
```

### 工作流四：AI 导演助手润色

```bash
# Step 1: 使用 LLM 润色提示词
seedance llm \
  --system-file "./prompts/seedance-2.0-director.md" \
  --text "一个女孩在雨天分手，很难过" > polished_prompt.txt

# Step 2: 使用润色后的提示词生成视频
seedance generate \
  --text "$(cat polished_prompt.txt)" \
  --reference-image "./girl_photo.jpg" \
  --reference-audio "./sad_piano.mp3" \
  --download
```

---

## 提示词工程

### 核心心法

- **U 型注意力**：模型重点关注提示词开头和结尾
- **八大要素**：精准主体 + 动作细节 + 场景环境 + 光影色调 + 镜头运镜 + 视觉风格 + 画质参数 + 约束条件

### 结构化模板

```markdown
# 整体设定
@图片1 用于锁定主角面部, @图片2 用于设定场景氛围。

# 分镜时序
镜头1 (0-5秒): [景别] [主体] [动作], [场景细节], [光影描述]。
镜头2 (5-10秒): [景别] [主体] [动作], [场景细节], [光影描述]。

# 风格与约束
电影质感, 复古胶片风格。4K超高清, 细节丰富。
面部稳定不变形, 动作自然流畅, 无闪烁, 无文字。
```

### 素材序号规则

- `--reference-image` 按顺序对应 `@图片1`, `@图片2`...
- `--reference-video` 按顺序对应 `@视频1`, `@视频2`...
- `--reference-audio` 按顺序对应 `@音频1`, `@音频2`...

---

## 最佳实践

- [✓] **始终使用 `generate`**：除非底层调试，否则用 `generate` 作为唯一入口
- [✓] **混合本地与远程素材**：本地文件会自动上传，URL 会直接透传
- [✓] **利用 AI 导演助手**：用 `llm` + `seedance-2.0-director.md` 润色提示词
- [✓] **合规自动兜底**：人物肖像素材触发风控时，`generate` 会自动 Assets 重试
- [✗] **避免手动指定模式**：`generate` 会自动识别，无需 `--mode`
- [✗] **避免用 `seedance` 处理本地文件**：底层 API 不自动上传

---

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| 缺少环境变量 | 运行命令后会一次性提示所有缺失变量，复制配置模板填写即可 |
| Python 依赖安装失败 | 设置 `SEEDANCE_USE_VENV=1` 强制使用虚拟环境 |
| 人脸/肖像合规错误 | `generate` 会自动 Assets 兜底重试，无需手动处理 |
| TOS 上传失败 | 检查 `VOLC_ACCESS_KEY` / `VOLC_SECRET_KEY` 是否正确 |

---

## 项目信息

- **仓库**: https://github.com/li-neo/seedance2-cli
- **安装**: `npm install -g github:li-neo/seedance2-cli`
- **直接运行**: `npx github:li-neo/seedance2-cli <command>`
