# Delta Spec: secret-management

> 基线: `openspec/specs/` 中无独立 spec

## MODIFIED Requirements

### R1 · SECRET_KEY 并发生成锁超时增强（更新）

`_ensure_secret_key` 的文件锁等待 SHALL 增加到 50×0.2s（共 10 秒），并 SHALL 检测并清理超过 30 秒的僵尸锁文件。

**行为要求**：
- 锁等待循环：50 次迭代，每次 `time.sleep(0.2)`，共 10 秒。
- 在尝试获取锁前，检查锁文件修改时间。若 `time.time() - os.path.getmtime(lock_path) > 30`，视为僵尸锁，删除后立即尝试获取。
- 僵尸锁清理后重新尝试 `O_CREAT | O_EXCL`，不进入等待循环。

#### Scenario: SMB 挂载下首启动成功获取锁
- **GIVEN** `data/config.yaml` 在 SMB 挂载目录，写入延迟 3 秒
- **WHEN** 两个进程同时首次启动
- **THEN** 先获取锁的进程在 3 秒内完成写入
- **AND** 后获取锁的进程在 10 秒等待内读取到已写入的密钥

#### Scenario: 进程崩溃后僵尸锁清理
- **GIVEN** 进程 A 获取锁后崩溃，锁文件残留
- **WHEN** 进程 B 启动，发现锁文件存在超过 30 秒
- **THEN** 进程 B 删除僵尸锁，重新获取锁并生成密钥
