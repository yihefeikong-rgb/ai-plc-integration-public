"""
全流水线验证：模板 JSON → CartGen → XML → 清理
"""
import json, os, subprocess, sys, tempfile

SCRIPT_DIR = os.path.dirname(__file__)
CARTGEN = os.path.join(SCRIPT_DIR, "CartGen", "CartGen.csproj")

# 测试所有 18 个模板
template_dir = os.path.join(SCRIPT_DIR, "templates")
templates = sorted([f for f in os.listdir(template_dir) if f.endswith('.json')])

print(f"=== 测试 CartGen 流水线: {len(templates)} 个模板 ===\n")
passed = 0
failed = []

for t in templates:
    json_path = os.path.join(template_dir, t)
    xml_path = json_path.replace('.json', '.xml')
    
    r = subprocess.run(
        ["dotnet", "run", "--project", CARTGEN, "--", json_path],
        capture_output=True, text=True, timeout=30
    )
    
    if r.returncode == 0 and os.path.exists(xml_path):
        size = os.path.getsize(xml_path)
        passed += 1
        print(f"  ✅ {t:30s} → {size:>6} bytes")
        os.unlink(xml_path)  # 清理
    else:
        err = r.stderr[:200] if r.stderr else r.stdout[:200]
        failed.append(t)
        print(f"  ❌ {t:30s} → {err}")

print(f"\n=== 结果: {passed}/{len(templates)} 通过 ===")
if failed:
    print(f"   失败: {failed}")
    
print("\n=== 验证 DeepSeek API 连通性 ===")
from config_loader import cfg
try:
    import requests
    resp = requests.post(
        cfg.deepseek.api_url,
        headers={"Authorization": f"Bearer {cfg.deepseek.api_key}",
                 "Content-Type": "application/json"},
        json={
            "model": cfg.deepseek.model,
            "messages": [{"role": "user", "content": "返回 JSON: {\"test\": \"ok\"}"}],
            "temperature": 0.1,
            "max_tokens": 100,
        },
        timeout=10,
    )
    if resp.status_code == 200:
        print("  ✅ DeepSeek API 连通")
    else:
        print(f"  ❌ DeepSeek API: HTTP {resp.status_code}")
except Exception as e:
    print(f"  ❌ DeepSeek API: {e}")
