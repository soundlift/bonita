## ADDED Requirements

### Requirement: celery_transfer_group SHALL 支持 force_refresh 参数实现完全重新开始

`celery_transfer_group` 任务 SHALL 新增 `force_refresh: bool = False` 参数。当 `force_refresh=True` 时,任务 SHALL 在处理每个文件前无条件删除该记录已有的 `destpath` 指向的目标文件(若文件存在),然后将 `force_refresh` 透传给 `celery_scrapping` 任务。当 `force_refresh=False` 时(默认),行为 SHALL 与现有逻辑完全一致,不影响 monitor 自动入库和其他非重试调用方。

#### Scenario: force_refresh=True 时删除旧目标文件

- **WHEN** `celery_transfer_group` 以 `force_refresh=True` 调用,且某条记录的 `destpath` 指向的文件已存在
- **THEN** 任务 SHALL 在重新处理该文件前删除旧的目标文件,无论新旧路径是否相同

#### Scenario: force_refresh=False 时保持原有行为

- **WHEN** `celery_transfer_group` 以 `force_refresh=False`(默认)调用
- **THEN** 任务 SHALL 保持现有行为,仅在"新路径 ≠ 旧路径"时删除旧文件,不影响 monitor 自动入库流程

#### Scenario: 直接转移模式下 force_refresh 删除旧文件

- **WHEN** `force_refresh=True` 且任务配置为直接转移模式(`sc_enabled=False`),且记录有已存在的 `destpath`
- **THEN** 任务 SHALL 删除旧目标文件后重新执行转移

### Requirement: celery_scrapping SHALL 在 force_refresh 时重新解析编号并强制网络刮削

`celery_scrapping` 任务 SHALL 新增 `force_refresh: bool = False` 参数。当 `force_refresh=True` 且 ExtraInfo 记录已存在时,任务 SHALL 使用 `FileNumInfo(file_path)` 重新解析,刷新 `number`/`tag`/`partNumber` 字段,但 SHALL 保留 `specifiedsource`/`specifiedurl` 字段不变,且 SHALL 保留用户已设置的 `crop` 值(仅当 `crop` 为 None 时才根据新 number 推断)。

当 `force_refresh=True` 时,任务 SHALL 跳过本地 Metadata 缓存查询,直接调用 `scraping()` 进行网络抓取。

#### Scenario: force_refresh 时刷新编号但保留指定源

- **WHEN** `celery_scrapping` 以 `force_refresh=True` 调用,且 ExtraInfo 已存在(用户曾手动设置 `specifiedsource="javbus"`)
- **THEN** 任务 SHALL 用 `FileNumInfo` 重新解析并更新 `number`/`tag`/`partNumber`,但 SHALL 保留 `specifiedsource="javbus"` 不变

#### Scenario: force_refresh 时保留用户设置的 crop

- **WHEN** `celery_scrapping` 以 `force_refresh=True` 调用,且 ExtraInfo 已存在且 `crop=False`(用户手动设置)
- **THEN** 任务 SHALL 保留 `crop=False` 不变,不根据新 number 重新推断裁剪设置

#### Scenario: force_refresh 时 crop 为 None 则推断

- **WHEN** `celery_scrapping` 以 `force_refresh=True` 调用,且 ExtraInfo 已存在且 `crop=None`
- **THEN** 任务 SHALL 根据重新解析的 number 调用 `need_crop()` 推断 crop 值

#### Scenario: force_refresh 时强制网络刮削

- **WHEN** `celery_scrapping` 以 `force_refresh=True` 调用,且本地 Metadata 表中存在该 number 的缓存记录
- **THEN** 任务 SHALL 跳过缓存查询,直接调用 `scraping()` 进行网络抓取

### Requirement: 单条重试入口 SHALL 触发 force_refresh

`POST /tasks/run/{id}` 端点中,当 `path_param.path` 非空时(即单条/子路径重跑场景),SHALL 调用 `celery_transfer_group.delay(task_dict, path, True, force_refresh=True)`。当 `path_param.path` 为空时(整任务重跑场景),SHALL 保持现有行为,不触发 force_refresh。

#### Scenario: 单条重试触发完全重新开始

- **WHEN** 客户端调用 `POST /tasks/run/{id}` 且 body 中 `path` 非空(指向具体文件)
- **THEN** 后端 SHALL 调用 `celery_transfer_group` 且 `force_refresh=True`

#### Scenario: 整任务重跑不触发 force_refresh

- **WHEN** 客户端调用 `POST /tasks/run/{id}` 且 body 中 `path` 为空
- **THEN** 后端 SHALL 调用 `celery_transfer_entry`(整任务入口),不触发 force_refresh

### Requirement: 重试 SHALL 保留 TransRecords.createtime 原始值

任何重试流程(批量或单条)SHALL 保留 `TransRecords.createtime` 的原始值,不得因重新处理而刷新。此约束由 SQLAlchemy `default`(仅 INSERT 生效)的语义天然保护,并在 spec 中显式声明为不变量,防止后续代码改动引入回归。

#### Scenario: 重试后 createtime 不变

- **WHEN** 一条 createtime 为 "2026-07-01 10:00:00" 的记录被重试(批量或单条),重试流程完成
- **THEN** 该记录的 `createtime` SHALL 仍为 "2026-07-01 10:00:00",只有 `updatetime` 被刷新
