import fs from "node:fs";
import path from "node:path";

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

const moduleEntryMatch = html.match(/<script\b[^>]*\btype=["']module["'][^>]*\bsrc=["']([^"']+)["'][^>]*>/i);
if (!moduleEntryMatch) {
  fail("dist/index.html does not include a module entry");
}

for (const match of html.matchAll(/\b(?:href|src)=["'](\.\/[^"']+)["']/gi)) {
  const assetPath = path.resolve("dist", match[1]);
  if (!fs.existsSync(assetPath)) {
    fail(`missing local HTML asset: ${match[1]}`);
  }
}

function resolveLocalModule(importerPath, specifier) {
  if (!specifier.startsWith(".")) return null;
  const resolved = path.resolve(path.dirname(importerPath), specifier);
  const relative = path.relative(path.resolve("dist"), resolved);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    fail(`module import escapes dist/: ${specifier} from ${importerPath}`);
  }
  return resolved;
}

function localModuleSpecifiers(source) {
  const imports = [];
  const patterns = [
    /\bimport\s+(?:[\s\S]*?\s+from\s+)?["']([^"']+)["']/g,
    /\bimport\s*\(\s*["']([^"']+)["']\s*\)/g,
    /\bexport\s+[\s\S]*?\s+from\s+["']([^"']+)["']/g,
  ];
  for (const pattern of patterns) {
    for (const match of source.matchAll(pattern)) imports.push(match[1]);
  }
  return imports;
}

const entryPath = resolveLocalModule(path.resolve("dist/index.html"), moduleEntryMatch[1]);
const pendingModules = [entryPath];
const checkedModules = new Set();

while (pendingModules.length) {
  const modulePath = pendingModules.pop();
  if (!modulePath || checkedModules.has(modulePath)) continue;
  if (!fs.existsSync(modulePath)) {
    fail(`missing module in build output: ${path.relative(path.resolve("dist"), modulePath)}`);
  }
  checkedModules.add(modulePath);
  const source = fs.readFileSync(modulePath, "utf8");
  for (const specifier of localModuleSpecifiers(source)) {
    const dependencyPath = resolveLocalModule(modulePath, specifier);
    if (dependencyPath && !checkedModules.has(dependencyPath)) pendingModules.push(dependencyPath);
  }
}

console.log("✅ preview check passed");
console.log(`- verified output files: ${requiredOutputFiles.join(", ")}`);
console.log(`- verified module graph: ${checkedModules.size} files`);
