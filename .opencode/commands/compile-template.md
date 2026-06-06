# project:compile-template — 编译 CartGen 模板

编译指定模板名到 TIA Portal 并验证。

## 参数
- TEMPLATE_NAME：模板中文名（如 "电机正反转"、"传送带控制"）

## 可用模板（18 个）

### 电机控制类
电机正反转、星三角启动、多电机顺序启动、单键启停

### 传送输送类
传送带控制、输送带分拣、小车往复3次

### 阀门泵类
阀门控制、水泵控制、灌装机控制

### 建筑设施类
2层电梯、停车场道闸、自动门控制、暖通空调风机

### 报警/其他
报警灯控制、8位抢答器、手动自动切换、气缸往复

## 步骤

### 1. 生成模板 XML
- RUN python mcp-servers/tia-mcp/gen_from_template.py $TEMPLATE_NAME

### 2. 编译验证
- RUN python mcp-servers/tia-mcp/test_full_flow.py

### 3. 返回结果
返回编译状态（State / Errors / Warnings）。
