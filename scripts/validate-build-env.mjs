import fs from "node:fs";

const requiredSourceFiles = ["index.html", "app.js", "styles.css"];

function fail(message) {
  console.error(`❌ build preflight failed: ${message}`);
  process.exit(1);
}

for (const file of requiredSourceFiles) {
  if (!fs.existsSync(file)) {
    fail(`required source file is missing: ${file}`);
  }
}

const dataUrl = (process.env.TALK_INDEX_DATA_URL || "").trim();
if (process.env.TALK_INDEX_DATA_URL !== undefined && dataUrl.length === 0) {
  fail("TALK_INDEX_DATA_URL is set but empty. Remove it or set a valid URL.");
}

if (dataUrl.length > 0) {
  try {
    const parsed = new URL(dataUrl);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      fail("TALK_INDEX_DATA_URL must use http or https.");
    }
  } catch {
    fail("TALK_INDEX_DATA_URL is not a valid URL.");
  }
}

console.log("✅ build preflight passed");
console.log(`- source files: ${requiredSourceFiles.join(", ")}`);
console.log(`- TALK_INDEX_DATA_URL override: ${dataUrl ? "set" : "not set (use index.html default)"}`);
