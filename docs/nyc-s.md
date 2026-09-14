# 纽约 Franklin Avenue Shuttle

完整四站顺序：Franklin Avenue → Park Place → Botanic Garden → Prospect Park。

## 当前工程与运营

- 游戏线路代码 `nyc-s`，原生线路 ID `1125899908808705`。
- 78 个 Medium 轨道节点、48 个附属建筑已通过原生选区建造，读回全部已建成，建筑层级与轨道一致。
- 四站双线，两端站后延伸 400 米并设置折返渡线；双向共八个有向停站。
- 两列 Kayou 231 六节替代编组，120 米、900 人；编号 `nyc-s-0001`、`nyc-s-0002`，原生 ID 分别为 `1407374900658178`、`1407374900723714`。
- 客运服务 `service=2`，自动运行，默认停站 20 秒；游戏票价起步 3、每公里 0。
- 施工费用 21,185,786，购车费用 26,400,000，均通过正常原生命令扣款。

## 验证范围

建造前已查看原生曲线图；双线自然并行，保留 Prospect Park 北侧真实转弯。原生建造检查无阻塞；独立纽约区域施工前四站周围 1 公里未查到既有轨道。建造使用选区，另读回北京保护节点。

有限运行测试推进 2,007 个游戏秒，采集 13 组列车载客及四站候车读数。两车均出现载客变化，最高观测单车 64 人；四站队列均出现明显减少。测试后恢复暂停。公司现金包含北京既有运营，不能用于计算纽约线路利润。

代表列车 `nyc-s-0001` 已通过 Computer Use 完成完整往返图形验收：游戏时间 2026-10-27 19:33:01 在 Franklin Avenue 1S 出发站台，依次经过南行四站、Prospect Park 站后尾轨、北行四站及 Franklin Avenue 站后尾轨，于 19:46:23 再次停靠 Franklin Avenue 1S。南端尾轨观察到向南驶出后向北返回，北端尾轨观察到向北驶出后向南返回；各站实际停靠和载客均有观察记录。第二列车已有原生载客采样，未单独完成整圈图形跟踪。

图形验收记录保存在 `work/nyc-s-visual-verification.json`，包含本轮原生运行／暂停命令、实际停站及前一轮已观察片段的摘要。最终恢复暂停，游戏时间 `1793148383`；本记录补充原建设检查点，不能将旧检查点中的窗口授权阻塞视为当前状态。

## 来源与恢复

- [MTA 线路时刻表](https://www.mta.info/schedules/subway/franklin-avenue-shuttle)。
- [OSM relation 6342928](https://www.openstreetmap.org/relation/6342928)，规划及来源摘要见 `data/nyc_s_plan.json`，准备入口 `prepare_nyc_s.py`。
- © OpenStreetMap contributors，[版权与 ODbL](https://www.openstreetmap.org/copyright)。
- 游戏采用双线、140 米站台及替代车辆；正标高路堤／桥梁用 `depth=1`，负标高敞堑／隧道用 `depth=-1`，游戏没有对应的敞堑地形接口。具体适配记录在规划中，不宣称逐设施精确复刻。
- 独立检查点 `work/nyc-s-built.json` 保存全部原生命令、ID、运行采样及验收状态；恢复前先查询实时世界，不重放检查点。该文件不是游戏存档。
