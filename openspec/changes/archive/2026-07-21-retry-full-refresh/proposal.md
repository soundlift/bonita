## Why

Records 页面有两个"重试"入口(工具栏批量重试、操作列单条重试),但它们当前只是"用旧数据重跑转移",不会重新解析编号、不会重新刮削元数据、不清理旧的目标文件。这导致用户修改文件名后、或刮削规则升级后,重试无法修正已有的错误编号和过期元数据——重试看起来"成功了"但结果不变,令人困惑。两个入口的语义需要统一为真正的「完全重新开始」,并且不丢失审计信息(创建时间)和用户意图(指定的刮削源/URL)。

## What Changes

- **BREAKING**: 两个重试入口(批量 `POST /records/retry`、单条 `POST /tasks/run/{id}` 带 path)SHALL 统一执行「完全重新开始」语义:重新解析文件名编号、删除旧的目标文件、强制重新网络刮削元数据。
- `celery_transfer_group` 任务签名 SHALL 新增 `force_refresh: bool = False` 参数,带默认值以保持向后兼容(旧调用方不受影响)。
- `celery_scrapping` 任务签名 SHALL 新增 `force_refresh: bool = False` 参数。当为 True 时:ExtraInfo 已存在也重新解析 number/tag/partNumber(保留 specifiedsource/specifiedurl/crop);跳过 Metadata 本地缓存,强制走 `scraping()` 网络抓取。
- 重试 SHALL 保留 `TransRecords.createtime` 的原始值(SQLAlchemy `default` 语义天然保护,spec 显式约束防止回归)。
- 重试 SHALL 保留 `ExtraInfo.specifiedsource`、`specifiedurl`、用户已设置的 `crop`。
- 单条重试入口(`POST /tasks/run/{id}` 的 path 分支)SHALL 触发 force_refresh;整任务重跑(path 为空)不触发,保持原有"扫描全量"语义。
- 前端重试确认对话框文案 SHALL 明确告知用户"将重新解析编号、重新刮削、删除旧文件",避免用户误以为是轻量重试。

## Capabilities

### New Capabilities
- `task-rerun-refresh`: 覆盖单条记录重试入口(`POST /tasks/run/{id}` 带 path)的 force_refresh 语义,以及 `celery_transfer_group` / `celery_scrapping` 任务在 force_refresh 模式下的处理契约(重新解析编号、删旧文件、强制网络刮削、保留审计字段)。

### Modified Capabilities
- `records-batch-retry`: 强化批量重试的需求——从"提交 celery_transfer_group 任务"升级为"提交任务且 force_refresh=True",并增加 createtime/用户意图字段的保留约束。

## Impact

- **后端核心改动**:`backend/bonita/celery_tasks/tasks.py`(两个 celery 任务签名 + 删文件逻辑 + 刷新字段逻辑)、`backend/bonita/services/record_service.py`(`retry_records` 传参)、`backend/bonita/api/routes/tasks.py`(`run_transfer_task` 的 path 分支传参)。
- **前端文案**:`frontend/src/pages/Records.vue`(重试确认对话框文案)、`frontend/src/plugins/i18n/locales/{en,zh}.ts`。
- **依赖系统**:Celery worker 需重启以加载新任务签名(参数有默认值,旧消息兼容)。
- **外部副作用**:重试会产生网络刮削请求(可能增加刮削站点负载);会删除旧的目标文件(用户已通过确认对话框知情)。
- **风险**:网络抓取失败可能导致原本缓存成功的记录重试后失败——这是"完全重新开始"的固有代价,record.success 会如实反映。
