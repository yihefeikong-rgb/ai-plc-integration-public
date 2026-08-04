let meta = #{
    name: "review-changes",
    description: "对目标改动/模块做多维度并行审查（正确性 / 错误处理 / 性能 / 安全），再由独立质疑者对抗验证每条发现，只输出有证据支撑的结论。支持多个模块路径分片审查。",
    when_to_use: "当需要对 diff、分支、提交、目录或多个模块做一次较全面的代码审查时",
    phases: [
        #{ title: "Review", detail: "每个模块 × 每个维度一个审查者" },
        #{ title: "Verify", detail: "每条发现一个质疑者" },
    ],
};

let findings_schema = #{
    "type": "object", "required": ["findings"],
    "properties": #{
        "findings": #{ "type": "array", "maxItems": 8, "items": #{
            "type": "object", "required": ["file", "issue", "severity"],
            "properties": #{
                "file": #{ "type": "string" },
                "issue": #{ "type": "string" },
                "severity": #{ "type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"] },
            },
        }},
    },
};

let verdict_schema = #{
    "type": "object", "required": ["real", "reason", "evidence"],
    "properties": #{
        "real": #{ "type": "boolean" },
        "reason": #{ "type": "string" },
        "evidence": #{ "type": "string" },
    },
};

// 守卫 args：未传 targets/target 时暂停等待，而不是直接报错。
let targets = if args == () { () } else { args.targets };
if targets == () {
    let single = if args == () { () } else { args.target };
    if single == () { pause("verification", "请传入 args.targets（模块路径数组）或 args.target（单个路径）。"); }
    targets = [ single ];
}

let dimensions = [
    #{ name: "正确性 bugs（逻辑错误、越界、竞态、边界条件）", label: "correctness" },
    #{ name: "错误处理缺口（异常吞掉、失败路径未处理、错误信息泄露敏感信息）", label: "error-handling" },
    #{ name: "性能问题（无意义重复计算、N+1、不必要阻塞）", label: "performance" },
    #{ name: "安全与控制边界问题（认证/令牌/审计链绕过、未校验输入、敏感信息硬编码、急停与安全逻辑被触碰、危险操作缺少确认）", label: "security" },
];

phase("Review");
let jobs = [];
for t in targets {
    for d in dimensions {
        jobs.push(#{
            prompt: "用只读工具实际审查模块 " + t + " 中的" + d.name + "。使用 list_dir 列出该路径下的源码，用 read_file、grep 检查真实代码，不要凭记忆回答。"
                + "忽略 node_modules、__pycache__、dist、release、*.pyc、*.dll、*.bin 等非源码产物；.cs 等生成代码不必深究，聚焦 .py/.js/.jsx/.ts/.scl 源码与配置文件。"
                + "最多报告 8 条具体发现，每条为 {file, issue, severity}，file 用相对项目根的路径，severity 取 CRITICAL / HIGH / MEDIUM / LOW；"
                + "只有在你确实读过相关代码后才能返回空列表，空列表是合法答案。",
            label: "review:" + t + ":" + d.label,
            capability_mode: "read-only",
            output_schema: findings_schema,
        });
    }
}
log("审查阶段将派出 " + jobs.len().to_string() + " 个子代理（" + targets.len().to_string() + " 模块 × 4 维度）");
let results = parallel(jobs);

let findings = [];
for r in results {
    if r != () && r.success && r.output.findings != () {
        for f in r.output.findings { findings.push(f); }
    }
}

// 按模块配额截断：从 file 推断模块前缀，每个模块最多保留 MAX_PER_MODULE 条，
// 防止某个模块发现过多挤掉其他模块（此前全局截断导致后 16 个模块全部丢失）。
fn module_of(f) {
    let parts = f.file.split("/");
    if parts.len() >= 2 && (parts[0] == "mcp-servers" || parts[0] == "ai-plc-assistant") {
        return parts[0] + "/" + parts[1];
    }
    return parts[0];
}
let MAX_PER_MODULE = 8;
let counts = #{};
let kept = [];
let dropped = 0;
for f in findings {
    let m = module_of(f);
    if counts[m] == () { counts[m] = 0; }
    if counts[m] < MAX_PER_MODULE {
        counts[m] += 1;
        kept.push(f);
    } else {
        dropped += 1;
    }
}
log("按模块配额保留 " + kept.len().to_string() + " 条进入验证（丢弃超出配额的 " + dropped.to_string() + " 条）");
findings = kept;
if findings.len() == 0 { complete(#{ summary: "未发现任何问题（各模块各维度均确认）。", confirmed: [] }); }

phase("Verify");
let vjobs = [];
for f in findings {
    vjobs.push(#{
        prompt: "对抗性验证下面这条审查发现，必须实际读取代码确认，不能只凭审查者转述。发现：\"" + f.issue + "\"，文件：" + f.file
            + "，声称严重度：" + f.severity + "。只有在你能独立检查到具体证据（如具体行、调用链、配置项）时才设 real=true；"
            + "证据不足或无法复现一律设 real=false，reason 说明理由，evidence 给出你独立看到的证据。",
        label: "verify:" + f.file,
        capability_mode: "read-only",
        output_schema: verdict_schema,
    });
}
log("验证阶段将派出 " + vjobs.len().to_string() + " 个子代理");
let verdicts = parallel(vjobs);

let confirmed = [];
let i = 0;
for v in verdicts {
    if v != () && v.success && v.output.real == true
        && v.output.evidence != () && v.output.evidence != "" {
        confirmed.push(findings[i]);
    }
    i += 1;
}
log(confirmed.len().to_string() + "/" + findings.len().to_string() + " 条发现通过对抗验证");
complete(#{ summary: confirmed.len().to_string() + " 条确认发现（其余已被质疑者驳回）", confirmed: confirmed });
