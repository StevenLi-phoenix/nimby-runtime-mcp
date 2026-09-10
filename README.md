# NIMBY Rails Runtime MCP

通过 stdio MCP 调用运行时桥接，在游戏核心命令队列中执行原生操作。使用正常资金，不以屏幕坐标、剪贴板或离线存档编辑作为建设接口。

## 文档入口

**[AGENTS.md：项目主文档与索引](AGENTS.md)** 维护当前工作约束。详细操作参见：

- [创建一条线路：完整流程](docs/create-line.md)
- [OSM 数据与线路几何](docs/osm-data.md)
- [默认参数与接口支持范围](docs/defaults.md)
- [变更记录](CHANGELOG.md)

默认建设规则为地铁 Medium／地下、城间高铁 High speed／高架、普速 Medium／Ground；地铁禁止平交道岔，新站标签为 Name and pax。当前接口固定创建 Medium，High speed 尚待参数化，复杂地下立交也可能需要扩展层级／坡度接口，详见默认参数文档。

## 启动

仓库位于 `D:\Documents\Codes\nimby-runtime-mcp`，Python 使用 uv：

```powershell
uv sync --locked
uv run python server.py
```

`server.py` 是 stdio MCP 服务，须由 MCP 客户端连接；不是交互命令行或网络监听服务。首次游戏工具调用才附加唯一游戏进程。先载入目标世界，版本哈希由 `game_version.py` 检查；当前适配 NIMBY Rails 1.19.10.5bfaea3。

批处理可使用持久客户端，已有会话时复用，不再启动另一份：

```powershell
uv run python mcp_session.py
# 在另一个终端提交：
uv run python session_call.py runtime_status
```

文件队列中的请求仍经过标准 MCP `call_tool`。单连接租约禁止同时附加多个适配器；超时结果先核实再恢复，不自动重放建造或购车。

## 代码结构

| 文件 | 职责 |
| --- | --- |
| `server.py` | MCP 工具、参数校验、新站标签与车辆编号 |
| `bridge.js` | 原生命令工厂、核心队列和运行时读回 |
| `runtime_connection.py` | 附加、哈希校验和关闭生命周期 |
| `runtime_lease.py` | 单连接租约 |
| `mcp_session.py` / `session_call.py` | 持久标准 MCP 客户端和请求驱动 |
| `data/` | 来源规划，与游戏 ID 分开保存 |
| `tests/` | 无需真实游戏的回归检查 |

`prepare_*`、`build_line*`、`configure_line*`、`verify_line2.py` 是特定线路脚本，含固定站序、`work/` 路径及历史参数，不是可以直接换名使用的通用生成器。不能重跑旧一号线配置覆盖玩家移除的停站或古城—苹果园改建；其同层渡线也不得作为新地铁模板。

## 开发检查

```powershell
uv run python -m unittest discover -s tests -v
```

新增原生操作还需对应版本的运行时验证。`smoke_readonly.py` 依赖既有一号线资料并启动独立 MCP 连接，只在前提成立且没有其他附加会话时运行。`runtime_probe.py`、`test_runtime_call.py`、`test_command_queue.py` 是历史调查工具，不是自动回归套件或日常建线入口。

OSM 来源规划保留 [OpenStreetMap 归属与许可信息](https://www.openstreetmap.org/copyright)，详见 OSM 文档。世界站数、车队、余额和工程状态以实时读取为准，不以文档历史快照代替。
