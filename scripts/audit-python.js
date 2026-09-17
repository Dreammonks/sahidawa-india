#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const ROOT_DIR = path.resolve(__dirname, "..");
const ETL_TOML_PATH = path.join(ROOT_DIR, "apps/etl/pyproject.toml");

const TEMP_ETL_REQ = path.join(ROOT_DIR, "apps/etl/temp-requirements-audit.txt");

// Colors
const c = {
    reset: "\x1b[0m",
    bold: "\x1b[1m",
    red: "\x1b[31m",
    green: "\x1b[32m",
    yellow: "\x1b[33m",
    cyan: "\x1b[36m",
    gray: "\x1b[90m",
};

function log(color, symbol, msg) {
    console.log(`${color}${symbol}${c.reset} ${msg}`);
}

function checkPipAudit() {
    try {
        execSync("pip-audit --version", { stdio: "ignore" });
        return true;
    } catch (err) {
        return false;
    }
}

/**
 * Check if a file has changed in the current branch compared to main.
 * This change-detection logic avoids blocking everyday development pushes by skipping
 * the Python audit unless the requirements file itself has been modified.
 *
 * @param {string} relativeFilePath Path to the file from the workspace root
 * @returns {boolean} True if the file has modified lines in this branch
 */
function hasFileChanged(relativeFilePath) {
    try {
        // Determine the base branch (local 'main' or fallback to remote 'origin/main')
        let base = "main";
        try {
            execSync("git rev-parse --verify main", { stdio: "ignore" });
        } catch {
            base = "origin/main";
        }

        // Find the merge-base (common ancestor) between base branch and current HEAD
        let mergeBase;
        try {
            mergeBase = execSync(`git merge-base ${base} HEAD`, { encoding: "utf8" }).trim();
        } catch {
            mergeBase = base;
        }

        // Check if there are diffs for the specified file path
        const diff = execSync(`git diff --name-only ${mergeBase} HEAD -- "${relativeFilePath}"`, {
            encoding: "utf8",
            stdio: ["pipe", "pipe", "pipe"],
        }).trim();

        return diff.length > 0;
    } catch (err) {
        // If Git command fails (e.g. non-git environment), fallback to true to run the audit safely
        return true;
    }
}

function parseAndPinRequirements(content) {
    const packages = new Map();
    const lines = content.split(/\r?\n/);

    for (const line of lines) {
        let trimmed = line.trim();
        if (!trimmed || trimmed.startsWith("#")) continue;

        // Filter out HTTP/HTTPS URLs (like custom model links)
        if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) continue;

        // Strip inline comments
        const commentIdx = trimmed.indexOf("#");
        if (commentIdx !== -1) {
            trimmed = trimmed.substring(0, commentIdx).trim();
        }

        // Parse package name and version operator/value
        const match = trimmed.match(/^([a-zA-Z0-9_\-\[\]]+)(>=|==|<=|~=|>|<)?(.*)$/);
        if (match) {
            let name = match[1].trim();
            const op = match[2];
            let ver = match[3] ? match[3].trim() : "";

            // Strip extras like [standard]
            const bracketIdx = name.indexOf("[");
            if (bracketIdx !== -1) {
                name = name.substring(0, bracketIdx).trim();
            }

            if (op && ver) {
                // If multiple comma-separated constraints, take the first one
                const commaIdx = ver.indexOf(",");
                if (commaIdx !== -1) {
                    ver = ver.substring(0, commaIdx).trim();
                }
                packages.set(name.toLowerCase(), `${name}==${ver}`);
            } else {
                // Unversioned: pin to a dummy 0.0.0 version to satisfy pip-audit --disable-pip
                if (!packages.has(name.toLowerCase())) {
                    packages.set(name.toLowerCase(), `${name}==0.0.0`);
                }
            }
        }
    }

    return Array.from(packages.values());
}

function runAudit() {
    if (!checkPipAudit()) {
        log(c.yellow, "⚠", "pip-audit is not installed.");
        console.log(`  ${c.bold}If you are modifying Python code, please install it:${c.reset}`);
        console.log(`  pip install pip-audit\n`);
        log(
            c.yellow,
            "⚠",
            "Skipping Python audit gracefully so work outside apps/etl is not blocked."
        );
        process.exit(0);
    }

    let failed = false;

    if (fs.existsSync(ETL_TOML_PATH)) {
        if (hasFileChanged("apps/etl/pyproject.toml")) {
            log(c.cyan, "→", "Preparing ETL dependency list...");
            const tomlContent = fs.readFileSync(ETL_TOML_PATH, "utf8");
            const dependenciesMatch = tomlContent.match(/dependencies\s*=\s*\[([\s\S]*?)\]/);
            const etlRawLines = [];
            if (dependenciesMatch) {
                const depBlock = dependenciesMatch[1];
                const lines = depBlock.split(/\r?\n/);
                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed || trimmed.startsWith("#")) continue;
                    const match = trimmed.match(/"([^"]+)"/) || trimmed.match(/'([^']+)'/);
                    if (match) {
                        etlRawLines.push(match[1]);
                    }
                }
            }

            const pinned = parseAndPinRequirements(etlRawLines.join("\n"));
            fs.writeFileSync(TEMP_ETL_REQ, pinned.join("\n"), "utf8");

            try {
                log(c.cyan, "→", "Auditing apps/etl dependencies...");
                const output = execSync(`pip-audit -r "${TEMP_ETL_REQ}" --no-deps --disable-pip`, {
                    encoding: "utf8",
                    stdio: ["pipe", "pipe", "pipe"],
                });
                console.log(output);
                log(c.green, "✔", "No Python vulnerabilities found in apps/etl");
            } catch (err) {
                failed = true;
                log(c.red, "✖", "Vulnerabilities found in apps/etl (or audit failed):");
                if (err.stdout) console.log(err.stdout);
                if (err.stderr) console.error(err.stderr);
            } finally {
                if (fs.existsSync(TEMP_ETL_REQ)) {
                    fs.unlinkSync(TEMP_ETL_REQ);
                }
            }
        } else {
            log(c.gray, "•", "No changes detected in apps/etl/pyproject.toml. Skipping ETL audit.");
        }
    } else {
        log(c.yellow, "⚠", "ETL pyproject.toml not found at: " + ETL_TOML_PATH);
    }

    if (failed) {
        log(c.red, "✖", "Python security audit failed.");
        process.exit(1);
    } else {
        log(c.green, "✔", "Python security audit passed.");
        process.exit(0);
    }
}

runAudit();
