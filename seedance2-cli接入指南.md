版本
更新时间
更新内容
作者
1.0.0
2026-05-11
初稿
@许建华 
引言
本指南为你提供一套以命令行工具（CLI）为核心的 Seedance 2.0 标准化接入与使用方法。
我们的核心目标是：
- 提升工程化效率：通过标准化的 CLI 工具链与可编排的工作流，将视频生成过程从“创意发散”收敛为“工程实现”，大幅提升交付效率与质量稳定性。
- 赋能高质量内容产出：掌握面向 CLI 的提示词工程、多模态素材协同与自动化兜底策略，创作出具有专业质感和商业价值的高质量视频。
核心工作流概览
我们已将 Seedance 2.0 的端到端视频生成过程封装为一系列独立的 SKILL （CLI） 工具，并通过 pipeline.py 实现智能编排。下图清晰地展示了从素材准备到最终视频产出的完整工作流。
SKILL 包：
暂时无法在飞书文档外展示此内容
暂时无法在飞书文档外展示此内容
SKILL 版演示：

该工作流的核心思想是“分而治之，自动编排”：
1. 准备与创作分离：业务侧同学专注于准备高质量的素材和符合业务逻辑的提示词初稿。
2. AI 辅助提效：利用 llm_cli.py 和 vlm_cli.py 辅助润色提示词、理解素材内容，提升创作质量。
3. 自动化流水线：通过 pipeline.py 一键执行后续所有技术步骤，包括自动上传素材、自动判断生成模式、API 调用、合规风险兜底等，开发者无需关心底层细节。
4. 下载与交付：流水线最终产出视频的下载地址，并可通过 download_cli.py 自动下载到本地，完成交付闭环。
快速上手：环境与配置
在开始使用 CLI 工具链之前，请确保你的开发环境已正确配置。
依赖安装
所有工具的 Python 依赖项均已在 requirements.txt 文件中列出。请在终端执行以下命令完成安装：
pip install -r seedance-2-video-generation/requirements.txt
环境变量配置
CLI 工具链通过环境变量获取火山引擎服务的访问凭证与配置信息。请在执行任何脚本前，确保以下环境变量已正确设置。
最佳实践：建议将以下配置保存为 .env 文件或直接添加到你的 Shell 配置文件（如 .zshrc 或 .bash_profile）中，以便长期使用。
国内环境配置模板
# AK/SK (用于 TOS/Assets/Ark API 鉴权)
# 获取文档: https://www.volcengine.com/docs/6291/65568
export VOLC_ACCESS_KEY="YOUR_ACCESS_KEY"
export VOLC_SECRET_KEY="YOUR_SECRET_KEY"

# Ark API (模型推理服务)
# API Key 获取: https://www.volcengine.com/docs/82379/1399008
# 模型列表: https://www.volcengine.com/docs/82379/2222480
export VOLC_ARK_API_URL="https://ark.cn-beijing.volces.com/api/v3"
export VOLC_ARK_API_KEY="YOUR_ARK_API_KEY"
export VOLC_ARK_SEEDANCE_MODEL="doubao-seedance-2-0-pro-260215"
export VOLC_ARK_LLM_MODEL="doubao-pro-32k"
export VOLC_ARK_VLM_MODEL="doubao-pro-32k"

# TOS (对象存储服务)
# 使用文档: https://www.volcengine.com/docs/6349/107356
export VOLC_TOS_REGION="cn-beijing"
export VOLC_TOS_ENDPOINT="tos-cn-beijing.volces.com"
export VOLC_TOS_BUCKET="your-tos-bucket-name"

# Assets (私域素材库)
# 使用文档: https://www.volcengine.com/docs/82379/2333565
export VOLC_ASSETS_HOST="ark.cn-beijing.volcengineapi.com"
export VOLC_ASSETS_REGION="cn-beijing"
export VOLC_ASSETS_SERVICE="ark"
export VOLC_ASSETS_VERSION="2024-01-01"

海外 BytePlus 环境配置模板
# AK/SK ENV
export VOLC_ACCESS_KEY="YOUR_ACCESS_KEY"
export VOLC_SECRET_KEY="YOUR_SECRET_KEY"

# ARK API
export VOLC_ARK_API_URL="https://ark.ap-southeast-1.byteplusapi.com/api/v3"
export VOLC_ARK_API_KEY="YOUR_ARK_API_KEY"
export VOLC_ARK_SEEDANCE_MODEL="dreamina-seedance-2-0-260128"
export VOLC_ARK_LLM_MODEL="seed-2-0-pro-260328"
export VOLC_ARK_VLM_MODEL="seed-2-0-pro-260328"

# TOS ENV
export VOLC_TOS_REGION="ap-southeast-1"
export VOLC_TOS_ENDPOINT="tos-ap-southeast-1.bytepluses.com"
export VOLC_TOS_BUCKET="your-tos-bucket-name"

# ASSETS ENV
export VOLC_ASSETS_HOST="ark.ap-southeast-1.byteplusapi.com"
export VOLC_ASSETS_REGION="ap-southeast-1"
export VOLC_ASSETS_SERVICE="ark"
export VOLC_ASSETS_VERSION="2024-01-01"

CLI 工具链详解
Seedance 2.0 CLI 工具链由一系列独立的 Python 脚本构成，每个脚本负责一项原子化的任务。这种设计使得你可以灵活地将它们组合、编排，以适应不同的业务场景。
pipeline.py：一键式视频生成流水线
这是我们最推荐的入口工具，它封装了从素材处理到视频生成的完整逻辑，实现了“一键启动，全程托管”。
- 核心作用：作为总调度器，自动编排 tos_cli.py、assets_cli.py、seedance_cli.py 等子工具，完成端到端的视频生成任务。
- 适用场景：所有标准的视频生成需求，尤其是当输入包含本地文件或需要合规兜底时。
命令用法
pipeline.py 会根据你传入的参数自动推断应使用的 Seedance 2.0 工作模式（t2v, i2v, fl2v, multimodal_ref2v），因此你只需关注业务素材本身，无需关心底层模式切换。
$ python seedance-2-video-generation/seedance-2-video-generation/scripts/pipeline.py --help
usage: pipeline.py [-h] [--text TEXT] [--first-frame FIRST_FRAME] [--last-frame LAST_FRAME] [--reference-image REFERENCE_IMAGE]
                   [--reference-video REFERENCE_VIDEO] [--reference-audio REFERENCE_AUDIO] [--duration DURATION]
                   [--ratio {16:9,4:3,1:1,3:4,9:16,21:9,adaptive}] [--resolution {480p,720p,1080p}]
                   [--generate-audio | --no-generate-audio] [--return-last-frame] [--watermark] [--seed SEED]
                   [--safety-identifier SAFETY_IDENTIFIER] [--web-search] [--download] [--output-path OUTPUT_PATH]

Seedance-2 视频生成一键流水线 (自动 Mode, 自动 TOS, 自动 Assets 兜底)

options:
  -h, --help            show this help message and exit
  --text TEXT           输入的提示词文本（t2v 模式必填，其他可选）
  --first-frame FIRST_FRAME
                        首帧图片路径 / URL / 素材 ID
  --last-frame LAST_FRAME
                        尾帧图片路径 / URL / 素材 ID
  --reference-image REFERENCE_IMAGE
                        参考图片路径 / URL / 素材 ID
  --reference-video REFERENCE_VIDEO
                        参考视频路径 / URL / 素材 ID
  --reference-audio REFERENCE_AUDIO
                        参考音频路径 / URL / 素材 ID
  --duration DURATION   视频时长（秒），支持 4~15 或 -1，默认 15
  --ratio {16:9,4:3,1:1,3:4,9:16,21:9,adaptive}
                        视频宽高比
  --resolution {480p,720p,1080p}
                        输出分辨率
  --generate-audio, --no-generate-audio
                        是否生成音频 (default: True)
  --return-last-frame   返回生成视频的尾帧图像
  --watermark           生成视频是否包含水印
  --seed SEED           种子整数，默认 -1
  --safety-identifier SAFETY_IDENTIFIER
                        终端用户的唯一标识符
  --web-search          开启联网搜索工具
  --download            等待完成后自动下载视频到本地
  --output-path OUTPUT_PATH
                        指定下载视频的保存路径（仅在启用 --download 时有效）

标准化示例
示例 1：纯文本生成视频，并下载到指定路径
python seedance-2-video-generation/seedance-2-video-generation/scripts/pipeline.py \
  --text "一只可爱的赛博朋克风格小猫在下雨的霓虹街道上奔跑" \
  --resolution "1080p" \
  --download \
  --output-path "./outputs/cyber_cat.mp4"

示例 2：使用本地图片和远程图片 URL 作为首尾帧生成视频
python seedance-2-video-generation/seedance-2-video-generation/scripts/pipeline.py \
  --first-frame "/path/to/my/local_start.png" \
  --last-frame "https://example.com/remote_end.png" \
  --text "画面从白天的公园丝滑过渡到夜晚的星空" \
  --duration 10

最佳实践与常见问题
- [✓] 始终使用 pipeline.py：除非你需要进行底层调试，否则请始终使用 pipeline.py 作为入口。它能为你处理绝大部分繁琐的工程细节。
- [✓] 混合使用本地与远程素材：你可以自由地混合使用本地文件路径和远程 URL 作为素材输入，流水线会自动处理。
- [✓] 自动合规兜底：当使用的人物肖像素材触发风控时，流水线会自动将其上传到你的私域素材库（Assets）并使用 asset:// ID 重试，实现合规流程自动化。
- [✗] 避免手动模式选择：你不需要手动指定 --mode 参数，这是 pipeline.py 的核心价值之一。
seedance_cli.py：视频生成核心 API
这是与 Seedance 2.0 模型 API 直接交互的底层工具。pipeline.py 在内部调用它来发起真正的视频生成请求。
- 核心作用：根据指定的 mode 和 content（包含文本和素材 URL/ID），创建并轮询视频生成任务。
- 适用场景：主要用于底层调试、验证特定参数组合的效果，或在不涉及本地文件和合规兜底的简单场景下直接使用。
命令用法
你需要明确指定 --mode，并为该模式提供正确的 content 参数。所有素材都必须是 URL 或 Asset ID 格式。
$ python seedance-2-video-generation/seedance-2-video-generation/scripts/seedance_cli.py --help
usage: seedance_cli.py [-h] --mode {t2v,i2v,fl2v,multimodal_ref2v} [--text TEXT] [--first-frame FIRST_FRAME]
                       [--last-frame LAST_FRAME] [--reference-image REFERENCE_IMAGE] [--reference-video REFERENCE_VIDEO]
                       [--reference-audio REFERENCE_AUDIO] [--duration DURATION]
                       [--ratio {16:9,4:3,1:1,3:4,9:16,21:9,adaptive}] [--resolution {480p,720p,1080p}]
                       [--generate-audio | --no-generate-audio] [--return-last-frame] [--watermark] [--seed SEED]
                       [--model MODEL] [--safety-identifier SAFETY_IDENTIFIER] [--web-search]
                       [--execution-expires-after EXECUTION_EXPIRES_AFTER] [--callback-url CALLBACK_URL] [--wait]
                       [--download] [--output-path OUTPUT_PATH] [--interval INTERVAL] [--timeout TIMEOUT]
                       [--poll-timeout POLL_TIMEOUT] [--json]

Seedance-2 video generation (env based).

options:
  -h, --help            show this help message and exit
  --mode {t2v,i2v,fl2v,multimodal_ref2v}
                        生成模式：t2v (文生视频) / i2v (图生视频-首帧) / fl2v (图生视频-首尾帧) / multimodal_ref2v (多模态参考生视频)
  --text TEXT           输入的提示词文本（t2v 模式必填，其他模式可选）
  --first-frame FIRST_FRAME
                        首帧图片 URL / Base64 / 素材 ID（i2v / fl2v）
  --last-frame LAST_FRAME
                        尾帧图片 URL / Base64 / 素材 ID（fl2v）
  --reference-image REFERENCE_IMAGE
                        参考图片 URL / Base64 / 素材 ID（multimodal_ref2v 支持 0~9 个）
  --reference-video REFERENCE_VIDEO
                        参考视频 URL / 素材 ID（multimodal_ref2v 支持 0~3 个）
  --reference-audio REFERENCE_AUDIO
                        参考音频 URL / Base64 / 素材 ID（multimodal_ref2v 支持 0~3 个）
  --duration DURATION   视频时长（秒），支持 4~15 或 -1（模型智能选择），默认 15
  --ratio {16:9,4:3,1:1,3:4,9:16,21:9,adaptive}
                        视频宽高比，默认 9:16
  --resolution {480p,720p,1080p}
                        输出分辨率，默认 720p
  --generate-audio, --no-generate-audio
                        是否生成音频，默认开启；可用 --no-generate-audio 关闭 (default: True)
  --return-last-frame   返回生成视频的尾帧图像
  --watermark           生成视频是否包含水印
  --seed SEED           种子整数，默认 -1
  --model MODEL         指定模型版本（默认读取 VOLC_ARK_SEEDANCE_MODEL）
  --safety-identifier SAFETY_IDENTIFIER
                        终端用户的唯一标识符
  --web-search          开启联网搜索工具
  --execution-expires-after EXECUTION_EXPIRES_AFTER
                        任务超时阈值（秒），默认 172800
  --callback-url CALLBACK_URL
                        回调通知地址
  --wait                等待任务完成并输出 video_url (default: True)
  --download            等待完成后自动下载视频到本地
  --output-path OUTPUT_PATH
                        指定下载视频的保存路径（仅在启用 --download 时有效，默认保存至脚本同级目录下的 runtime/ 文件夹内）
  --interval INTERVAL   轮询间隔（秒）
  --timeout TIMEOUT     等待超时（秒）
  --poll-timeout POLL_TIMEOUT
                        单次轮询请求超时（秒）
  --json                输出 JSON

标准化示例
# 使用多模态参考模式，所有素材均为 URL
python seedance-2-video-generation/seedance-2-video-generation/scripts/seedance_cli.py \
  --mode "multimodal_ref2v" \
  --text "请将@图片1的人物风格转换为@图片2的赛博朋克场景中，动作参考@视频1" \
  --reference-image "https://example.com/character.png" \
  --reference-image "https://example.com/scene.png" \
  --reference-video "https://example.com/motion.mp4"

最佳实践与常见问题
- [✓] 调试利器：当 pipeline.py 运行失败时，你可以使用 seedance_cli.py 传入相同的、已转换为 URL 的参数，来复现和定位问题。
- [✗] 不要用它处理本地文件：seedance_cli.py 不具备自动上传本地文件的能力。如果你传入一个本地路径，它会直接报错。
tos_cli.py：本地文件上传 TOS
负责将本地文件上传到火山引擎对象存储（TOS），并返回一个带签名的、有时效性的可读 URL。
- 核心作用：解决模型 API 无法直接访问本地文件的问题，是连接本地素材与云端服务的第一座桥梁。
- 适用场景：在调用任何需要 URL 输入的下游 CLI 之前，对本地文件进行预处理。
命令用法
$ python seedance-2-video-generation/seedance-2-video-generation/scripts/tos_cli.py --help
usage: tos_cli.py [-h] --files FILES [FILES ...] [--dir DIR] [--expires EXPIRES] [--json]

Upload local files to TOS and print presigned URLs.

options:
  -h, --help            show this help message and exit
  --files FILES [FILES ...], -f FILES [FILES ...]
                        一个或多个本地文件路径
  --dir DIR             对象前缀目录（默认 TOS_DIR 或 volc-assets/）
  --expires EXPIRES     URL 有效期（秒），默认 24 小时
  --json                以 JSON 输出（用于脚本串联）

标准化示例
# 上传单个文件
python seedance-2-video-generation/seedance-2-video-generation/scripts/tos_cli.py --files "/path/to/my/video.mp4"

# 上传多个文件并以 JSON 格式输出结果
python seedance-2-video-generation/seedance-2-video-generation/scripts/tos_cli.py --files "image1.jpg" "image2.png" --json

最佳实践与常见问题
- [✓] 内容寻址与秒传：该工具默认使用文件的 MD5 内容摘要来命名 TOS 对象。这意味着，如果你多次上传同一个文件，它不会产生重复存储，而是会直接复用已有的对象，并返回一个新的签名 URL，实现“秒传”。
- [✓] 作为前置步骤：在任何需要处理本地文件的自动化脚本中，都应首先调用 tos_cli.py。
assets_cli.py：私域素材库管理
将公网 URL 或 TOS URL 形式的素材入库到你的私域素材库（Assets），主要用于处理需要合规审查的人物肖像。
- 核心作用：对涉及人脸/肖像的素材进行合规入库，获取 asset:// 格式的素材 ID，用于解决部分场景下的风控限制问题。
- 适用场景：当 seedance_cli.py 返回包含“人脸”、“肖像”、“portrait”等敏感词的错误时，作为兜底策略自动调用。
命令用法
$ python seedance-2-video-generation/seedance-2-video-generation/scripts/assets_cli.py --help
usage: assets_cli.py [-h] [--urls [URLS ...]] [--url-file URL_FILE] [--group GROUP] [--project PROJECT]
                     [--asset-type {Image,Video,Audio}] [--host HOST] [--region REGION] [--service SERVICE] [--version VERSION]
                     [--on-exists {auto,use,overwrite,new-group,prompt}] [--name-prefix NAME_PREFIX] [--md5-timeout MD5_TIMEOUT]
                     [--json]

Upload URLs to Assets library and print asset_id.

options:
  -h, --help            show this help message and exit
  --urls [URLS ...]     一个或多个可访问 URL
  --url-file URL_FILE   URL 列表文件（每行一个 URL）
  --group GROUP         素材库 group 名称
  --project PROJECT     ProjectName，默认 default
  --asset-type {Image,Video,Audio}
                        强制指定素材类型（默认按 URL 后缀猜测）
  --host HOST           Assets API host（默认读 VOLC_ASSETS_HOST）
  --region REGION       Assets region（默认读 VOLC_ASSETS_REGION）
  --service SERVICE     Assets service（默认读 VOLC_ASSETS_SERVICE）
  --version VERSION     Assets API version（默认读 VOLC_ASSETS_VERSION）
  --on-exists {auto,use,overwrite,new-group,prompt}
                        同名素材已存在时策略：auto=同MD5复用，否则新建（默认 auto）
  --name-prefix NAME_PREFIX
                        素材 Name 前缀（默认 md5_）
  --md5-timeout MD5_TIMEOUT
                        下载计算 MD5 的超时（秒），默认 60
  --json                以 JSON 输出（用于脚本串联）

标准化示例
# 将一个 TOS URL 入库到 Assets
python seedance-2-video-generation/seedance-2-video-generation/scripts/assets_cli.py --urls "https://your-bucket.tos-cn-beijing.volces.com/xxx?AWSAccessKeyId=..."

最佳实践与常见问题
- [✓] 自动化调用：通常你不需要手动调用此脚本。pipeline.py 在捕捉到特定错误后会自动触发它。
- [✓] 内容安全：Assets 素材库提供了内容审核与管理能力，是处理企业生产环境中敏感素材（如签约模特、自有版权内容）的最佳实践。
llm_cli.py & vlm_cli.py：AI 辅助创作工具
这两个工具分别用于调用大语言模型（LLM）和多模态大模型（VLM），为视频创作提供 AI 助力。
- llm_cli.py：纯文本处理。可用于润色提示词、扩写分镜脚本、生成台词等。
- vlm_cli.py：多模态理解。可用于理解图片/视频内容，让 AI 为你分析参考素材的特点，并将其转化为文字描述，用于丰富你的提示词。
命令用法
llm_cli.py
$ python seedance-2-video-generation/seedance-2-video-generation/scripts/llm_cli.py --help
usage: llm_cli.py [-h] [-s SYSTEM] [--system-file SYSTEM_FILE] [-t TEXT] [--text-file TEXT_FILE] [--model MODEL]

大型语言模型 (LLM) CLI - 纯文本生成工具

options:
  -h, --help            show this help message and exit
  -s SYSTEM, --system SYSTEM
                        可选的系统提示词文本（System Prompt），用于设定人设或背景规则
  --system-file SYSTEM_FILE
                        可选的系统提示词文件路径（优先级高于 --system）
  -t TEXT, --text TEXT  输入的指令/提问文本（如：'你好，请写一首诗'）
  --text-file TEXT_FILE
                        可选的提问文本文件路径（优先级高于 --text）
  --model MODEL         指定模型版本（默认读取 VOLC_ARK_LLM_MODEL）

vlm_cli.py
$ python seedance-2-video-generation/seedance-2-video-generation/scripts/vlm_cli.py --help
usage: vlm_cli.py [-h] -t TEXT [-m [MEDIA ...]] [--model MODEL]

多模态大模型理解 CLI (支持图片/视频/文档/音频)

options:
  -h, --help            show this help message and exit
  -t TEXT, --text TEXT  输入的指令/提问文本（如：'请描述图片内容'）
  -m [MEDIA ...], --media [MEDIA ...]
                        要分析的媒体路径或 URL（可多次指定），自动识别 图片/视频/PDF/音频
  --model MODEL         指定模型版本（默认读取 VOLC_ARK_VLM_MODEL）

标准化示例
示例 1：使用 llm_cli.py 和导演 Prompt 润色提示词
python seedance-2-video-generation/seedance-2-video-generation/scripts/llm_cli.py \
  --system-file "seedance-2-video-generation/seedance-2-video-generation/prompts/seedance-2.0-director.md" \
  --text "用户原始意图：做一个女孩在海边走路的视频，伤感一点"

预期输出会是一个结构化的、符合 Seedance 2.0 最佳实践的详细提示词。
示例 2：使用 vlm_cli.py 分析参考图片
python seedance-2-video-generation/seedance-2-video-generation/scripts/vlm_cli.py \
  --media "/path/to/reference_scene.jpg" \
  --text "请详细描述这幅画面的构图、光影、色调和风格，用于生成视频的提示词。"

预期输出会是一段关于该图片视觉元素的详细文字描述，你可以直接将其融入到 pipeline.py 的 --text 参数中。
download_cli.py：通用文件下载器
一个简单的工具，用于从给定的 URL 下载文件到本地。
- 核心作用：将云端生成或存储的视频、图片等文件下载到本地，完成交付闭环。
- 适用场景：当 pipeline.py 或 seedance_cli.py 成功返回 video_url 后，用于获取视频文件实体。
命令用法
$ python seedance-2-video-generation/seedance-2-video-generation/scripts/download_cli.py --help
usage: download_cli.py [-h] -o OUTPUT_PATH url

通用文件下载工具

positional arguments:
  url                   要下载的文件的 URL

options:
  -h, --help            show this help message and exit
  -o OUTPUT_PATH, --output OUTPUT_PATH
                        指定保存的本地路径

标准化示例
python seedance-2-video-generation/seedance-2-video-generation/scripts/download_cli.py \
  "https://some-video-url/generated_video.mp4?token=..." \
  --output "./my_project/final_video.mp4"

CLI 提示词工程：写给 AI 导演的精确脚本
即便使用 CLI，提示词（Prompt）依然是决定视频生产品质的灵魂。一个结构清晰、指令明确的提示词，是与 AI 高效协作的基石。本章节提炼了 seedance-2.0-director.md 的核心思想，为你提供一套可直接应用于 CLI 场景的提示词工程方法论。
核心心法：U 型注意力与八大要素
- U 型注意力机制：模型会重点关注提示词的开头和结尾。因此，请将最核心的指令（如主体、风格、关键参考素材）放在开头，将全局约束和画质要求放在结尾。
- 提示词万能公式：一份高质量的提示词应尽量包含以下八大核心要素：精准主体 + 动作细节 + 场景环境 + 光影色调 + 镜头运镜 + 视觉风格 + 画质参数 + 约束条件
像导演一样创作：结构化分镜与多模态绑定
最能发挥 Seedance 2.0 电影感潜力的提示词，是时序化的分镜脚本。你需要像导演一样，将一个长镜头拆解为多个逻辑连贯的短镜头，并为每个镜头分配合适的素材。
提示词结构模板
# 整体设定 (放开头)
@图片1 用于锁定主角面部, @图片2 用于设定场景氛围, @视频1 用于参考运镜。

# 分镜时序 (主体部分)
镜头1 (0-5秒): [景别] [主体] [动作], [场景细节], [光影描述], (音效/音乐)。
镜头2 (5-10秒): [景别] [主体] [动作], [场景细节], [光影描述], (音效/音乐)。
镜头3 (10-15秒): [景别] [主体] [动作], [场景细节], [光影描述], (音效/音乐)。

# 风格与约束 (放结尾)
电影质感, 复古胶片风格。4K超高清, 细节丰富。面部稳定不变形, 动作自然流畅, 无闪烁, 无文字。

参考素材序号规则
当你在 pipeline.py 或 seedance_cli.py 中通过 --reference-image, --reference-video 等参数传入多个素材时，它们在提示词中的 @ 序号是按类型和顺序决定的。
- 第一个 --reference-image 对应 @图片1，第二个对应 @图片2。
- 第一个 --reference-video 对应 @视频1，以此类推。
终极武器：AI 导演助手
当你需要将一个模糊的创意快速转化为结构化的提示词时，可以借助 llm_cli.py 和我们为你准备的 seedance-2.0-director.md 系统提示词（System Prompt）。
这个“AI 导演助手”能自动帮你完成：
- 结构化重写：将自然语言意图转换为标准的四段式（整体设定 → 素材声明 → 分镜时序 → 风格约束）提示词。
- 动作具象化：将抽象情绪（如“悲伤”）外化为具体动作（如“眼眶湿润，嘴唇微微颤抖”）。
- 约束内置：自动添加所有必要的负向约束，如“面部稳定不变形”、“避免生成文字”等，从源头规避常见问题。
使用示例
假设你的原始意图是：“一个女孩在雨天分手，很难过”。
你可以这样调用 llm_cli.py：
python seedance-2-video-generation/seedance-2-video-generation/scripts/llm_cli.py \
  --system-file "seedance-2-video-generation/seedance-2-video-generation/prompts/seedance-2.0-director.md" \
  --text "用户原始意图：一个女孩在雨天分手，很难过。参考素材：@图片1是女孩照片，@音频1是悲伤的钢琴曲。"

AI 导演助手可能会生成类似以下的专业提示词：
@图片1 用于锁定主角面部特征, @音频1 作为背景音乐。

开场：雨夜的城市街头，主角独自撑着一把透明雨伞站在路灯下。中景，雨水打在伞面上，在她脸上投下斑驳的光影，她的眼神空洞地望着前方。

中段：一个男人走进画面，对她说了些什么，然后转身决绝地离开。特写镜头，主角的嘴唇微微颤抖，一滴泪水混合着雨水从脸颊滑落。

收束：主角缓缓蹲下身子，将脸埋在膝盖里，肩膀开始无法抑制地抽动。镜头从她背后慢慢拉远，将她融入整个湿冷、孤独的城市夜景中。

4K超高清，电影质感，冷色调。确保主角面部稳定不变形，五官清晰，人体结构准确，动作自然流畅不僵硬，画面无卡顿、无闪烁。避免生成任何形式的文字、字幕。

你只需将这段优化后的提示词直接喂给 pipeline.py 的 --text 参数，即可启动一次高质量的视频生成。
