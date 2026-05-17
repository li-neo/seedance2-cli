#!/usr/bin/env node
// Seedance CLI 统一入口
// 通过子命令分发到对应的 Python 脚本

const { spawn } = require('child_process');
const path = require('path');

const SCRIPTS_DIR = path.join(__dirname, '..', 'scripts');

const COMMANDS = {
  // 核心流水线
  'generate': { script: 'pipeline.py', desc: '一键生成视频（自动模式识别 + TOS + Assets 兜底）' },
  'gen': { script: 'pipeline.py', desc: 'generate 的别名' },

  // 原子能力
  'seedance': { script: 'seedance_cli.py', desc: '直接调用 Seedance API' },
  'tos': { script: 'tos_cli.py', desc: 'TOS 文件上传工具' },
  'assets': { script: 'assets_cli.py', desc: 'Assets 素材库工具' },
  'llm': { script: 'llm_cli.py', desc: 'LLM 文本生成工具' },
  'vlm': { script: 'vlm_cli.py', desc: 'VLM 多模态理解工具' },
  'download': { script: 'download_cli.py', desc: '文件下载工具' },
};

function printHelp() {
  console.log(`
seedance2-cli v${require('../package.json').version}

Usage: seedance <command> [options]

Commands:
${Object.entries(COMMANDS)
  .filter(([k]) => !['gen'].includes(k))
  .map(([k, v]) => `  ${k.padEnd(12)} ${v.desc}`)
  .join('\n')}

Options:
  -h, --help    Show help for a command
  -v, --version Show CLI version

Examples:
  seedance generate --text "一只赛博朋克小猫" --download
  seedance tos --files ./a.jpg ./b.png
  seedance assets --urls https://example.com/img.jpg
  seedance llm --text "你好"
  seedance vlm --image ./photo.jpg --text "描述这张图"
`);
}

function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || ['-h', '--help'].includes(args[0])) {
    printHelp();
    process.exit(0);
  }

  if (['-v', '--version'].includes(args[0])) {
    console.log(require('../package.json').version);
    process.exit(0);
  }

  const [command, ...restArgs] = args;
  const cmdDef = COMMANDS[command];

  if (!cmdDef) {
    console.error(`Unknown command: ${command}`);
    console.error(`Run 'seedance --help' for usage.`);
    process.exit(1);
  }

  const scriptPath = path.join(SCRIPTS_DIR, cmdDef.script);
  const pyArgs = [scriptPath, ...restArgs];

  // 优先使用 python3，回退 python
  const python = process.env.SEEDANCE_PYTHON || 'python3';
  const child = spawn(python, pyArgs, {
    stdio: 'inherit',
    cwd: SCRIPTS_DIR,
  });

  child.on('exit', (code) => {
    process.exit(code ?? 0);
  });

  child.on('error', (err) => {
    console.error(`Failed to start ${python}: ${err.message}`);
    process.exit(1);
  });
}

main();
