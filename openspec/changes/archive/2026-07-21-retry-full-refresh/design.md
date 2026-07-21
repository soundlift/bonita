## Context

Records 页面有两个重试入口,最终都调用 `celery_transfer_group` 任务:

- **批量重试**:`POST /records/retry` → `record_service.retry_records` → `celery_transfer_group.delay(task_conf, srcpath, True)`
- **单条重试**:操作列图标 → `POST /tasks/run/{id}` body `{path: srcpath}` → `celery_transfer_group.delay(task_dict, path, True)`

当前 `celery_transfer_group` 内部有两个分支:
- 刮削模式(`sc_enabled=True`):调用 `celery_scrapping` 获取元数据 → 转移文件
- 直接转移模式(`sc_enabled=False`):直接转移文件

`celery_scrapping` 内部对 ExtraInfo 和 Metadata 都有缓存优先逻辑——已存在的 ExtraInfo 不重新解析编号,本地有 Metadata 记录就不走网络。这导致重试时编号错误无法被修正、过期元数据无法被刷新。

## Goals / Non-Goals

**Goals:**
- 两个重试入口统一执行「完全重新开始」语义
- 重新解析文件名编号(number/tag/partNumber)
- 删除旧的目标文件,避免残留
- 强制重新网络刮削元数据,忽略本地缓存
- 保留审计字段(createtime)和用户意图字段(specifiedsource/specifiedurl/crop)
- 向后兼容:force_refresh 带默认值 False,不影响 monitor 自动入库和其他非重试调用方

**Non-Goals:**
- 不改造 `celery_transfer_entry`(整任务入口)的 force_refresh 支持——它扫全量,语义已隐含从头来
- 不新增前端 UI 选项(如"强制刷新"勾选框)——重试即完全重新开始,无需用户选择
- 不重构 ExtraInfo/Metadata 的数据模型
- 不改变 monitor 自动入库的流程(它调用 celery_transfer_group 时不传 force_refresh,走默认 False)

## Decisions

### 决策 1:通过 `force_refresh` 参数贯穿,而非新建独立任务

**选择**:给 `celery_transfer_group` 和 `celery_scrapping` 加 `force_refresh: bool = False` 参数。

**理由**:
- 重试与正常入库 95% 逻辑相同,只有三个卡点不同(编号刷新、删旧文件、强制网络)
- 新建独立任务会导致两条几乎相同的代码路径,维护成本高
- 参数带默认值,所有现有调用方(monitor、celery_transfer_entry)零改动

**备选方案(否决)**:
- 新建 `celery_retry_group` / `celery_rescrap` 独立任务:代码重复严重
- 在 record 上加 `needs_refresh` 标记,让任务自己判断:状态管理复杂,且无法区分"这次重试"和"下次正常入库"

### 决策 2:ExtraInfo 刷新策略——保留用户意图,只刷新解析字段

**选择**:force_refresh=True 且 ExtraInfo 已存在时,用 `FileNumInfo(file_path)` 重新解析,刷新 `number`/`tag`/`partNumber`,但保留 `specifiedsource`/`specifiedurl`/`crop`。

**理由**:
- `specifiedsource`/`specifiedurl` 是用户手动指定的刮削源/URL,代表用户意图,丢失会导致刮削行为改变
- `crop` 如果用户手动设置过(False/True),应尊重;只有 None(未设置)时才根据新 number 推断
- `number`/`tag`/`partNumber` 是从文件名解析的结果性数据,应当随文件名/解析规则更新

### 决策 3:Metadata 强制网络抓取——跳过缓存查询

**选择**:force_refresh=True 时,`celery_scrapping` 跳过 `session.query(Metadata).filter(number==...)` 分支,直接走 `scraping()` 网络抓取。

**理由**:
- 本地 Metadata 缓存可能本身就是错的(这是用户重试的常见动机)
- 网络抓取会拿到最新数据,符合"完全重新开始"语义
- 抓取结果仍会写入 Metadata 表(save_metadata 控制),不破坏缓存机制

**备选方案(否决)**:
- 删除旧 Metadata 记录再抓取:破坏性太强,其他记录可能引用同一 number
- 加缓存有效期:过度设计,重试场景需要的是确定性的强制刷新,不是时间触发

### 决策 4:删除旧 destpath 文件——无条件删除

**选择**:force_refresh=True 时,在 `celery_transfer_group` 处理每个文件的开头,如果 `record.destpath` 存在且文件存在,无条件删除(不判断新旧路径是否相同)。

**理由**:
- 现有逻辑(第 309-312 行)只在"新路径 ≠ 旧路径"时删旧文件——重新刮削后路径相同但封面/NFO 内容可能已变,旧文件残留会造成混淆
- 无条件删除确保目标目录干净,转移结果就是最新刮削的产物
- 用户已通过确认对话框知情(文案会明确说明删除旧文件)

### 决策 5:createtime 保护——依赖 SQLAlchemy 语义 + spec 约束

**选择**:不写冗余的"保存-恢复"代码,依赖 SQLAlchemy `default`(仅 INSERT 生效)的天然保护,在 spec 里显式写明约束。

**理由**:
- SQLAlchemy 的 `default=` 只在 INSERT 时触发,UPDATE 不改 createtime
- 代码里没有任何地方显式 `record.createtime = xxx`
- 加冗余保护代码反而引入复杂度和 bug 风险
- spec 约束让任何后续改动者都能看到这个不变量

### 决策 6:单条重试入口的 force_refresh 触发条件

**选择**:`POST /tasks/run/{id}` 端点中,仅当 `path_param.path` 非空时(即单条/子路径重跑)传 `force_refresh=True`;path 为空(整任务重跑)不传,走默认 False。

**理由**:
- records 页面的单条重试(`rerunThisRecord`)总是传 path,走的是子路径分支
- 整任务重跑从 Tasks 页面触发,语义是"重新扫描整个 source_folder",不应强制刷新所有已有记录
- 这样的条件触发保持两个页面的语义清晰分离

## Risks / Trade-offs

- **[网络抓取失败导致重试反而变差]** → record.success 如实设为 False,用户在页面看到失败状态可判断原因;scraping_sites 配置多源可提高成功率
- **[删除旧 destpath 后新转移失败导致文件丢失]** → 这是"完全重新开始"的固有代价,用户已通过确认对话框文案知情;失败时 record.success=False,用户可重新触发
- **[Celery worker 需重启加载新签名]** → 参数有默认值,重启前的旧消息仍能被处理(走 force_refresh=False);文档已说明部署流程
- **[批量重试触发大量网络请求]** → 现有批量重试已逐条提交任务,受 semaphore(MAX_CONCURRENT_TASKS)限制并发,网络压力可控
- **[force_refresh 透传增加函数签名复杂度]** → 只加一个 bool 参数,且有明确语义,可接受
