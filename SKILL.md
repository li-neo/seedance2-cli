---
name: "seedance2-cli"
description: "端到端生成 Seedance-2 视频。能根据图片、视频、音频等多种输入自动识别生成模式，并通过参数校验与合规兜底等护栏提升输出稳定性与可复现性。"
---

# seedance2-cli

## 1. 目标

这是一个一键生成 Seedance 2.0 视频的完整 Skill。
它能根据用户输入的素材**智能识别视频生成模式**，并通过内置的稳定性护栏和错误处理机制，**提升生成成功率与效果的可复现性**。

核心能力包括：
- **多模式自动识别**：根据输入的图片、视频、音频组合，自动选择最合适的生成模式（文生视频、图生视频、视频续写/编辑等，通过 `multimodal_ref2v` 支持多模态参考续写）。
- **全自动素材上云**：无缝处理本地文件，自动上传至云存储 (TOS)，用户无需手动操作。
- **合规流程自动化**：当遇到人脸/肖像等合规限制时，自动将素材转存至私域素材库 (Assets) 并重试，最大化提升成功率。
- **稳定性与可复现性护栏**：内置参数安全校验与随机种子控制等策略，让你的每次创作都有更可预期的结果。

## 2. 核心约束 (必须遵守)

- **保留完整参数**：若用户输入的是素材 URL，必须保留并透传完整 URL（包含 `?x=a&y=b` 等全部 query 参数），不得截断或丢失。
- **回传视频要求**：视频生成完毕后，必须同时向用户发送：
  1. 视频文件本体（作为附件/文件流发送，可使用 `--download` 自动下载至本地后发送）。
  2. 视频文件的完整下载地址（包含 `?x=a&y=b` 等全部 query 参数）。
- 必须实时输出处理过程：流水线各步骤的进度、素材上传、接口请求与兜底重试等信息须以行缓冲/直写方式即时输出（stderr/stdout），便于用户观察执行状态与问题定位。

---

## 3. 快速开始

### 3.1. 安装 CLI 工具

**方式一：通过 GitHub 直接运行（无需安装，推荐）**

```bash
npx github:li-neo/seedance2-cli generate --text "一只可爱的赛博朋克风格小猫在下雨的霓虹街道上奔跑"
```

**方式二：全局安装（从 GitHub）**

```bash
npm install -g github:li-neo/seedance2-cli
seedance generate --text "一只可爱的赛博朋克风格小猫在下雨的霓虹街道上奔跑"
```

**方式三：克隆后本地运行**

```bash
git clone https://github.com/li-neo/seedance2-cli.git
cd seedance2-cli
npm install
npx seedance generate --text "..."
```

### 3.2. 配置环境变量

在执行脚本之前，必须配置所有相关的环境变量。如果缺失，脚本在启动时会**一次性**报出所有缺失的变量并退出。你可以直接复制国内或 BytePlus 的环境配置模板进行设置（具体值需替换）。

#### 国内环境配置示例

```bash
# AK/SK (用于 TOS/Assets 鉴权)
# 获取文档: https://www.volcengine.com/docs/6291/65568?lang=zh
export VOLC_ACCESS_KEY="xxxx"
export VOLC_SECRET_KEY="xxxxxx=="

# Assets 参数 (私域素材库)
# 接口文档: https://www.volcengine.com/docs/82379/2333565?lang=zh
export VOLC_ASSETS_HOST="ark.cn-beijing.volcengineapi.com"
export VOLC_ASSETS_REGION="cn-beijing"
export VOLC_ASSETS_SERVICE="ark"
export VOLC_ASSETS_VERSION="2024-01-01"
export VOLC_ASSETS_GROUP="seedance-pipeline-group"
export VOLC_ASSETS_PROJECT="default"

# TOS 参数 (对象存储)
# 获取文档: https://www.volcengine.com/docs/6349/107356?lang=zh
export VOLC_TOS_REGION="cn-beijing"
export VOLC_TOS_ENDPOINT="tos-cn-beijing.volces.com"
export VOLC_TOS_BUCKET="xxx"

# Ark API (模型推理服务)
# 获取文档: https://www.volcengine.com/docs/82379/1399008?lang=zh#f97e77a7
export VOLC_ARK_API_URL="https://ark.cn-beijing.volces.com/api/v3"
export VOLC_ARK_API_KEY="xxxxxx"
export VOLC_ARK_SEEDANCE_MODEL="doubao-seedance-2-0-pro-260215"
```

#### BytePlus 环境配置示例

```bash
# AK/SK ENV
export VOLC_ACCESS_KEY="xxxx"
export VOLC_SECRET_KEY="xxxxxxx=="

# ASSETS ENV
export VOLC_ASSETS_HOST="ark.ap-southeast-1.byteplusapi.com"
export VOLC_ASSETS_REGION="ap-southeast-1"
export VOLC_ASSETS_SERVICE="ark"
export VOLC_ASSETS_VERSION="2024-01-01"
export VOLC_ASSETS_GROUP="seedance-pipeline-group"
export VOLC_ASSETS_PROJECT="default"

# TOS ENV
export VOLC_TOS_REGION="ap-southeast-1"
export VOLC_TOS_ENDPOINT="tos-ap-southeast-1.bytepluses.com"
export VOLC_TOS_BUCKET="xxx"

# ARK
export VOLC_ARK_API_URL="https://ark.ap-southeast-1.byteplusapi.com/api/v3"
export VOLC_ARK_API_KEY="xxxxx"
export VOLC_ARK_SEEDANCE_MODEL="dreamina-seedance-2-0-260128"
```

---

## 4. 执行流程与核心逻辑

`seedance generate`（底层调用 `scripts/pipeline.py`）会自动执行以下智能编排流程：
所有日志均为实时输出（行缓冲），不延迟。

1.  **参数校验与护栏**：首先通过 `scripts/validate_and_normalize.py` 对输入参数进行标准化，应用安全范围裁剪和随机种子控制等策略。
2.  **多模式自动识别**：调用 `scripts/select_mode.py`，根据你的输入（文本、图片、视频等）智能决策采用哪种生成模式。
3.  **本地文件自动上云 (TOS)**：自动识别所有本地文件路径，通过 `scripts/tos_cli.py` 将其上传至对象存储，并替换为有时效的签名 URL。
4.  **发起首次生成**：使用处理好的参数和素材 URL，调用 `scripts/seedance_cli.py` 首次尝试生成视频。
5.  **人脸/肖像合规自动兜底 (Assets)**：如果首次生成因人脸合规问题失败，脚本会自动捕获该错误，调用 `scripts/assets_cli.py` 将所有相关素材上传至私域素材库，并使用获得的 `asset://` ID **自动发起第二次生成**。
6.  **结果输出与下载**：任务成功后，在控制台打印生成的视频 URL。如果使用了 `--download` 参数，视频文件将自动下载到本地。

---

## 5. CLI 命令体系

安装后，使用 `seedance <command>` 调用各功能：

| 命令 | 说明 |
|------|------|
| `seedance generate` | **核心命令**：一键生成视频（自动模式识别 + TOS + Assets 兜底） |
| `seedance seedance` | 直接调用 Seedance API（需手动指定 `--mode`） |
| `seedance tos` | TOS 文件上传工具 |
| `seedance assets` | Assets 素材库工具 |
| `seedance llm` | LLM 文本生成工具 |
| `seedance vlm` | VLM 多模态理解工具 |
| `seedance download` | 文件下载工具 |

所有命令均支持 `--help` 查看详细参数。

---

## 6. 多模式自动识别

脚本会根据你传入的参数，自动推断最合适的 Seedance 2.0 工作模式。

| 核心场景 | 输入特征 | 自动判定的模式 |
| :--- | :--- | :--- |
| **文生视频** | 只提供了文本 (`--text`) | `t2v` |
| **图生视频 (单帧)**| 只提供了 1 张参考图 | `i2v` |
| **图生视频 (首尾帧)**| 提供了 2 张参考图 | `fl2v` |
| **视频 + 文本（续写/编辑）** | 提供了参考视频 + 文本提示 | `multimodal_ref2v`（视频续写/编辑） |
| **视频续写/编辑** | 只提供了 1 个参考视频 | `multimodal_ref2v` |
| **多模态参考** | 提供了图片、视频、音频的任意组合 | `multimodal_ref2v` |

特别说明：视频+文本为"续写/编辑"，不等同于"换脸/换角色"。如需更强的人物控制，建议同时提供参考图片。

> 📚 **想了解更多细节？**
>
> - 完整的模式映射规则、优先级和回退策略，请查阅 [**模式映射与自动识别 (`references/mode-mapping.md`)**](./references/mode-mapping.md)。
> - 关于脚本如何处理典型的错误（如素材合规、参数超范围），请查阅 [**典型错误与自动处理 (`references/error-cases.md`)**](./references/error-cases.md)。

---

## 7. 稳定性与参数护栏

为了提升生成效果的稳定性和可复现性，我们引入了一系列参数护栏。

- **随机种子控制**：默认情况下，`--seed` 为 `-1`，由服务端自行采样随机种子；如需确定性结果，请在 CLI 中显式设置具体整数值（例如 `--seed 42`），以便在多次执行中复现相同结果。
- **参数安全范围**: 对于 `--duration` 等关键参数，脚本会进行范围校验，将超出安全范围的值自动裁剪到合理边界，避免任务因无效参数而失败。

> 📚 **想了解更多细节？**
>
> - 所有参数的安全边界与默认值说明，请查阅 [**参数安全与稳定性护栏 (`references/parameter-safety.md`)**](./references/parameter-safety.md)。

---

## 8. 使用示例

所有 CLI 参数均对齐了 Seedance 2.0 API 官方文档，并在此基础上提供少量易用性的补充参数（如 `--download`、`--output-path` 等）。

### 示例 1：文生视频（高质量配置示例）

```bash
seedance generate \
  --text "一只可爱的赛博朋克风格小猫在下雨的霓虹街道上奔跑"
```
*该示例仅包含必要参数，其余均采用默认配置*

### 示例 2：首尾帧生视频（混合本地文件与 URL）

```bash
seedance generate \
  --first-frame "https://example.com/start.png" \
  --last-frame "https://example.com/end.png" \
  --text "画面从白天渐变到黑夜"
```

### 示例 3：多模态参考视频（视频续写/编辑）

在参考视频基础上进行续写或编辑（仅使用必要参数，其他默认）。

```bash
seedance generate \
  --reference-video "https://example.com/source.mp4" \
  --text "请在参考视频的基础上进行续写或编辑"
```

### 关键参数说明

- `--text`：提示词文本，默认不填写（仅文本驱动场景下推荐必填）。
- `--first-frame`：首帧图片路径/URL/素材 ID，默认不使用首帧约束。
- `--last-frame`：尾帧图片路径/URL/素材 ID，默认不使用尾帧约束。
- `--reference-image`：参考图片路径/URL/素材 ID，可多次指定；默认不提供参考图片。
- `--reference-video`：参考视频路径/URL/素材 ID，可多次指定；默认不提供参考视频。
- `--reference-audio`：参考音频路径/URL/素材 ID，可多次指定；默认不提供参考音频。
- `--duration`：视频时长（秒），支持 4–15 或 `-1`（模型智能选择），默认 `15`。
- `--ratio`：视频宽高比，默认 `9:16`，可选 `16:9`、`4:3`、`1:1`、`3:4`、`9:16`、`21:9`、`adaptive`。
- `--resolution`：输出分辨率，默认 `720p`，可选 `480p`、`720p`、`1080p`。
- `--generate-audio`：是否生成音频，默认开启；如需关闭可显式传入 `--no-generate-audio`。
- `--return-last-frame`：是否同时返回生成视频的尾帧图像，默认关闭。
- `--watermark`：是否在视频中添加水印，默认不添加。
- `--seed`：随机种子整数，默认 `-1`；`--seed=-1` 时由服务端自行采样随机种子，如需确定性结果请显式设置具体整数值。
- `--safety-identifier`：终端用户的唯一标识符，默认不传，由服务端按默认策略处理。
- `--web-search`：是否开启联网搜索工具，默认关闭；如设置 `SEEDANCE_DISABLE_WEB_SEARCH=1` 则会被强制关闭。
- `--download`：任务完成后是否自动下载生成视频到本地，默认不下载。
- `--output-path`：配合 `--download` 指定保存路径，默认使用脚本内置路径（如 `scripts/runtime/` 目录）。

可通过 `seedance generate --help` 查看完整参数列表。

---

## 9. 安装后引导流程

安装 Skill 后，推荐按照以下顺序引导用户完成环境配置和首个示例的执行：

1. **安装完成后立即发送环境配置命令模板。**
   - 将「3.2. 配置环境变量」中的 `国内环境配置示例` 与 `BytePlus 环境配置示例` 两段命令原样发送给用户，确保两套命令与本章节保持同步更新。
   - 明确提示：**"请将以下命令复制粘贴到会话，替换敏感信息（AK/SK、Bucket、API key、Model 等）后发回给我进行校验。"**

2. **根据用户粘贴回来的命令进行校验。**
   - 检查是否包含本 Skill 所需的全部环境变量：`VOLC_ACCESS_KEY`、`VOLC_SECRET_KEY`、所有 `VOLC_ASSETS_*`（含 `VOLC_ASSETS_GROUP` 与 `VOLC_ASSETS_PROJECT`）、所有 `VOLC_TOS_*`、`VOLC_ARK_API_URL`、`VOLC_ARK_API_KEY`、`VOLC_ARK_SEEDANCE_MODEL`。
   - 如发现遗漏或拼写错误，在会话中直接指出问题项并给出修正示例；仅在命令完整且字段正确时再继续执行示例命令。

3. **确认环境就绪后再运行示例。**
   - 在确认用户侧环境配置无误后，引导其在本地终端执行依赖安装命令和示例 CLI（例如「8. 使用示例」中的文生视频或视频续写/编辑示例）。
   - 当运行 `scripts/pipeline.py` 时，如仍存在环境缺失，`check_and_guide_envs` 会在日志中自动输出同样的两套完整配置命令，供用户再次复制粘贴并修正。

4. **关于随机种子配置的提醒。**
   - 本 Skill 不需要也不支持通过任何环境变量配置随机种子；不要要求用户设置 `SEEDANCE_SEED_MODE`、`SEEDANCE_DEFAULT_SEED` 等 seed 相关环境变量。
   - 若希望获得确定性结果，仅需在 CLI 调用中显式传入 `--seed <整数>`（例如 `--seed 42`）；保留默认值 `--seed=-1` 时，由服务端自行采样随机种子。
