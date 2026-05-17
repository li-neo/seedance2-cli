#!/usr/bin/env node
/**
 * Seedance CLI 主入口（兼容直接 require/import）
 */

const { spawn } = require('child_process');
const path = require('path');

const SCRIPTS_DIR = path.join(__dirname, 'scripts');

const COMMANDS = {
  generate: { script: 'pipeline.py', desc: '一键生成视频（自动模式识别 + TOS + Assets 兜底）' },
  gen: { script: 'pipeline.py', desc: 'generate 的别名' },
  seedance: { script: 'seedance_cli.py', desc: '直接调用 Seedance API' },
  tos: { script: 'tos_cli.py', desc: 'TOS 文件上传工具' },
  assets: { script: 'assets_cli.py', desc: 'Assets 素材库工具' },
  llm: { script: 'llm_cli.py', desc: 'LLM 文本生成工具' },
  vlm: { script: 'vlm_cli.py', desc: 'VLM 多模态理解工具' },
  download: { script: 'download_cli.py', desc: '文件下载工具' },
};

function run(command, args = []) {
  const cmdDef = COMMANDS[command];
  if (!cmdDef) {
    throw new Error(`Unknown command: ${command}. Available: ${Object.keys(COMMANDS).join(', ')}`);
  }
  const scriptPath = path.join(SCRIPTS_DIR, cmdDef.script);
  const python = process.env.SEEDANCE_PYTHON || 'python3';
  return spawn(python, [scriptPath, ...args], {
    stdio: 'inherit',
    cwd: SCRIPTS_DIR,
  });
}

function getHelp() {
  return `
seedance2-cli v${require('./package.json').version}

Usage: seedance <command> [options]

Commands:
${Object.entries(COMMANDS)
  .filter(([k]) => !['gen'].includes(k))
  .map(([k, v]) => `  ${k.padEnd(12)} ${v.desc}`)
  .join('\n')}
`;
}

module.exports = { run, getHelp, COMMANDS };

// 如果直接运行此文件，则作为 CLI 入口
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length === 0 || ['-h', '--help'].includes(args[0])) {
    console.log(getHelp());
    process.exit(0);
  }

  if (['-v', '--version'].includes(args[0])) {
    console.log(require('./package.json').version);
    process.exit(0);
  }

  const [command, ...restArgs] = args;
  const child = run(command, restArgs);
  child.on('exit', (code) => process.exit(code ?? 0));
  child.on('error', (err) => {
    console.error(`Failed to start: ${err.message}`);
    process.exit(1);
  });
}
