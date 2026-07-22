# Delta Spec: data-safety

> 基线: `openspec/specs/transfer-transaction-safety/spec.md`

## MODIFIED Requirements

### R1 · clean_others 路径规范化比较（更新）

`celery_clean_others` 在比较 DB `destpath` 与文件系统扫描路径时，SHALL 对两侧路径统一执行 `os.path.normcase(os.path.realpath(os.path.normpath()))` 规范化后再比较。

**行为要求**：
- 规范化函数 `_normalize(p)` 组合 `normpath`（消除 `./`/`//`）→ `realpath`（解析符号链接）→ `normcase`（统一大小写）。
- `known_paths` 集合由规范化后的 DB 路径构成。
- 扫描路径也规范化后再比较，移除 `dest not in known_paths` 的原始路径回退检查。

#### Scenario: 符号链接路径不导致误删
- **GIVEN** DB 中 `destpath = /mnt/link/movie.mp4`，实际文件 `/data/movie.mp4`，`/mnt/link` 是符号链接
- **WHEN** `clean_others` 扫描到 `/data/movie.mp4`
- **THEN** 规范化后两侧均为 `/data/movie.mp4`，匹配成功，不删除

#### Scenario: 路径大小写差异不导致误删（Windows）
- **GIVEN** DB 中 `destpath = C:/Media/Movie.mp4`，扫描路径 `c:/media/movie.mp4`
- **WHEN** `clean_others` 执行清理
- **THEN** `normcase` 统一为小写后匹配，不删除
