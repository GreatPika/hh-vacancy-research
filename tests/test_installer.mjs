import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const repoRoot = path.resolve(import.meta.dirname, "..");
const cliPath = path.join(repoRoot, "bin", "hh-vacancy-research-skill.mjs");

async function makeTempDir(prefix) {
  return fs.mkdtemp(path.join(os.tmpdir(), prefix));
}

function runCli(args, env) {
  return spawnSync(process.execPath, [cliPath, ...args], {
    cwd: repoRoot,
    env: { ...process.env, ...env },
    encoding: "utf8",
    stdio: "pipe",
  });
}

async function pathExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

function installStatePath(cacheHome, target) {
  const hash = createHash("sha256").update(path.resolve(target)).digest("hex").slice(0, 16);
  return path.join(cacheHome, "installs", `${hash}.json`);
}

async function writeStaleInstallState(cacheHome, target) {
  const statePath = installStatePath(cacheHome, target);
  await fs.mkdir(path.dirname(statePath), { recursive: true });
  await fs.writeFile(
    statePath,
    `${JSON.stringify({
      packageName: "hh-vacancy-research-skill",
      packageVersion: "0.0.0",
      targetDir: target,
      cacheRoot: cacheHome,
    }, null, 2)}\n`,
    "utf8",
  );
}

async function createFakePython(binDir) {
  const fakePython = path.join(binDir, "python");
  await fs.mkdir(binDir, { recursive: true });
  await fs.writeFile(
    fakePython,
    `#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const args = process.argv.slice(2);

if (args[0] === "--version") {
  console.log("Python 3.12.0");
  process.exit(0);
}

if (args[0] === "-m" && args[1] === "venv") {
  const destination = args[2];
  const binDir = process.platform === "win32" ? "Scripts" : "bin";
  const pythonName = process.platform === "win32" ? "python.exe" : "python";
  const pythonPath = path.join(destination, binDir, pythonName);
  fs.mkdirSync(path.dirname(pythonPath), { recursive: true });
  fs.writeFileSync(pythonPath, \`#!/usr/bin/env node
const args = process.argv.slice(2);
if (args[0] === "-m" && args[1] === "pip" && args[2] === "install" && args[3] === "-r") {
  process.exit(0);
}
if (args[0] === "-c" && args[1].includes("import openpyxl")) {
  console.log("3.1.5");
  process.exit(0);
}
if (args.some((arg) => arg.endsWith("hh_vacancy_scraper.py")) && args.includes("--validate-profile")) {
  process.exit(0);
}
process.exit(1);
\`);
  fs.chmodSync(pythonPath, 0o755);
  process.exit(0);
}

process.exit(1);
`,
    { mode: 0o755 },
  );
  return fakePython;
}

test("install copies only skill files into the Codex skill directory", async () => {
  const codexHome = await makeTempDir("hh-skill-codex-");
  const cacheHome = await makeTempDir("hh-skill-cache-");

  const result = runCli(["install", "--skip-python-deps"], {
    CODEX_HOME: codexHome,
    HH_VACANCY_RESEARCH_SKILL_CACHE: cacheHome,
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);

  const skillDir = path.join(codexHome, "skills", "hh-vacancy-research");
  assert.equal(await pathExists(path.join(skillDir, "SKILL.md")), true);
  assert.equal(await pathExists(path.join(skillDir, "requirements.txt")), false);
  assert.equal(await pathExists(path.join(skillDir, ".venv")), false);
  assert.equal(await pathExists(path.join(skillDir, ".hh-vacancy-research-skill.install.json")), false);
  assert.equal(await pathExists(path.join(skillDir, "scripts", "__pycache__")), false);
});

test("install creates Python virtualenv outside the Codex skill directory", async () => {
  const codexHome = await makeTempDir("hh-skill-codex-");
  const cacheHome = await makeTempDir("hh-skill-cache-");
  const fakeBin = await makeTempDir("hh-skill-python-");
  const python = process.platform === "win32" ? "python" : await createFakePython(fakeBin);

  const result = runCli(["install", "--python", python], {
    CODEX_HOME: codexHome,
    HH_VACANCY_RESEARCH_SKILL_CACHE: cacheHome,
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);

  const skillDir = path.join(codexHome, "skills", "hh-vacancy-research");
  const externalVenv = path.join(cacheHome, "venv");
  assert.equal(await pathExists(path.join(skillDir, ".venv")), false);
  assert.equal(await pathExists(externalVenv), true);
});

test("doctor uses the external virtualenv and does not require requirements.txt in the skill directory", async () => {
  const codexHome = await makeTempDir("hh-skill-codex-");
  const cacheHome = await makeTempDir("hh-skill-cache-");
  const fakeBin = await makeTempDir("hh-skill-python-");
  const python = process.platform === "win32" ? "python" : await createFakePython(fakeBin);
  const env = {
    CODEX_HOME: codexHome,
    HH_VACANCY_RESEARCH_SKILL_CACHE: cacheHome,
  };

  const install = runCli(["install", "--python", python], env);
  assert.equal(install.status, 0, install.stderr || install.stdout);

  const doctor = runCli(["doctor"], env);
  assert.equal(doctor.status, 0, doctor.stderr || doctor.stdout);
  assert.match(doctor.stdout, /doctor passed/);

  const skillDir = path.join(codexHome, "skills", "hh-vacancy-research");
  assert.equal(await pathExists(path.join(skillDir, "requirements.txt")), false);
});

test("install refuses to replace an existing skill directory even when stale external state exists", async () => {
  const codexHome = await makeTempDir("hh-skill-codex-");
  const cacheHome = await makeTempDir("hh-skill-cache-");
  const skillDir = path.join(codexHome, "skills", "hh-vacancy-research");
  await fs.mkdir(skillDir, { recursive: true });
  await fs.writeFile(path.join(skillDir, "SKILL.md"), "manual skill\n", "utf8");
  await writeStaleInstallState(cacheHome, skillDir);

  const result = runCli(["install", "--skip-python-deps"], {
    CODEX_HOME: codexHome,
    HH_VACANCY_RESEARCH_SKILL_CACHE: cacheHome,
  });

  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /already exists/);
  assert.equal(await fs.readFile(path.join(skillDir, "SKILL.md"), "utf8"), "manual skill\n");
});

test("uninstall keeps shared virtualenv while another external install state exists", async () => {
  const firstCodexHome = await makeTempDir("hh-skill-codex-");
  const secondCodexHome = await makeTempDir("hh-skill-codex-");
  const cacheHome = await makeTempDir("hh-skill-cache-");
  const fakeBin = await makeTempDir("hh-skill-python-");
  const python = process.platform === "win32" ? "python" : await createFakePython(fakeBin);
  const firstEnv = {
    CODEX_HOME: firstCodexHome,
    HH_VACANCY_RESEARCH_SKILL_CACHE: cacheHome,
  };
  const secondEnv = {
    CODEX_HOME: secondCodexHome,
    HH_VACANCY_RESEARCH_SKILL_CACHE: cacheHome,
  };

  const firstInstall = runCli(["install", "--python", python], firstEnv);
  assert.equal(firstInstall.status, 0, firstInstall.stderr || firstInstall.stdout);
  const secondInstall = runCli(["install", "--skip-python-deps"], secondEnv);
  assert.equal(secondInstall.status, 0, secondInstall.stderr || secondInstall.stdout);

  const uninstall = runCli(["uninstall"], firstEnv);
  assert.equal(uninstall.status, 0, uninstall.stderr || uninstall.stdout);

  assert.equal(await pathExists(path.join(cacheHome, "venv")), true);
  assert.equal(await pathExists(path.join(firstCodexHome, "skills", "hh-vacancy-research")), false);
  assert.equal(await pathExists(path.join(secondCodexHome, "skills", "hh-vacancy-research")), true);
});
