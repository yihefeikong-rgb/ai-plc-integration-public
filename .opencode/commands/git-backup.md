# project:git-backup — 双仓库备份

推送到私有仓库和公开仓库。

## 步骤

### 1. 查看当前状态
- RUN git status

### 2. 添加并提交
- RUN git add -A
- RUN git commit -m "改动说明"

### 3. 推送到两个仓库
- RUN git push origin master
- RUN git push public master

## 仓库地址
- 私有（origin）：https://github.com/yihefeikong-rgb/ai-plc-integration
- 公开（public）：https://github.com/yihefeikong-rgb/ai-plc-integration-public

## 回滚规则
如果改动后不可用，回滚到最新仓库版本：
- RUN git reset --hard origin/master
