"""
批量生成所有模板的 LAD FB + IO 映射 + 编译
逐个调用 gen_from_template.py 串行执行，输出写入日志文件
"""
import subprocess, sys, os, time

# 强制 UTF-8 输出，防止 pipe 编码崩溃
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

LOG_FILE = cfg.logging.batch_log

def log(msg):
    """安全打印到控制台和日志文件"""
    # 先确保写入日志（UTF-8 无问题）
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')
        f.flush()
    # 打印到控制台时用 backslashreplace 避免 GBK 崩溃
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        safe = msg.encode('utf-8', errors='backslashreplace').decode('utf-8')
        print(safe, flush=True)

# 初始化日志
with open(LOG_FILE, 'w', encoding='utf-8') as f:
    f.write(f"Batch Gen Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.flush()

from config_loader import cfg
DONE = set(cfg.generation.batch_skip)
TEMPLATES_DIR = cfg.generation.templates_dir
SCRIPT = os.path.join(os.path.dirname(__file__), 'gen_from_template.py')

# 收集模板
templates = []
for fname in sorted(os.listdir(TEMPLATES_DIR)):
    if fname.endswith('.json'):
        name = fname.replace('.json', '')
        if name not in DONE:
            templates.append(name)

total = len(templates)
log(f"[TOTAL] {total} 待生成 (已跳过: 电机正反转)")
log("")

failures = []
for i, name in enumerate(templates, 1):
    log(f"\n{'='*60}")
    log(f"  [{i}/{total}] {name}")
    log(f"{'='*60}")

    start = time.time()
    try:
        proc = subprocess.Popen(
            [sys.executable, SCRIPT, name],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding='utf-8', errors='replace',
            bufsize=1,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
        )
        for line in proc.stdout:
            log(line.rstrip('\n\r'))
        proc.wait(timeout=300)
        retcode = proc.returncode
    except subprocess.TimeoutExpired:
        log(f"  [TIMEOUT] {name} 超时 300s")
        failures.append(name)
        proc.kill()
        continue
    except Exception as e:
        log(f"  [ERROR] {name}: {str(e).encode('ascii', errors='backslashreplace').decode('ascii')}")
        failures.append(name)
        continue

    elapsed = time.time() - start
    log(f"  [TIME] {elapsed:.0f}s")

    if retcode != 0:
        log(f"  [FAIL] {name} (code={retcode})")
        failures.append(name)
    else:
        log(f"  [OK] {name} 完成")

log("")
log("=" * 60)
if failures:
    log(f"[DONE] 完成 {total - len(failures)}/{total}，失败 {len(failures)} 个:")
    for f in failures:
        log(f"  - {f}")
else:
    log(f"[DONE] 全部 {total} 个模板处理完毕！")
log("=" * 60)
