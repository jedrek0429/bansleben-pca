import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';

function parseArgs(argv) {
  const result = { root: '', baseUrl: '' };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--root') result.root = argv[++i] || '';
    else if (argv[i] === '--base-url') result.baseUrl = argv[++i] || '';
  }
  if (!result.root || !result.baseUrl) {
    throw new Error('Usage: node tools/check_accessibility.mjs --root <generated-root> --base-url <url>');
  }
  return result;
}

function findHtmlFiles(dir) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) results.push(...findHtmlFiles(full));
    else if (entry.isFile() && entry.name.endsWith('.html')) results.push(full);
  }
  return results.sort();
}

const args = parseArgs(process.argv.slice(2));
const root = path.resolve(args.root);
const baseUrl = args.baseUrl.replace(/\/$/, '');
const pages = findHtmlFiles(root);
if (!pages.length) throw new Error(`No HTML files found under ${root}`);

const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();
const failures = [];

for (const file of pages) {
  const relative = path.relative(root, file).split(path.sep).join('/');
  const route = relative === 'index.html'
    ? '/'
    : relative.endsWith('/index.html')
      ? `/${relative.slice(0, -'index.html'.length)}`
      : `/${relative}`;
  const url = `${baseUrl}${route}`;
  await page.goto(url, { waitUntil: 'networkidle' });
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const blocking = result.violations.filter((violation) => ['critical', 'serious'].includes(violation.impact));
  if (blocking.length) failures.push({ route, violations: blocking });
}

await browser.close();

if (failures.length) {
  for (const failure of failures) {
    console.error(`Accessibility violations on ${failure.route}:`);
    for (const violation of failure.violations) {
      console.error(`  ${violation.id} [${violation.impact}]: ${violation.help}`);
      for (const node of violation.nodes.slice(0, 5)) {
        console.error(`    ${node.target.join(' ')}`);
      }
    }
  }
  process.exit(1);
}

console.log(`Accessibility OK: ${pages.length} generated pages scanned for serious/critical WCAG A/AA violations.`);
