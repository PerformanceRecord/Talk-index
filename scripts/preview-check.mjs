import fs from "node:fs";

const requiredOutputFiles = ["dist/index.html", "dist/app.js", "dist/styles.css"];

function fail(message) {
  console.error(`❌ preview check failed: ${message}`);
  process.exit(1);
}

for (const file of requiredOutputFiles) {
  if (!fs.existsSync(file)) {
    fail(`missing build output: ${file}`);
  }
}

const html = fs.readFileSync("dist/index.html", "utf8");
if (!html.includes("window.TALK_INDEX_DATA_URL")) {
  fail("dist/index.html does not define window.TALK_INDEX_DATA_URL");
}

console.log("✅ preview check passed");
console.log(`- verified output files: ${requiredOutputFiles.join(", ")}`);
