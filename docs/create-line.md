# 创建一条线路：完整流程

[返回主文档 AGENTS.md](../AGENTS.md) · [OSM 数据](osm-data.md) · [默认参数](defaults.md)

本流程覆盖地理规划、原生蓝图、配线、换乘、运营线路、车辆和验收。工具参数以 [server.py](../server.py) 为准，原生命令适配在 [bridge.js](../bridge.js)。调用示例必须填入本次规划和实时查询得到的 ID，不能直接重跑既有线路。

## 1. 确定范围和建设规格

确定城市、线路名称、起终点或环线方向、完整站序、关闭／不停靠的站点、换乘站及是否共用既有设施。记录玩家已修改的几何、站名、停站和经营设置。

按默认参数选择：地铁 Medium，按实际地面／高架／地下区间还原；高铁 High speed／高架，普速 Medium／Ground。地铁避免导致信号阻塞的跨线同层平交，普通同层道岔和交叉渡线可以保留。当前工具未开放 High speed 参数；层级编辑支持 `-3..3`，原有建站接口仍为 `-1/0/1`。

明确线路代码、颜色、运营方向及车队方案，例如 `bj-3`，内外环分别 `bj-3i`、`bj-3o`。当前正则只允许一个城市分隔连字符，`bj-3-inner` 不符合校验。新默认不是自动改造既有线路的指令。

## 2. 检查环境和 MCP 连接

在仓库根目录使用 uv：

```powershell
uv sync --locked
```

先载入目标世界；适配器要求唯一 NimbyRails 进程，EXE 哈希须匹配 [game_version.py](../game_version.py)。游戏更新后先适配，不跳过哈希检查。

使用已注册 stdio MCP 或本仓库持久客户端，二选一。已有持久客户端时复用，不重复启动：

```powershell
# 仅在没有现存持久客户端时启动；该命令持续运行。
uv run python mcp_session.py
# 另一个终端提交请求，不再附加游戏：
uv run python session_call.py runtime_status
```

Python 调用：

```python
from session_call import call
status = call('runtime_status')
```

完整路径为 `mcp_session.py → MCP ClientSession.call_tool → server.py → bridge.js → 游戏原生命令队列`。磁盘队列只是客户端驱动，不能作为绕过 MCP 的理由。单连接租约禁止争用；一次观测超时不是重启依据。

修改服务器或桥接后，旧会话需有序退出、确认其进程终止，再启动新客户端。当前队列支持 `{"stop": true}` 控制消息，关闭过程会排空原生回调；不需要重启游戏来加载 MCP 代码。

## 3. 读取现场并暂停

读取 `runtime_status`，记录 PID、速度、游戏时间和现金。该工具没有世界名称／UUID，因此还要用已知车站、坐标及线路核对目标世界。通过 `set_simulation_speed(speed=0)` 暂停并读回。

使用 `get_line`、`get_station`、`list_trains` 盘点；从已核实站台 ID 调用 `get_track_network`，包含分支并记录类型、层级、坐标和蓝图状态。旧检查点仅是查找种子，不能代替当前状态。当前没有通用全线路／全车站列表工具，未知范围须补充只读接口或结合 UI 观察确认。

用户正在改动或现场与计划不符时重新读相关区域。不要恢复旧 OSM 里的停站覆盖玩家删除的停站，也不要以旧端点覆盖玩家改建区间。

## 4. 准备地理规划

按 [OSM 数据文档](osm-data.md) 获取完整关系、验证站序和连续性、投影坐标、计算站台切线及简化区间。写入独立 `data/<line>_plan.json`，明确来源、最终轨道类型、depth、用户例外与无平交配线方案。

新线路使用独立构建入口。`build_line1.py`、`build_line2.py` 写死站序、路径或预算，只能参考算法，不能改一个名字就运行。

检查站台长度、曲线、道路、层级过渡、换乘距离及折返空间。投影 world_length 不是实际票价里程或原生工程账单。

## 5. 预算和检查点

预算分别计入轨道／站台、配线／立交、车辆及运营储备。现有六节替代编组每列为 13,200,000 游戏货币。二号线的 5 亿施工前门槛是特定方案，不是所有线路默认。

每个变更命令都记录：

```text
写 pending(tool, arguments)
 → 发起一次 MCP 调用
 → 保存完整返回和 native IDs
 → 更新阶段与下一步骤
```

检查点至少含计划摘要、现场识别信息、站台／区间／配线 ID、命名完成情况、停站进度、购车 ID、待处理命令及读回结果。恢复所需持久状态不是可清理缓存。现有脚本使用 `work/*-built.json`，不进 Git；新下载和临时调试输出放 `%TEMP%`，不另建临时目录。迁移旧队列／检查点需同步消费者，不能中途移走。

现有二号线脚本仍存在“命令结果已写入，但阶段尚未写完”的中断窗口。恢复时必须同时核查 `commands`、`pending`、协议结果和游戏对象，不能只按数组长度重放。标签设置失败可能发生在站台成功创建之后：用异常返回 ID 补标签，不再建站。

## 6. 创建站台与保存方向映射

传入已投影的端点和类别对应层级：

```python
result = call('create_platform',
              start_x=a['x'], start_y=a['y'],
              end_x=b['x'], end_y=b['y'], depth=-1)
# result['nodes'] 是原生节点；result['stations'] 是默认标签设置后的读回。
```

工具默认设置 `Name and pax`。返回节点中应有 4 个 `station_id != '0'` 的站台节点，核对其连接结构再使用。现有脚本约定：

```text
p0 = 最靠近规划 start 的站台节点
p1 = 站台节点表中的 p0.next
p2 = 另一股道上 next 仍在站台节点表中的节点
p3 = 站台节点表中的 p2.next

west_stop = p0.id             east_stop = p2.id
west_primary = p0.previous    east_primary = p1.next
west_secondary = p3.next      east_secondary = p2.previous
```

`east/west` 是沿规划路线的历史字段名，不代表真实方位。有向停站不能按节点 ID 大小猜方向。保存原生站点和节点 ID 后再调用 `rename_station`，核对名称及标签；返回结构不符合预期就停止依赖该结构的后续命令。

## 7. 连接区间与设计配线

连接前站 `east_primary` 和后站 `west_primary`。先读实时端点，确认确实空闲；沿规划中间点调用 `extend_track`，每次保存新的前沿端点，最终 `connect_track_endpoints(..., dual=True)`。

同坐标不代表拓扑连接，必须用原生 ID 接既有端点。`create_track_segment` 没有 depth 参数，固定地下 Medium；普速可从显式 `depth=0` 的站台端点延伸，不能给不支持的工具传伪参数。

### 环线

最后一站连接回第一站，双股道都要闭合。从每方向站台沿 `next` 遍历，必须回到起点且含该方向全部站台。分支节点可能有 `previous=0` 或 `next=0`；应结合 `branch_parent/branches` 检查，不能把所有分支端点判成主环断点。

### 非环线配线与跨线平交

明确末站进站、停车、反向出站的完整进路。普通同层道岔和交叉渡线是正常配线，不应因几何相交就下沉到 `-3`。不同线路的正线同层交叉若造成信号阻塞，应将一条线路的交叉段与相邻站台调整至不同地下层，并核对过渡轨道和换乘。

`create_track_branch` 创建单线连接，`edge_id` 表示节点的 previous 边，位置比例 `.01.. .99`。历史脚本可作为配线参考，但不能重放旧检查点覆盖玩家改动。建成后观察折返和信号等待。

站台变层使用原生 ReBP → `set_track_depth` → 正常建造。层级编辑同时同步节点附属建筑，读回 `buildings[].depth` 应与节点 `depth` 一致。历史棕色站台／站房层级不同步时，使用 `sync_platform_building_depth(node_ids)`；其仅同步附属建筑，不移动轨道。`get_nearby_track_nodes` 可查附近对象及附属建筑。原生曲线相交审计只能定位候选点，不能把普通渡线自动判为行车故障。

## 8. 换乘与已有设施

建轨位置完成后、建造前，使用 `calculate_track_tangents(node_ids, paired_nodes)` 读取实时前后节点并预览切线角度，再用 `auto_set_track_tangents` 写入显式方向。相邻边长比例达到4:1时优先沿长直段，避免短过渡把长线拉弯；长度相近时使用单位向量角平分线。双线须显式传入对应节点对，工具不会猜测跨线配对；位置和间距错误需要先整理，方向计算不能代替几何修正。仅处理选定的非站台、非道岔蓝图控制点，先接完前后区间，保留玩家修正过的节点；设置后核对原生曲线和限速，不能把计算成功当作曲线验收或建造授权。

同一换乘站使用统一 station 归属。先读取 `get_station_inventory` 和站台节点，核对位置、名称及原生 ID，再调用：

```python
call('assign_platform_station', node_ids=new_platform_node_ids, station_id=existing_station_id)
```

该接口使用 Track properties 对应的原生 Edit，保留轨道位置、连接和层级，读回节点归属。当前北京任务只需统一 station 归属，不要求站台范围重叠，不为合站补建 Platform footprint extension。

合站后重新扫描全世界轨道引用，通过 `delete_empty_stations` 删除引用数为零的旧站点；工具拒绝删除仍有轨道引用的车站。历史 WalkLink 不等于合站，只有明确需要站外步行连接时才使用。

已建轨道变更通过 `rebuild_track_blueprints → 类型／层级编辑 → build_all_blueprints`，完成后重新验证几何、连接、运营及费用。标签设置和步行换乘不需要重建轨道。

## 9. 核对并建成蓝图

通过完整网络查询检查站数、连通、双环或折返、类型、depth 和地铁无平交。超过 5,000 节点上限时先完善分区验证，不能用局部检查证明整线完成。

**`build_all_blueprints` 建造全世界全部待建蓝图。`verify_node_ids` 只限定读回范围，不是建设选区。** 查询既有已知网络，并观察全局蓝图账单或开发相应读取接口，确认没有误纳入玩家其他蓝图。已知网络没有蓝图不能证明世界其他位置也没有。

独立补建可使用 `build_selected_blueprints(node_ids, protected_node_ids)`。它向原生建造命令传入选区模式，选择指定轨道及其附属建筑；保护列表仅作建造前后状态校验。完成后必须核对选中轨道和建筑均已建成，其他待建蓝图保持原状态。该模式已通过53号站及其连接线的小规模真实建造验证。

原生建造可能允许现金变为负数，不能把命令成功当作预算足够。核对原生账单、正常资金和购车储备后提交一次：

```python
result = call('build_all_blueprints', verify_node_ids=all_new_node_ids)
```

成功须有 `code=0` 且全新线节点 `blueprint=false`。读取现金记录实际工程成本。冲突或资金不足时处理具体问题；超时先查节点是否已经建成，再决定后续动作。

## 10. 创建运营线路与停站

```python
line = call('create_line')['line']
line_id = line['id']  # 立即记录
call('set_line_name', line_id=line_id, name=planned_name, code=planned_code,
     color=planned_color, base_fare=planned_base, fare_per_km=planned_per_km)
```

显式传本次代码，不能依赖历史默认 `bj-1`。票价按方案设置，示例中的 `25 + 10/km` 不是普遍最优或现实票制。

用 `add_line_stop` 逐站追加有向节点，每次记录 `stop_id` 和当前站数。重复运行会重复追加：

- 环线：沿规划顺序添加 `east_stop`，另一运营方向逆序添加 `west_stop`；N 站对应每方向 N 个停站，不额外重复首站。
- 非环线：可正向添加全部 `east_stop`、逆序添加全部 `west_stop`，形成约 2N 个有向停站；必须有符合规格的可行折返。

常规非环线需要站后折返空间和配线，终点安排到达、站后折返、出发的完整进路。机场线因站后空间不足例外采用站前折返、终点只列一次停站：北新桥→东直门→三元桥→T3→T2→三元桥→东直门循环，共7个停站。不得把机场线例外推广到8号线等常规线路。运行时核对实际渡线和换向位置。

最后 `get_line` 比较完整有序停站列表，不能只检查总数。观察游戏分段路径、周期及缺失路径提示，确认方向和寻路正确。

`west_stop` / `east_stop` 是建站端点键，不代表地图上固定的东西侧；也不能直接用 `next` 推断列车行驶方向。须在游戏核对站台编号和方向字母，以及区间是否发生不必要的站前换线。北京10号线已核实：外环规划顺序用 `east_stop`，内环逆序用 `west_stop`；慈寿寺内环为东侧 `2N`。

修正既有停站使用 `set_line_stop_platform(line_id, stop_index, platform_node_id)`，其中索引从0开始。先暂停、保存实时停站列表，再通过原生 EditStop 修改同一车站的有向节点，读回核对停站 ID、站序和经营设置；不要删除重建运营线路或重复购车。

## 11. 购车并开通客运

确认预算、车型长度和站台长度后：

```python
fleet = call('purchase_six_car_trains', line_id=line_id, count=planned_count)['trains']
# 保存所有 train.id；工具已自动分配线路并按前缀命名。
call('set_line_service', line_id=line_id, service=2,
     reference_train_id=fleet[0]['id'])
```

当前工具只有 Kayou 231 六节替代编组，不支持直接采购任意普速／高铁车型。数量按周期和目标间隔估算，见默认参数。`list_trains` 核查全车队编号唯一、新车前缀和编组。

购车成功但改名失败时，用异常中的 ID 读取现有车并仅补 `rename_train`，禁止再次购车。

## 12. 运行与完成验收

记录起始游戏时间，设置有限运行速度和明确停止条件，至少观察完整一圈／往返。高倍速期间主动监测并及时暂停，不能无限放任运行。Computer Use 只观察路径、速度、停站、上下客、载客数及提示，游戏操作仍用 MCP。

| 要求 | 证据 |
| --- | --- |
| 全部站点、正确站序 | 实时站点和有序 stops 与规划逐项比较 |
| 类型、层级、全线建成 | 含分支的完整网络读回 |
| 跨线平交与信号 | 正线交叉层级及行车核查；普通同层渡线不作为自动改造目标 |
| 双环／双向折返可行 | 拓扑与实际行驶、停站观察 |
| 换乘 | 同一换乘站所有站台节点指向同一 station；需要的站外步行连接另行校验 |
| 车队及编号 | 全车队查询、单车属性、实际线路状态 |
| 客运运行 | service=2，并观察行驶、上下客和载客 |
| 玩家改动保留 | 对比施工前现场，不能对比旧规划 |
| 正常资金 | 原生建造／采购结果及现金记录 |
| 存档（若任务要求） | 游戏保存和重载校验；检查点 JSON 不是游戏存档 |

当前没有通用原生保存 MCP 工具，不能把规划／检查点写入说成世界已保存。最后按用户要求恢复速度或暂停，报告范围、车队、换乘和未完成项。蓝图存在、线路设置完成或余额上涨，都不能单独证明通车。

## 13. 中断与错误恢复

| 现象 | 恢复方式 |
| --- | --- |
| 请求过期且未派发 | 确认未进入原生队列，再发新请求 |
| processing 文件、超时、连接断开 | 结果未知；读取对象和日志，不把文件改回 request 重放 |
| 建站后默认标签失败 | 按已创建 ID 补标签，不再建站 |
| 站名未完成 | 查询现有名称，仅补命名 |
| 追加停站中断 | 比较完整列表，只补明确缺失部分 |
| 购车后命名中断 | 按已购 ID 补改名 |
| 建成阶段超时 | 查 blueprint 状态和现金 |
| 用户改图或加载世界 | 重新确认现场，禁止旧几何覆盖 |

客户端请求有效期 25 秒、等结果约 30 秒；桥接任务超时约 5 秒。排队过期、已派发超时和已验证失败应分别处理。以当前进程／任务和游戏读回为证据，不以旧锁文件判断仍在运行。

## 14. 现有脚本的复用边界

| 文件 | 用途与限制 |
| --- | --- |
| [prepare_geometry.py](../prepare_geometry.py) | 一号线投影；写死站序，混合 depth 不能当新地铁默认 |
| [prepare_line2.py](../prepare_line2.py) | 二号线闭合几何；relation、18 站和路径固定 |
| [build_line1.py](../build_line1.py) | 区间简化参考；保留玩家改动，不重跑旧线 |
| [build_line2.py](../build_line2.py) | 双环、逐命令检查点参考；只到蓝图，门槛和路径固定 |
| [configure_line2.py](../configure_line2.py) | 固定内外环各 18 站和 6 列车；有 services 时拒绝重跑 |
| [inventory_line1.py](../inventory_line1.py) | 旧 ID 仅作现场查询种子 |
| [verify_line2.py](../verify_line2.py) | 二号线特定 ID 验收；还会写报告／检查点，不是纯文件只读 |

`verify_line2.py` 固定一号线 70 停站、688 节点等历史条件，不能直接证明新线完成，也未验证任意配线无平交。为新线提取算法时审核所有固定值，并建立对应范围的完整验收。
