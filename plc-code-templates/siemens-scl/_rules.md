# SCL 外部源强制规则

> 来源：TIA Portal V21 实测编译验证。违反任一条均可能导致编译失败。

## 1. 编码与文件

1. 文件必须 UTF-8 **无 BOM**（首字节不可为 EF BB BF），含 BOM 时报 `设定值"﻿"无效`
2. 扩展名 `.scl`，一个文件对应一个块（FC/FB/OB）
3. 可执行代码仅写在 FC/FB/OB 中；DB 不写 BEGIN...END 段
4. 重导同一块前必须先删除旧外部源，否则报 `name not unique`

## 2. 块接口（变量区）

5. VAR_INPUT 和 VAR_IN_OUT 中**禁止** `String[n]` / `WString[n]`，必须写 `String` 或 `WString`（无长度）
6. 块内调用 IEC 实例、读写实例成员、调用本 FB 内声明的系统 FB，**必须**带 `#` 前缀
7. IEC 定时器/边沿/计数器实例调用必须有 `#` 前缀：`#ton(IN:=..., PT:=...)` 而非 `ton(...)`

## 3. 形参绑定

8. 块调用 Input/InOut 形参用 `:=`，Output 形参用 `=>`
9. 对用户 FC/FB 的 VAR_OUTPUT 形参**禁止**使用 `:=`（应使用 `=>`）
10. T_DIFF 按函数返回值使用，**不要**写 `OUT =>` 或 `OUT :=` 作为第三形参

## 4. TSEND_C / TRCV_C

11. SCL 外部源中 TSEND_C/TRCV_C **禁止**出现 `EN :=` 或 `ENO =>`
12. TSEND_C/TRCV_C 成员访问必须 `#实例.DONE`、`#实例.BUSY`、`#实例.RCVD_LEN` 带 `#` 前缀

## 5. MB_CLIENT 硬限制

13. SCL 外部源中**禁止**使用 `MB_CLIENT`，外部源导入时不解析该系统 FB，报 `Invalid data type`（全引脚）
    - 替代方案：TSEND_C + TRCV_C 自组 Modbus TCP

## 6. 控制结构

14. 每个 IF/CASE/FOR/WHILE/REPEAT 必须有对应的 END_IF/END_CASE/END_FOR/END_WHILE/END_REPEAT 闭合
15. RETURN 可提前退出 FC/FB，不等于闭合控制结构

## 7. 类型与运算符

16. 整型与实型混合运算必须**显式转换**（如 INT_TO_REAL、REAL_TO_INT），不依赖隐式转换
17. IEC 实例每周期有且仅有一次有效调用（IN/CLK/PT 等形参齐全），禁止空调用 `ton()`

## 8. 编译报错速查

| 编译信息 | 原因 | 改法 |
|----------|------|------|
| 行 0 `设定值"﻿"无效` | UTF-8 BOM | 去掉 BOM 重新导入 |
| Invalid function name | 实例当全局调用（无 #） | 加 # 前缀 |
| Parameter 'IN' has to be used | 空调用 | 删除空调用 |
| Tag 'ton.Q' is not declared | 读成员未加 # | 改为 #ton.Q |
| Invalid parameter assignment | TSEND_C 写 EN:= | 去掉 EN/ENO |
| Compound part of instruction expected | VAR_INPUT 写 String[n] | 改为 String |
| Invalid data type (MB_CLIENT) | 外部源不解析 MB_CLIENT | 改用 TSEND_C/TRCV_C |
| name not unique | 重导未删旧外部源 | 先删旧外部源再导入 |
