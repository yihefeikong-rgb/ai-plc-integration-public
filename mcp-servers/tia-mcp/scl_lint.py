"""
SCL 外部源代码静态校验器

在导入 TIA Portal 前对 SCL 代码做正则检查，拦截已知会导致编译失败的写法。
规则来源: plc-code-templates/siemens-scl/_rules.md（基于 TIA V21 实测）

用法:
    from scl_lint import lint_scl
    errors = lint_scl(scl_code)
    if errors:
        for e in errors:
            print(f"L{e['line']}: {e['rule']} - {e['message']}")
"""

import re
from typing import List, Dict


# ═══════════════════════════════════════════════════════════════
# 预处理：消除假阳性来源（字符串字面量 / 块注释 / 行注释）
# ═══════════════════════════════════════════════════════════════

def _strip_strings_and_comments(code: str) -> str:
    """将字符串字面量、块注释、行注释替换为等长空格，保留行号。

    消除假阳性：正则不扫描这些区域内的关键字。
    假阴性由后续的 _flatten_function_calls 处理。
    """
    result = list(code)

    # ── Pass 1: 块注释 (* ... *) ──
    i = 0
    while i < len(result) - 1:
        if result[i] == '(' and result[i + 1] == '*':
            j = i + 2
            while j < len(result) - 1:
                if result[j] == '*' and result[j + 1] == ')':
                    j += 2
                    break
                j += 1
            for k in range(i, min(j, len(result))):
                if result[k] != '\n':
                    result[k] = ' '
            i = j
        else:
            i += 1

    # ── Pass 2: 行注释 // ──
    i = 0
    while i < len(result) - 1:
        if result[i] == '/' and result[i + 1] == '/':
            j = i
            while j < len(result) and result[j] != '\n':
                result[j] = ' '
                j += 1
            i = j
        else:
            i += 1

    # ── Pass 3: 字符串字面量 '...'（含 '' 转义） ──
    i = 0
    while i < len(result):
        if result[i] == "'":
            j = i + 1
            while j < len(result):
                if result[j] == "'":
                    if j + 1 < len(result) and result[j + 1] == "'":
                        # '' 转义 = 单引号字面量
                        j += 2
                        continue
                    else:
                        j += 1  # 包含闭合引号
                        break
                elif result[j] == '\n':
                    break  # 未闭合字符串，停止
                j += 1
            for k in range(i, min(j, len(result))):
                if result[k] != '\n':
                    result[k] = ' '
            i = j
        else:
            i += 1

    return ''.join(result)


def _flatten_function_calls(code: str) -> str:
    """将跨行函数调用/表达式括号合并为单行，便于正则检测。

    找出所有 '(' ... 匹配的 ')' 之间的内容（支持嵌套括号），
    将中间换行替换为空格。
    行号不受影响（后续行清空但保留行号占位）。
    """
    lines = list(code.split('\n'))
    n = len(lines)
    skip_until = 0  # 跳过被合并的行

    for i in range(n):
        if i < skip_until:
            continue
        line = lines[i]

        # 计算该行的括号深度
        depth = 0
        for ch in line:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth = max(0, depth - 1)

        if depth == 0:
            continue

        # 有未闭合的 '('：向下扫描直到闭合
        j = i + 1
        while j < n and depth > 0:
            for ch in lines[j]:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        break
            j += 1

        if depth == 0 and j > i + 1:
            # 合并 lines[i] 到 lines[j-1]
            merged = lines[i]
            for k in range(i + 1, j):
                merged += ' ' + lines[k]
            lines[i] = merged
            for k in range(i + 1, j):
                lines[k] = ''
            skip_until = j

    return '\n'.join(lines)


def lint_scl(scl_code: str) -> List[Dict[str, object]]:
    """校验 SCL 代码，返回违规列表。

    Args:
        scl_code: SCL 源代码字符串

    Returns:
        list[dict]: 违规列表，每条含 rule/line/message
        - rule: 规则标识符 (str)
        - line: 违规行号 (int, 1-indexed)
        - message: 人类可读描述 (str)
    """
    if not scl_code or not scl_code.strip():
        return []

    # ── 预处理：消除假阳性来源 ──
    cleaned = _strip_strings_and_comments(scl_code)

    errors: List[Dict[str, object]] = []

    # ── 辅助：在变量区内查找带长度的 String/WString ──
    errors.extend(_check_no_string_len_in_var(cleaned))
    # ── 辅助：IEC 实例调用无 # 前缀 ──
    errors.extend(_check_iec_instance_without_hash(cleaned))
    # ── 辅助：TSEND_C / TRCV_C 出现 EN/ENO ──
    errors.extend(_check_tsend_en_eno(cleaned))
    # ── 辅助：MB_CLIENT 出现在外部源 ──
    errors.extend(_check_mb_client_in_scl(cleaned))
    # ── 辅助：IF/CASE/FOR/WHILE/REPEAT 不成对 ──
    errors.extend(_check_unpaired_block(cleaned))
    # ── 辅助：Output 形参误用 := ──
    errors.extend(_check_output_with_colon_eq(cleaned))

    # 按行号排序
    errors.sort(key=lambda e: e["line"])  # type: ignore[return-value]
    return errors


# ═══════════════════════════════════════════════════════════════
# 规则 1: VAR_INPUT/VAR_IN_OUT 内禁止 String[n]/WString[n]
# ═══════════════════════════════════════════════════════════════

_VAR_INPUT_RE = re.compile(
    r'(VAR_INPUT|VAR_IN_OUT)\s*\n', re.IGNORECASE
)
_END_VAR_RE = re.compile(r'^\s*END_VAR\s*$', re.IGNORECASE)
_STRING_LEN_RE = re.compile(
    r'\b(String|WString)\s*\[\s*\d+\s*\]', re.IGNORECASE
)
_VAR_TEMP_RE = re.compile(r'^\s*VAR_TEMP\s*$', re.IGNORECASE)


def _check_no_string_len_in_var(scl_code: str) -> List[Dict[str, object]]:
    """检查 VAR_INPUT/VAR_IN_OUT 中是否包含 String[n]/WString[n]"""
    errors = []
    lines = scl_code.split("\n")
    in_forbidden_var = False
    nesting = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip().upper()

        if re.match(r'^\s*VAR_INPUT\s*$', line, re.IGNORECASE):
            in_forbidden_var = True
            nesting = 0
            continue
        if re.match(r'^\s*VAR_IN_OUT\s*$', line, re.IGNORECASE):
            in_forbidden_var = True
            nesting = 0
            continue
        if re.match(r'^\s*VAR_TEMP\s*$', line, re.IGNORECASE):
            in_forbidden_var = False
            continue
        if re.match(r'^\s*VAR\s*$', line, re.IGNORECASE):
            in_forbidden_var = False
            continue
        if re.match(r'^\s*VAR_OUTPUT\s*$', line, re.IGNORECASE):
            in_forbidden_var = False
            continue
        if re.match(r'^\s*VAR_CONSTANT\s*$', line, re.IGNORECASE):
            in_forbidden_var = False
            continue

        if in_forbidden_var:
            # 跟踪嵌套（结构体的 VAR_INPUT 内部有子结构的 END_VAR）
            if re.match(r'^\s*(VAR_INPUT|VAR_IN_OUT|VAR_OUTPUT|VAR_TEMP|VAR\b)', line, re.IGNORECASE):
                nesting += 1
            if re.match(r'^\s*END_VAR\s*$', line, re.IGNORECASE):
                if nesting > 0:
                    nesting -= 1
                else:
                    in_forbidden_var = False

            match = _STRING_LEN_RE.search(line)
            if match:
                errors.append({
                    "rule": "NO_STRING_LEN_IN_VAR",
                    "line": i,
                    "message": f"VAR_INPUT/VAR_IN_OUT 中禁止带长度: {match.group(0)}，应改为 {match.group(1)}（无长度）",
                })

    return errors


# ═══════════════════════════════════════════════════════════════
# 规则 2: IEC 实例调用无 # 前缀
# ═══════════════════════════════════════════════════════════════

# 匹配 IEC 标准函数实例调用（无 # 前缀）
_IEC_INSTANCE_NAMES = {
    "TON", "TON_TIME", "TOF", "TOF_TIME", "TP", "TP_TIME",
    "R_TRIG", "F_TRIG",
    "CTU", "CTD", "CTUD", "CTU_INT", "CTD_INT", "CTUD_INT",
    "TSEND_C", "TRCV_C", "TCON", "TDISCON",
    "MB_COMM_LOAD", "MB_MASTER", "MB_SLAVE", "MB_SERVER",
}

# 匹配 非#前缀 的 IEC 实例调用: 标识符( ... )
_IEC_CALL_WITHOUT_HASH_RE = re.compile(
    r'(?<![#\w])(\w+)\s*\(\s*(IN\s*:=|CLK\s*:=|CU\s*:=|CD\s*:=|REQ\s*:=|EN_R\s*:=|CONT\s*:=|PT\s*:=)',
    re.IGNORECASE,
)

# 空调用 like ton() / ton ();
_EMPTY_IEC_CALL_RE = re.compile(
    r'(?<![#\w])(\w+)\s*\(\s*\)',
    re.IGNORECASE,
)


def _check_iec_instance_without_hash(scl_code: str) -> List[Dict[str, object]]:
    """检查 IEC 实例调用是否缺少 # 前缀"""
    errors = []
    lines = scl_code.split("\n")

    for i, line in enumerate(lines, 1):
        # 跳过注释行
        if line.strip().startswith("//"):
            # 但仍检查行末注释前的代码
            code_part = line
        else:
            code_part = line

        # 去掉行末注释
        comment_pos = code_part.find("//")
        if comment_pos >= 0:
            # 确保不在字符串中
            code_part = code_part[:comment_pos]

        # 检查空调用
        for m_empty in _EMPTY_IEC_CALL_RE.finditer(code_part):
            name = m_empty.group(1)
            if name.upper() in _IEC_INSTANCE_NAMES:
                errors.append({
                    "rule": "IEC_INSTANCE_WITHOUT_HASH",
                    "line": i,
                    "message": f"IEC 实例 '{name}()' 空调用（缺少 IN/PT 等形参），且缺少 # 前缀",
                })

        # 检查缺少 # 前缀的调用
        for m_call in _IEC_CALL_WITHOUT_HASH_RE.finditer(code_part):
            name = m_call.group(1)
            if name.upper() in _IEC_INSTANCE_NAMES:
                # 排除：变量声明行（: TON; 等）
                before = code_part[:m_call.start()]
                if re.search(r':\s*$', before):
                    continue
                # 排除：已经是 #实例.成员 访问
                if re.search(r'#\w+\.' + re.escape(name), code_part, re.IGNORECASE):
                    continue
                errors.append({
                    "rule": "IEC_INSTANCE_WITHOUT_HASH",
                    "line": i,
                    "message": f"IEC 实例 '{name}' 调用缺少 # 前缀，应改为 #{name.lower()}(...)",
                })

    return errors


# ═══════════════════════════════════════════════════════════════
# 规则 3: TSEND_C/TRCV_C 不允许出现 EN/ENO
# ═══════════════════════════════════════════════════════════════

_TSEND_EN_RE = re.compile(
    r'\b(EN\s*:=|ENO\s*=>)',
    re.IGNORECASE,
)

# IEC 实例名（FB 成员声明的变量名用于 TSEND_C/TRCV_C）
_TSEND_TRCV_RE = re.compile(
    r'\b(TSEND_C|TRCV_C)\b', re.IGNORECASE,
)


def _check_tsend_en_eno(scl_code: str) -> List[Dict[str, object]]:
    """检查 TSEND_C/TRCV_C 中是否出现 EN := 或 ENO =>

    策略：先用 _flatten_function_calls 把跨行调用合并为单行，
    然后在合并后的代码中按行检测。合并只在当前规则内做，不影响原始行号。
    """
    errors = []
    # 合并跨行调用，保留原始行号
    flat = _flatten_function_calls(scl_code)
    lines = flat.split("\n")

    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        # 如果在函数调用括号中出现了 EN:= 或 ENO=>
        # 匹配 (... EN := ...) 或 (... ENO => ...)
        for m in re.finditer(
            r'\(\s*([^()]*(?:\([^()]*\)[^()]*)*)\s*\)', line
        ):
            params_block = m.group(1)
            for pm in _TSEND_EN_RE.finditer(params_block):
                errors.append({
                    "rule": "TSEND_EN_ENO",
                    "line": i,
                    "message": f"调用中出现 {pm.group(0).strip()}，SCL 外部源不允许 EN/ENO 形参",
                })

    return errors


# ═══════════════════════════════════════════════════════════════
# 规则 4: 外部源中不允许 MB_CLIENT
# ═══════════════════════════════════════════════════════════════

_MB_CLIENT_RE = re.compile(r'\bMB_CLIENT\b', re.IGNORECASE)


def _check_mb_client_in_scl(scl_code: str) -> List[Dict[str, object]]:
    """检查 SCL 外部源中是否出现 MB_CLIENT"""
    errors = []
    lines = scl_code.split("\n")

    for i, line in enumerate(lines, 1):
        code = line.split("//")[0]
        for m in _MB_CLIENT_RE.finditer(code):
            errors.append({
                "rule": "MB_CLIENT_IN_SCL",
                "line": i,
                "message": "外部源 SCL 中不允许 MB_CLIENT（导入时全引脚 Invalid data type），请用 TSEND_C/TRCV_C 替代",
            })

    return errors


# ═══════════════════════════════════════════════════════════════
# 规则 5: IF/CASE/FOR/WHILE/REPEAT 不成对闭合
# ═══════════════════════════════════════════════════════════════

_OPEN_BLOCK_RE = re.compile(
    r'\b(IF|CASE|FOR|WHILE|REPEAT)\b', re.IGNORECASE
)
_CLOSE_BLOCK_RE = re.compile(
    r'\b(END_IF|END_CASE|END_FOR|END_WHILE|END_REPEAT)\b', re.IGNORECASE
)

_BLOCK_PAIRS = {
    "IF": "END_IF",
    "CASE": "END_CASE",
    "FOR": "END_FOR",
    "WHILE": "END_WHILE",
    "REPEAT": "END_REPEAT",
}


def _check_unpaired_block(scl_code: str) -> List[Dict[str, object]]:
    """检查控制结构是否成对闭合（使用简单栈计数）"""
    stack = []
    lines = scl_code.split("\n")

    for i, line in enumerate(lines, 1):
        code = line.split("//")[0]
        # 找所有开/闭关键词
        tokens = re.findall(
            r'\b(IF|CASE|FOR|WHILE|REPEAT|END_IF|END_CASE|END_FOR|END_WHILE|END_REPEAT)\b',
            code, re.IGNORECASE,
        )
        for token in tokens:
            upper = token.upper()
            if upper in _BLOCK_PAIRS:
                stack.append((upper, i))
            elif upper.startswith("END_"):
                expected_close = None
                # 找栈顶最近未闭合的块
                for close_key, expect_end in _BLOCK_PAIRS.items():
                    if expect_end == upper:
                        expected_close = close_key
                        break
                if not stack:
                    errors = [{
                        "rule": "UNPAIRED_BLOCK",
                        "line": i,
                        "message": f"多余的 {upper}，没有对应开语句",
                    }]
                    return errors
                if stack[-1][0] != expected_close:
                    errors = [{
                        "rule": "UNPAIRED_BLOCK",
                        "line": i,
                        "message": f"{upper} 与 {stack[-1][0]}（第{stack[-1][1]}行）不匹配，期望 {_BLOCK_PAIRS.get(stack[-1][0], '?')}",
                    }]
                    return errors
                stack.pop()

    if stack:
        return [{
            "rule": "UNPAIRED_BLOCK",
            "line": stack[-1][1],
            "message": f"{stack[-1][0]}（第{stack[-1][1]}行）缺少对应的闭合 {_BLOCK_PAIRS.get(stack[-1][0], '?')}",
        }]
    return []


# ═══════════════════════════════════════════════════════════════
# 规则 6: Output 形参用 := 而非 =>
# ═══════════════════════════════════════════════════════════════

# 匹配块调用中 Output 方向形参被绑定为 := 的情况
# 形如: #fb(OUTPUT_PARAM := value) 或 "FC"(OUTPUT := x)
# 我们检测传参时的 ":=" — 但无法在静态分析中区分 Input 和 Output
# 策略：检测常见 IUO 模式中明确的 Output 形参名被错误用 := 绑定

# 系统 FC/FB 的已知 OUTPUT 形参名
_KNOWN_OUTPUT_PARAMS = {
    "DONE", "BUSY", "ERROR", "STATUS", "NDR", "RCVD_LEN",
    "RET_VAL", "OUT", "Q", "ET", "CV",
}

# 匹配非函数调用的 := 绑定 形如 #inst.Param 或 "FC".Param
# 这里我们追查 常见模式：在调用括号内的 := 绑定到已知 Output 名
_OUTPUT_WITH_COLON_EQ_RE = re.compile(
    r'(\w+)\s*:=',
    re.IGNORECASE,
)


def _check_output_with_colon_eq(scl_code: str) -> List[Dict[str, object]]:
    """检查块调用中 Output 形参是否误用 :=（应使用 =>）

    这是启发式规则：当函数调用的参数列表中，参数名是已知 Output 形参名
    且用了 := 而非 =>，判定为错误。
    """
    errors = []
    # 合并跨行调用，保留原始行号
    flat = _flatten_function_calls(scl_code)
    lines = flat.split("\n")

    # 匹配函数调用：标识符( ... )
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue

        # 找函数调用中的参数绑定：ParamName := value
        for m in re.finditer(
            r'\(\s*([^()]*(?:\([^()]*\)[^()]*)*)\s*\)', line
        ):
            params_block = m.group(1)
            for pm in re.finditer(
                r'(?<![#\w])(\w+)\s*:=',
                params_block,
            ):
                pname = pm.group(1).upper()
                if pname in _KNOWN_OUTPUT_PARAMS:
                    errors.append({
                        "rule": "OUTPUT_WITH_COLON_EQ",
                        "line": i,
                        "message": f"Output 形参 '{pm.group(1)}' 误用 :=，应改为 =>",
                    })

    return errors
