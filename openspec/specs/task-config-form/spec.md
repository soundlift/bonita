# task-config-form Specification

## Purpose
TBD - created by archiving change transfer-safety-transaction. Update Purpose after archive.
## Requirements
### Requirement: 任务配置表单 SHALL 对移动操作模式展示风险提示

`TransferConfigDetailForm.vue` 的操作方式选择器（`VRadioGroup` inline 模式）SHALL 在用户选中"移动"（value=3）时，在选择器下方渲染一段警告色说明文字。文案 SHALL 明确告知移动模式会删除源文件，且转移过程中刮削或磁盘出错时源文件不可恢复，并 SHALL 推荐用户优先使用硬链接。

当操作方式为硬链接(1)/软链接(2)/复制(4)时，风险提示 SHALL NOT 显示。

i18n key SHALL 为 `components.task.form.moveWarning`，SHALL 在 `zh.ts` 和 `en.ts` 中同步维护。

#### Scenario: 选中移动时显示风险提示

- **WHEN** 用户在任务配置表单中选中操作方式为"移动"（value=3）
- **THEN** 表单 SHALL 在操作方式选择器下方显示警告色（warning/error）的说明文字，包含"删除源文件""不可恢复""建议硬链接"关键信息

#### Scenario: 选中其他模式时不显示风险提示

- **WHEN** 用户选中操作方式为硬链接/软链接/复制
- **THEN** 表单 SHALL NOT 显示移动风险提示

