#!/usr/bin/env node
/**
 * seedance2-cli 自动化安装脚本
 * 兼容 OpenClaw / Hermes / 其他 Agent 框架的自动安装
 *
 * 特性：
 * - 零交互安装（--yes 模式）
 * - 自动检测 python3 / pip 可用性
 * - 支持虚拟环境隔离（推荐）
 * - 详细的 JSON 状态输出（便于 Agent 解析）
 * - 失败时返回非零退出码
 * - OpenClaw 环境自动安装 SKILL.md 到 skills 目录
 *
 * 使用方式：
 *   curl -fsSL https://raw.githubusercontent.com/li-neo/seedance2-cli/main/install.js | node
 */

const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const PKG_NAME = 'seedance2-cli';
const REPO_URL = 'https://github.com/li-neo/seedance2-cli.git';

function log(level, message) {
  const timestamp = new Date().toISOString();
  const output = JSON.stringify({ timestamp, level, message, pkg: PKG_NAME });
  if (level === 'error') {
    console.error(output);
  } else {
    console.log(output);
  }
}

function runCommand(cmd, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, {
      stdio: options.silent ? 'pipe' : 'inherit',
      ...options,
    });

    let stdout = '';
    let stderr = '';

    if (options.silent) {
      child.stdout?.on('data', (data) => { stdout += data; });
      child.stderr?.on('data', (data) => { stderr += data; });
    }

    child.on('exit', (code) => {
      if (code === 0) {
        resolve({ code: 0, stdout, stderr });
      } else {
        reject(new Error(`Command failed with code ${code}: ${stderr || stdout}`));
      }
    });

    child.on('error', (err) => {
      reject(err);
    });
  });
}

function detectPython() {
  const candidates = [
    process.env.SEEDANCE_PYTHON,
    'python3',
    'python',
  ].filter(Boolean);

  for (const py of candidates) {
    try {
      execSync(`${py} --version`, { stdio: 'pipe' });
      return py;
    } catch {
      continue;
    }
  }
  return null;
}

function detectPip(python) {
  try {
    execSync(`${python} -m pip --version`, { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function detectOpenClaw() {
  // 检测 OpenClaw 环境：检查 OPENCLAW_HOME 或 ~/.openclaw 目录
  const openclawHome = process.env.OPENCLAW_HOME;
  if (openclawHome && fs.existsSync(openclawHome)) {
    return openclawHome;
  }

  const homeDir = os.homedir();
  const possiblePaths = [
    path.join(homeDir, '.openclaw'),
    path.join(homeDir, 'openclaw'),
    path.join(homeDir, '.config', 'openclaw'),
  ];

  for (const p of possiblePaths) {
    if (fs.existsSync(p)) {
      return p;
    }
  }
  return null;
}

async function cloneRepo(targetDir) {
  if (fs.existsSync(targetDir)) {
    log('info', `Directory exists: ${targetDir}, pulling latest changes...`);
    await runCommand('git', ['-C', targetDir, 'pull'], { silent: true });
  } else {
    log('info', `Cloning repository to ${targetDir}...`);
    await runCommand('git', ['clone', REPO_URL, targetDir], { silent: true });
  }
}

async function installPythonDeps(python, requirementsPath) {
  const venvPath = path.join(path.dirname(requirementsPath), '.venv');

  if (!fs.existsSync(venvPath)) {
    log('info', 'Creating virtual environment...');
    await runCommand(python, ['-m', 'venv', venvPath], { silent: true });
  }

  const venvPython = process.platform === 'win32'
    ? path.join(venvPath, 'Scripts', 'python.exe')
    : path.join(venvPath, 'bin', 'python');

  log('info', `Installing Python dependencies with ${venvPython}...`);
  await runCommand(venvPython, ['-m', 'pip', 'install', '-r', requirementsPath], { silent: false });

  return venvPython;
}

function installSkillToOpenClaw(openclawHome, installDir) {
  const skillsDir = path.join(openclawHome, 'skills');
  if (!fs.existsSync(skillsDir)) {
    fs.mkdirSync(skillsDir, { recursive: true });
  }

  const skillName = 'seedance2-cli';
  const targetDir = path.join(skillsDir, skillName);

  // 复制 SKILL.md 到 OpenClaw skills 目录
  const skillSource = path.join(installDir, 'SKILL.md');
  if (fs.existsSync(skillSource)) {
    if (fs.existsSync(targetDir)) {
      fs.rmSync(targetDir, { recursive: true });
    }
    fs.mkdirSync(targetDir, { recursive: true });
    fs.copyFileSync(skillSource, path.join(targetDir, 'SKILL.md'));
    log('info', `Skill installed to OpenClaw: ${targetDir}`);
    return true;
  }
  return false;
}

function printEnvGuide() {
  const guide = `
╔══════════════════════════════════════════════════════════════════════════════╗
║                     seedance2-cli 环境变量配置指南                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  使用本工具前，必须配置以下环境变量：                                         ║
║                                                                              ║
║  【国内环境】                                                                 ║
║  export VOLC_ACCESS_KEY="你的 Access Key"                                    ║
║  export VOLC_SECRET_KEY="你的 Secret Key"                                    ║
║  export VOLC_ARK_API_KEY="你的 Ark API Key"                                  ║
║  export VOLC_ARK_API_URL="https://ark.cn-beijing.volces.com/api/v3"          ║
║  export VOLC_ARK_SEEDANCE_MODEL="doubao-seedance-2-0-pro-260215"             ║
║  export VOLC_TOS_REGION="cn-beijing"                                         ║
║  export VOLC_TOS_ENDPOINT="tos-cn-beijing.volces.com"                        ║
║  export VOLC_TOS_BUCKET="你的 TOS Bucket"                                    ║
║                                                                              ║
║  【海外 BytePlus 环境】                                                       ║
║  export VOLC_ARK_API_URL="https://ark.ap-southeast-1.byteplusapi.com/api/v3" ║
║  export VOLC_ARK_SEEDANCE_MODEL="dreamina-seedance-2-0-260128"               ║
║  export VOLC_TOS_REGION="ap-southeast-1"                                     ║
║  export VOLC_TOS_ENDPOINT="tos-ap-southeast-1.bytepluses.com"                ║
║                                                                              ║
║  【获取方式】                                                                 ║
║  • AK/SK:      https://www.volcengine.com/docs/6291/65568                    ║
║  • Ark API Key: https://www.volcengine.com/docs/82379/1399008                ║
║  • TOS Bucket:  https://www.volcengine.com/docs/6349/107356                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
`;
  console.log(guide);
}

async function main() {
  log('info', 'Starting automated installation...');

  // 1. 检测 Node.js
  try {
    execSync('node --version', { stdio: 'pipe' });
    log('info', 'Node.js is available');
  } catch {
    log('error', 'Node.js is not installed. Please install Node.js >= 18 first.');
    process.exit(1);
  }

  // 2. 检测 Python
  const python = detectPython();
  if (!python) {
    log('error', 'Python is not installed. Please install Python 3 first.');
    process.exit(1);
  }
  log('info', `Python detected: ${python}`);

  // 3. 检测 pip
  if (!detectPip(python)) {
    log('error', 'pip is not available. Please install pip first.');
    process.exit(1);
  }
  log('info', 'pip is available');

  // 4. 检测 OpenClaw 环境
  const openclawHome = detectOpenClaw();
  if (openclawHome) {
    log('info', `OpenClaw detected at: ${openclawHome}`);
  }

  // 5. 克隆仓库到临时目录
  const installDir = process.env.SEEDANCE_INSTALL_DIR || path.join(os.tmpdir(), PKG_NAME);
  try {
    await cloneRepo(installDir);
    log('info', `Repository ready at ${installDir}`);
  } catch (err) {
    log('error', `Failed to clone repository: ${err.message}`);
    process.exit(1);
  }

  // 6. 安装 Python 依赖
  const requirementsPath = path.join(installDir, 'requirements.txt');
  if (!fs.existsSync(requirementsPath)) {
    log('error', `requirements.txt not found at ${requirementsPath}`);
    process.exit(1);
  }

  try {
    const targetPython = await installPythonDeps(python, requirementsPath);
    log('info', `Python dependencies installed successfully. Python: ${targetPython}`);
  } catch (err) {
    log('error', `Failed to install Python dependencies: ${err.message}`);
    process.exit(1);
  }

  // 7. 验证 CLI 可用性
  try {
    const binPath = path.join(installDir, 'bin', 'seedance.js');
    await runCommand('node', [binPath, '--version'], { silent: true });
    log('info', 'CLI verification passed');
  } catch (err) {
    log('error', `CLI verification failed: ${err.message}`);
    process.exit(1);
  }

  // 8. 安装 Skill 到 OpenClaw（如果检测到）
  if (openclawHome) {
    const installed = installSkillToOpenClaw(openclawHome, installDir);
    if (installed) {
      log('info', 'Skill registered in OpenClaw successfully');
    }
  }

  // 9. 输出使用信息和环境变量指南
  log('info', 'Installation completed successfully!');
  log('info', `Install directory: ${installDir}`);
  log('info', `To use: cd ${installDir} && node bin/seedance.js <command>`);
  log('info', 'Or: npx github:li-neo/seedance2-cli <command>');

  printEnvGuide();
}

main().catch((err) => {
  log('error', `Unexpected error: ${err.message}`);
  process.exit(1);
});
