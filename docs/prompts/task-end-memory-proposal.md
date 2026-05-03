# 任务结束 — 知识沉淀提示词

请根据本次任务，总结是否有值得沉淀为长期项目知识的内容。

**先只列出候选项，不要调用 propose_memory。**

每条候选项包含：

- title：简洁具体的知识标题
- content：知识内容
- type：知识类型（code_pattern / architecture / business_rule / api / data_structure / troubleshooting 等）
- module：所属模块
- tags：相关标签
- reason：为什么值得保存

等待我确认后，再逐条调用 propose_memory。

注意：

- 不要包含密钥、token、密码、私钥
- 不要照搬大段源码（>50 行）
- 不要记录一次性任务过程
- 只记录长期有效的项目知识
