#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { constants as fsConstants } from "node:fs";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SKILL_NAME = "hh-vacancy-research";
const PACKAGE_NAME = "hh-vacancy-research-skill";
const SOURCE_REPO = "https://github.com/GreatPika/hh-vacancy-research";
const MARKER_FILE = ".hh-vacancy-research-skill.install.json";
const VENV_DIR = ".venv";
const PAYLOAD_ENTRIES = [
  "SKILL.md",
  "agents",
  "references",
  "requirements.txt",
  "scripts",
  "templates",
];

const sourceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const packageJson = JSON.parse(
  await fs.readFile(path.join(sourceRoot, "package.json"), "utf8"),
);
const packageVersion = packageJson.version;

function usage() {
  return `hh-vacancy-research-skill ${packageVersion}

Install and manage the hh-vacancy-research Codex skill.

Usage:
  hh-vacancy-research-skill install [--force] [--skip-python-deps] [--python <path>]
  hh-vacancy-research-skill doctor [--python <path>]
  hh-vacancy-research-skill uninstall [--force]
  hh-vacancy-research-skill --help
  hh-vacancy-research-skill --version

Examples:
  npx hh-vacancy-research-skill install
  npx hh-vacancy-research-skill install --skip-python-deps
  npx hh-vacancy-research-skill install --python python3.12
  npx hh-vacancy-research-skill doctor

The installer writes to $CODEX_HOME/skills/${SKILL_NAME}, or ~/.codex/skills/${SKILL_NAME}
when CODEX_HOME is not set. Python dependencies are installed into the skill-local .venv,
not into system Python.`;
}

function codexHome() {
  return process.env.CODEX_HOME
    ? path.resolve(process.env.CODEX_HOME)
    : path.join(os.homedir(), ".codex");
}

function targetDir() {
  return path.join(codexHome(), "skills", SKILL_NAME);
}

function markerPath(target = targetDir()) {
  return path.join(target, MARKER_FILE);
}

async function exists(filePath) {
  try {
    await fs.access(filePath, fsConstants.F_OK);
    return true;
  } catch {
    return false;
  }
}

function parseArgs(argv) {
  const args = [...argv];
  const command = args[0] && !args[0].startsWith("-") ? args.shift() : "help";
  const options = {
    force: false,
    skipPythonDeps: false,
    python: "",
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--force") {
      options.force = true;
    } else if (arg === "--skip-python-deps") {
      options.skipPythonDeps = true;
    } else if (arg === "--python") {
      const value = args[index + 1];
      if (!value || value.startsWith("-")) {
        throw new Error("--python requires a value");
      }
      options.python = value;
      index += 1;
    } else if (arg.startsWith("--python=")) {
      options.python = arg.slice("--python=".length);
      if (!options.python) {
        throw new Error("--python requires a value");
      }
    } else if (arg === "--help" || arg === "-h") {
      return { command: "help", options };
    } else if (arg === "--version" || arg === "-v") {
      return { command: "version", options };
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  if (command === "--help" || command === "-h") {
    return { command: "help", options };
  }
  if (command === "--version" || command === "-v") {
    return { command: "version", options };
  }

  return { command, options };
}

async function assertSourcePayload() {
  for (const entry of PAYLOAD_ENTRIES) {
    const entryPath = path.join(sourceRoot, entry);
    if (!(await exists(entryPath))) {
      throw new Error(`Package payload is missing ${entryPath}`);
    }
  }
}

async function copyPayload(target) {
  await fs.mkdir(target, { recursive: true });
  for (const entry of PAYLOAD_ENTRIES) {
    await fs.cp(path.join(sourceRoot, entry), path.join(target, entry), {
      recursive: true,
      force: true,
      errorOnExist: false,
    });
  }
}

async function writeMarker(target) {
  const marker = {
    packageName: PACKAGE_NAME,
    packageVersion,
    sourceRepo: SOURCE_REPO,
    installedAt: new Date().toISOString(),
  };
  await fs.writeFile(markerPath(target), `${JSON.stringify(marker, null, 2)}\n`, "utf8");
}

function pythonCandidates(options) {
  if (options.python) {
    return [{ command: options.python, prefixArgs: [] }];
  }
  if (process.platform === "win32") {
    return [
      { command: "py", prefixArgs: ["-3"] },
      { command: "python", prefixArgs: [] },
      { command: "python3", prefixArgs: [] },
    ];
  }
  return [
    { command: "python3", prefixArgs: [] },
    { command: "python", prefixArgs: [] },
  ];
}

function detectPython(options) {
  for (const candidate of pythonCandidates(options)) {
    const result = spawnSync(candidate.command, [...candidate.prefixArgs, "--version"], {
      encoding: "utf8",
      stdio: "pipe",
    });
    if (result.status === 0) {
      return candidate;
    }
  }
  return null;
}

function runPython(python, args, runOptions = {}) {
  return spawnSync(python.command, [...python.prefixArgs, ...args], {
    stdio: runOptions.capture ? "pipe" : "inherit",
    encoding: "utf8",
  });
}

function formatPythonCommand(python) {
  return [python.command, ...python.prefixArgs].join(" ");
}

function venvPath(target) {
  return path.join(target, VENV_DIR);
}

function venvPython(target) {
  return {
    command: process.platform === "win32"
      ? path.join(venvPath(target), "Scripts", "python.exe")
      : path.join(venvPath(target), "bin", "python"),
    prefixArgs: [],
  };
}

function formatShellPath(value) {
  return JSON.stringify(value);
}

async function createVirtualenv(target, basePython) {
  const destination = venvPath(target);
  console.log(`Creating Python virtual environment at ${destination}...`);
  const venv = runPython(basePython, ["-m", "venv", destination]);
  if (venv.status !== 0) {
    throw new Error(
      "Python virtual environment creation failed. The skill files were installed. " +
        `Retry with --python <path>, or run: ${formatPythonCommand(basePython)} -m venv ${formatShellPath(destination)}`,
    );
  }
}

async function installPythonDependencies(target, basePython) {
  await createVirtualenv(target, basePython);
  const python = venvPython(target);
  const requirements = path.join(target, "requirements.txt");
  console.log(`Installing Python dependencies into ${venvPath(target)}...`);
  const result = runPython(python, [
    "-m",
    "pip",
    "install",
    "-r",
    requirements,
  ]);
  if (result.status !== 0) {
    throw new Error(
      "Python dependency installation failed inside the skill virtual environment. " +
        `Retry with --python <path>, or run: ${formatPythonCommand(python)} -m pip install -r ${formatShellPath(requirements)}`,
    );
  }
}

async function pythonForDoctor(target, options) {
  if (options.python) {
    const explicit = detectPython(options);
    if (!explicit) {
      throw new Error(`Python executable was not found: ${options.python}`);
    }
    return explicit;
  }
  const installed = venvPython(target);
  if (await exists(installed.command)) {
    return installed;
  }
  throw new Error(
    `${venvPath(target)} was not found. Run \`${PACKAGE_NAME} install --force\`, ` +
      "or pass --python <path> to check another Python environment.",
  );
}

async function install(options) {
  await assertSourcePayload();
  const target = targetDir();
  const targetExists = await exists(target);
  const markerExists = await exists(markerPath(target));

  if (targetExists && !markerExists && !options.force) {
    throw new Error(
      `${target} already exists and was not created by ${PACKAGE_NAME}. ` +
        "Use --force to replace it.",
    );
  }

  if (targetExists) {
    await fs.rm(target, { recursive: true, force: true });
  }

  await copyPayload(target);
  await writeMarker(target);
  console.log(`Installed ${SKILL_NAME} to ${target}`);

  if (options.skipPythonDeps) {
    console.log("Skipped Python dependency installation.");
    return;
  }

  const python = detectPython(options);
  if (!python) {
    throw new Error(
      "Python 3 was not found. The skill files were installed, but Python dependencies were not. " +
        "Install Python 3 and run `hh-vacancy-research-skill install --force`, " +
        "or rerun with --skip-python-deps.",
    );
  }
  await installPythonDependencies(target, python);
}

async function doctor(options) {
  const target = targetDir();
  const skillPath = path.join(target, "SKILL.md");
  const agentMetadataPath = path.join(target, "agents", "openai.yaml");
  const scriptPath = path.join(target, "scripts", "hh_vacancy_scraper.py");

  if (!(await exists(skillPath))) {
    throw new Error(`${skillPath} was not found. Run \`${PACKAGE_NAME} install\` first.`);
  }
  if (!(await exists(agentMetadataPath))) {
    throw new Error(`${agentMetadataPath} was not found. Run \`${PACKAGE_NAME} install --force\`.`);
  }

  const python = await pythonForDoctor(target, options);
  console.log(`Python: ${formatPythonCommand(python)}`);

  const openpyxl = runPython(python, ["-c", "import openpyxl; print(openpyxl.__version__)"], {
    capture: true,
  });
  if (openpyxl.status !== 0) {
    throw new Error(
      `openpyxl is not available for ${formatPythonCommand(python)}. ` +
        `Run: ${formatPythonCommand(python)} -m pip install -r ${formatShellPath(path.join(target, "requirements.txt"))}`,
    );
  }
  console.log(`openpyxl: ${openpyxl.stdout.trim()}`);

  const validationProfile = path.join(
    await fs.mkdtemp(path.join(os.tmpdir(), "hh-vacancy-research-doctor-")),
    "profile.json",
  );
  await fs.writeFile(
    validationProfile,
    `${JSON.stringify({
      title: "Doctor validation profile",
      hh: {
        area: "113",
        max_pages: 1,
        search_delay_min: 0,
        search_delay_max: 0,
        vacancy_delay_min: 0,
        vacancy_delay_max: 0,
        filters: {
          search_field: [],
          experience: [],
          schedule: [],
          employment: [],
          industry: [],
          salary: null,
          only_with_salary: false,
          order_by: "relevance",
          period: null,
        },
      },
      match_scope: {
        title: true,
        company: false,
        description: true,
        skills: true,
      },
      search_terms: {
        Doctor: ["Doctor validation"],
      },
      term_patterns: {
        Doctor: ["Doctor\\s+validation"],
      },
      exclude_patterns: {},
      notes: "Temporary profile generated by doctor.",
    }, null, 2)}\n`,
    "utf8",
  );

  const validation = runPython(python, [
    scriptPath,
    "--profile",
    validationProfile,
    "--validate-profile",
  ]);
  if (validation.status !== 0) {
    throw new Error("Generated validation profile failed.");
  }

  console.log(`${SKILL_NAME} doctor passed.`);
}

async function uninstall(options) {
  const target = targetDir();
  if (!(await exists(target))) {
    console.log(`${SKILL_NAME} is not installed at ${target}`);
    return;
  }

  const markerExists = await exists(markerPath(target));
  if (!markerExists && !options.force) {
    throw new Error(
      `${target} does not contain ${MARKER_FILE}. ` +
        "Refusing to remove a manual install without --force.",
    );
  }

  await fs.rm(target, { recursive: true, force: true });
  console.log(`Removed ${target}`);
}

async function main() {
  const { command, options } = parseArgs(process.argv.slice(2));

  if (command === "help") {
    console.log(usage());
    return;
  }
  if (command === "version") {
    console.log(packageVersion);
    return;
  }
  if (command === "install") {
    await install(options);
    return;
  }
  if (command === "doctor") {
    await doctor(options);
    return;
  }
  if (command === "uninstall") {
    await uninstall(options);
    return;
  }

  throw new Error(`Unknown command: ${command}\n\n${usage()}`);
}

try {
  await main();
} catch (error) {
  console.error(`error: ${error.message}`);
  process.exit(1);
}
