import fs from "node:fs";
import path from "node:path";

const distDir = "dist";
const files = ["index.html", "app.js", "styles.css"];

const dataUrl = (process.env.TALK_INDEX_DATA_URL || "").trim();

fs.rmSync(distDir, { recursive: true, force: true });
fs.mkdirSync(path.join(distDir, "index"), { recursive: true });

for (const file of files) {
  fs.copyFileSync(file, path.join(distDir, file));
}

if (dataUrl) {
  const indexPath = path.join(distDir, "index.html");
  const original = fs.readFileSync(indexPath, "utf8");
  const replaced = original.replace(
    /window\.TALK_INDEX_DATA_URL\s*=\s*"[^"]*";/,
    `window.TALK_INDEX_DATA_URL = "${dataUrl}";`
  );

  if (original === replaced) {
    console.error("❌ build failed: could not find TALK_INDEX_DATA_URL assignment in index.html");
    process.exit(1);
  }

  fs.writeFileSync(indexPath, replaced, "utf8");
}

console.log("✅ static build completed");
console.log(`- output directory: ${distDir}`);
console.log(`- bundled files: ${files.join(", ")}`);
console.log(`- TALK_INDEX_DATA_URL override: ${dataUrl ? "applied" : "not applied"}`);
