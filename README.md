# seedance2-cli

seedance2-cli - Seedance-2 视频生成 CLI 工具集。一键生成视频，支持多模式自动识别、TOS 上传、Assets 兜底等完整流水线。

## 安装

**通过 GitHub 直接运行（无需安装）**

```bash
npx github:li-neo/seedance2-cli generate --text "一只赛博朋克小猫"
```

**全局安装**

```bash
npm install -g github:li-neo/seedance2-cli
seedance generate --text "一只赛博朋克小猫"
```

**克隆后本地运行**

```bash
git clone https://github.com/li-neo/seedance2-cli.git
cd seedance2-cli
npm install
npx seedance generate --text "一只赛博朋克小猫"
```

## 配置环境变量

首次运行前需配置火山引擎相关环境变量：

```bash
export VOLC_ACCESS_KEY="xxxx"
export VOLC_SECRET_KEY="xxxxxx=="
export VOLC_ASSETS_HOST="ark.cn-beijing.volcengineapi.com"
export VOLC_ASSETS_REGION="cn-beijing"
export VOLC_ASSETS_SERVICE="ark"
export VOLC_ASSETS_VERSION="2024-01-01"
export VOLC_ASSETS_GROUP="seedance-pipeline-group"
export VOLC_ASSETS_PROJECT="default"
export VOLC_TOS_REGION="cn-beijing"
export VOLC_TOS_ENDPOINT="tos-cn-beijing.volces.com"
export VOLC_TOS_BUCKET="xxx"
export VOLC_ARK_API_URL="https://ark.cn-beijing.volces.com/api/v3"
export VOLC_ARK_API_KEY="xxxxxx"
export VOLC_ARK_SEEDANCE_MODEL="doubao-seedance-2-0-pro-260215"
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `seedance generate` | 一键生成视频（自动模式识别 + TOS + Assets 兜底） |
| `seedance seedance` | 直接调用 Seedance API |
| `seedance tos` | TOS 文件上传工具 |
| `seedance assets` | Assets 素材库工具 |
| `seedance llm` | LLM 文本生成工具 |
| `seedance vlm` | VLM 多模态理解工具 |
| `seedance download` | 文件下载工具 |

## 使用示例

```bash
# 文生视频
seedance generate --text "一只可爱的赛博朋克风格小猫在下雨的霓虹街道上奔跑"

# 首尾帧生视频
seedance generate \
  --first-frame "https://example.com/start.png" \
  --last-frame "https://example.com/end.png" \
  --text "画面从白天渐变到黑夜"

# 视频续写/编辑
seedance generate \
  --reference-video "https://example.com/source.mp4" \
  --text "请在参考视频的基础上进行续写或编辑"
```

## 项目结构

```
seedance2-cli/
├── bin/seedance.js          # CLI 统一入口
├── index.js                 # 模块入口
├── package.json             # npm 配置
├── scripts/                 # Python 核心脚本
│   ├── pipeline.py          # 主流水线
│   ├── seedance_cli.py      # Seedance API 调用
│   ├── tos_cli.py           # TOS 上传
│   ├── assets_cli.py        # Assets 素材库
│   ├── llm_cli.py           # LLM 文本生成
│   ├── vlm_cli.py           # VLM 多模态理解
│   ├── download_cli.py      # 文件下载
│   └── postinstall.js       # 自动安装 Python 依赖
├── prompts/                 # 提示词模板
├── references/              # 参考文档
├── SKILL.md                 # Skill 定义文档
└── requirements.txt         # Python 依赖
```

## License

MIT
