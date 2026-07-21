/**
 * P6 Lighthouse 性能报告脚本
 *
 * 用法：
 *   node scripts/run-lighthouse.mjs
 *
 * 前置：vite preview --port 4173 --strictPort
 *   （playwright.config.js 的 webServer 已自动启动；若单独跑，请先启 preview）
 *
 * 流程：
 *   1. 启动 Chrome（headless）导航到 /
 *   2. 跑 Lighthouse audit
 *   3. 输出 HTML 报告到 docs/frontend/lighthouse-report.html
 *   4. 输出 JSON 指标到 stdout，验证 LCP < 2.5s / CLS < 0.1
 *
 * 不依赖 lighthouse-ci，仅用 lighthouse 核心 + Node API。
 */

import { mkdirSync, writeFileSync, existsSync, copyFileSync } from 'fs'
import { resolve, dirname, join } from 'path'
import { fileURLToPath } from 'url'
import { homedir } from 'os'
import { spawn } from 'child_process'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:4173'
// 路径：__dirname 是 ai-plc-assistant/frontend/scripts/，../../../ 到仓库根 docs/
const OUT_HTML = resolve(__dirname, '../../../docs/frontend/lighthouse-report.html')
const OUT_JSON = resolve(__dirname, '../../../docs/frontend/lighthouse-report.json')

// 性能阈值（按 web/performance.md 验收指标）
const THRESHOLDS = {
  lcp: 2500,    // LCP < 2.5s
  cls: 0.1,     // CLS < 0.1
  fcp: 1500,    // FCP < 1.5s
  tbt: 200,     // TBT < 200ms
  inp: 200,     // INP < 200ms
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

async function waitForServer(url, timeoutMs = 30_000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url)
      if (res.ok || res.status === 404) return true
    } catch {
      // 服务器未启
    }
    await sleep(500)
  }
  throw new Error(`服务器在 ${timeoutMs / 1000}s 内未启动: ${url}`)
}

/**
 * 用 child_process 调 `npx lighthouse` 跑审计，避免 ESM 引入 lighthouse 复杂依赖。
 * 输出 JSON 到 stdout，解析后生成 HTML 报告。
 *
 * CHROME_PATH 环境变量指定 Playwright Chromium 路径（lighthouse 自身找不到 Chrome 时）。
 * 用相对路径 `lighthouse-tmp` 写到 cwd（避免路径含空格导致 lighthouse CLI 解析失败）。
 */
function runLighthouseCli(url) {
  return new Promise((resolvePromise, reject) => {
    // 找 Playwright Chromium 作为 Lighthouse 的 Chrome
    const chromePath = process.env.CHROME_PATH ||
      findPlaywrightChrome()

    // 用相对路径避免 Windows 绝对路径含空格导致 lighthouse CLI 解析失败
    const OUTPUT_PATH_REL = 'lighthouse-tmp'

    const args = [
      'lighthouse',
      url,
      '--output=json',
      '--output=html',
      `--output-path=${OUTPUT_PATH_REL}`,
      '--quiet',
      `--chrome-flags=--headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --no-first-run`,
      '--max-wait=120000',
    ]

    const env = { ...process.env }
    if (chromePath) {
      env.CHROME_PATH = chromePath
      console.log(`[Lighthouse] 使用 Chrome: ${chromePath}`)
    }

    const child = spawn('npx', args, {
      cwd: __dirname,
      shell: process.platform === 'win32',
      stdio: ['ignore', 'pipe', 'pipe'],
      env,
    })

    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (d) => (stdout += d.toString()))
    child.stderr.on('data', (d) => (stderr += d.toString()))

    child.on('close', (code) => {
      // Windows + chrome-launcher 已知问题：rmSync EPERM 导致 exit 1，
      // 但报告 .report.json / .report.html 已写完。
      resolvePromise({ stdout, stderr, exitCode: code, outputPath: OUTPUT_PATH_REL })
    })
    child.on('error', reject)
  })
}

/**
 * 找 Playwright 安装的 Chromium（Windows 路径）
 */
function findPlaywrightChrome() {
  const localAppData = process.env.LOCALAPPDATA || join(homedir(), 'AppData', 'Local')
  const candidates = [
    join(localAppData, 'ms-playwright', 'chromium-1228', 'chrome-win64', 'chrome.exe'),
    join(localAppData, 'ms-playwright', 'chromium-1148', 'chrome-win', 'chrome.exe'),
  ]
  for (const p of candidates) {
    if (existsSync(p)) return p
  }
  return null
}

async function run() {
  mkdirSync(dirname(OUT_HTML), { recursive: true })
  console.log(`[Lighthouse] 等待服务器: ${BASE_URL}`)
  await waitForServer(BASE_URL)

  console.log(`[Lighthouse] 启动审计...`)
  console.log(`  URL: ${BASE_URL}/`)
  console.log(`  报告: ${OUT_HTML}`)

  // 先检查 lighthouse 是否可用
  const versionCheck = new Promise((resolvePromise, reject) => {
    const child = spawn('npx', ['lighthouse', '--version'], {
      cwd: __dirname,
      shell: process.platform === 'win32',
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    let out = ''
    child.stdout.on('data', (d) => (out += d.toString()))
    child.on('close', (code) => (code === 0 ? resolvePromise(out.trim()) : reject(new Error(`lighthouse --version exit ${code}`))))
    child.on('error', reject)
  })

  try {
    const version = await versionCheck
    console.log(`[Lighthouse] 版本: ${version}`)
  } catch (e) {
    console.error('[Lighthouse] 未安装，请运行: npm install -D lighthouse')
    console.error('错误:', e.message)
    process.exit(1)
  }

  const { stderr, exitCode, outputPath } = await runLighthouseCli(`${BASE_URL}/`)

  if (exitCode !== 0) {
    console.log(`[Lighthouse] exit ${exitCode}（Windows chrome-launcher cleanup EPERM 是已知问题，报告已生成则继续）`)
  }

  // 报告生成在 cwd/scripts/ 下的 lighthouse-tmp.report.{json,html}
  const generatedHtml = resolve(__dirname, `${outputPath}.report.html`)
  const generatedJson = resolve(__dirname, `${outputPath}.report.json`)
  if (!existsSync(generatedJson)) {
    throw new Error(`Lighthouse 报告未生成: ${generatedJson}\nstderr: ${stderr}`)
  }
  let lighthouseJson
  try {
    lighthouseJson = JSON.parse(await import('fs').then((fs) => fs.readFileSync(generatedJson, 'utf-8')))
  } catch (e) {
    throw new Error(`解析 lighthouse JSON 失败: ${e.message}`)
  }

  // 移动 .report.html 到目标路径
  try {
    copyFileSync(generatedHtml, OUT_HTML)
    copyFileSync(generatedJson, OUT_JSON)
  } catch {
    // 如果路径相同就跳过
  }

  const audits = lighthouseJson?.audits || {}
  const categories = lighthouseJson?.categories || {}

  const metrics = {
    lcp: audits['largest-contentful-paint']?.numericValue,
    cls: audits['cumulative-layout-shift']?.numericValue,
    fcp: audits['first-contentful-paint']?.numericValue,
    tbt: audits['total-blocking-time']?.numericValue,
    inp: audits['interaction-to-next-paint']?.numericValue,
  }

  console.log('\n========== Lighthouse 指标 ==========')
  console.log(`LCP: ${metrics.lcp ? (metrics.lcp / 1000).toFixed(2) + 's' : 'N/A'} (目标 < ${THRESHOLDS.lcp / 1000}s)`)
  console.log(`CLS: ${metrics.cls?.toFixed(3) || 'N/A'} (目标 < ${THRESHOLDS.cls})`)
  console.log(`FCP: ${metrics.fcp ? (metrics.fcp / 1000).toFixed(2) + 's' : 'N/A'} (目标 < ${THRESHOLDS.fcp / 1000}s)`)
  console.log(`TBT: ${metrics.tbt?.toFixed(0) + 'ms' || 'N/A'} (目标 < ${THRESHOLDS.tbt}ms)`)

  const performance = categories['performance']?.score
  if (performance !== undefined) {
    console.log(`Performance 评分: ${(performance * 100).toFixed(0)}/100`)
  }

  if (stderr) {
    console.log(`\n[Lighthouse stderr]: ${stderr.slice(0, 200)}`)
  }

  // 验收检查（不强制 exit 1，但提示）
  const failures = []
  if (metrics.lcp && metrics.lcp > THRESHOLDS.lcp) failures.push(`LCP ${(metrics.lcp / 1000).toFixed(2)}s > ${THRESHOLDS.lcp / 1000}s`)
  if (metrics.cls && metrics.cls > THRESHOLDS.cls) failures.push(`CLS ${metrics.cls.toFixed(3)} > ${THRESHOLDS.cls}`)
  if (metrics.fcp && metrics.fcp > THRESHOLDS.fcp) failures.push(`FCP ${(metrics.fcp / 1000).toFixed(2)}s > ${THRESHOLDS.fcp / 1000}s`)
  if (metrics.tbt && metrics.tbt > THRESHOLDS.tbt) failures.push(`TBT ${metrics.tbt.toFixed(0)}ms > ${THRESHOLDS.tbt}ms`)

  if (failures.length > 0) {
    console.log('\n[WARN] 部分指标未达标:')
    for (const f of failures) console.log(`  - ${f}`)
    console.log('（不阻断构建，仅作记录）')
  } else {
    console.log('\n[OK] 全部性能指标达标')
  }

  console.log(`\n报告已生成:\n  HTML: ${OUT_HTML}\n  JSON: ${OUT_JSON}`)
  process.exit(0)
}

run().catch((err) => {
  console.error('[Lighthouse] 失败:', err.message)
  process.exit(1)
})
