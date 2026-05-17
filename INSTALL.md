# 自动化安装指南

## OpenClaw / Hermes / 其他 Agent 框架

### 一键安装命令

```bash
# 方式一：npx 直接运行（推荐，零配置）
npx github:li-neo/seedance2-cli generate --text "一只赛博朋克小猫"

# 方式二：全局安装
npm install -g github:li-neo/seedance2-cli
seedance generate --text "一只赛博朋克小猫"

# 方式三：自动化安装脚本（带完整日志输出）
curl -fsSL https://raw.githubusercontent.com/li-neo/seedance2-cli/main/install.js | node
```

### Agent 框架集成

#### OpenClaw 集成

在 OpenClaw 的 skill 配置中：

```yaml
skills:
  - name: seedance2-cli
    install: |
      npm install -g github:li-neo/seedance2-cli
    env:
      - VOLC_ACCESS_KEY
      - VOLC_SECRET_KEY
      - VOLC_ARK_API_KEY
      - VOLC_ARK_SEEDANCE_MODEL
```

#### Hermes 集成

在 Hermes 的 tool 定义中：

```json
{
  "name": "seedance_video_generate",
  "install_command": "npm install -g github:li-neo/seedance2-cli",
  "command": "seedance generate --text {text} --download",
  "env_vars": [
    "VOLC_ACCESS_KEY",
    "VOLC_SECRET_KEY",
    "VOLC_ARK_API_KEY",
    "VOLC_ARK_SEEDANCE_MODEL"
  ]
}
```

### 环境变量要求

安装前必须配置以下环境变量：

```bash
# AK/SK (用于 TOS/Assets 鉴权)
export VOLC_ACCESS_KEY="xxxx"
export VOLC_SECRET_KEY="xxxxxx=="

# Assets 参数 (私域素材库)
export VOLC_ASSETS_HOST="ark.cn-beijing.volcengineapi.com"
export VOLC_ASSETS_REGION="cn-beijing"
export VOLC_ASSETS_SERVICE="ark"
export VOLC_ASSETS_VERSION="2024-01-01"
export VOLC_ASSETS_GROUP="seedance-pipeline-group"
export VOLC_ASSETS_PROJECT="default"

# TOS 参数 (对象存储)
export VOLC_TOS_REGION="cn-beijing"
export VOLC_TOS_ENDPOINT="tos-cn-beijing.volces.com"
export VOLC_TOS_BUCKET="xxx"

# Ark API (模型推理服务)
export VOLC_ARK_API_URL="https://ark.cn-beijing.volces.com/api/v3"
export VOLC_ARK_API_KEY="xxxxxx"
export VOLC_ARK_SEEDANCE_MODEL="doubao-seedance-2-0-pro-260215"
```

### 自动化安装特性

- **零交互**: 无需用户确认，自动完成所有步骤
- **依赖检测**: 自动检测 Node.js 和 Python3 环境
- **虚拟环境支持**: 设置 `SEEDANCE_USE_VENV=1` 可使用虚拟环境隔离
- **JSON 日志输出**: 便于 Agent 框架解析安装状态
- **非零退出码**: 安装失败时返回错误码，便于自动化流程判断

### 安装后验证

```bash
seedance --version
# 应输出: 1.0.0

seedance --help
# 应显示所有可用命令
```
