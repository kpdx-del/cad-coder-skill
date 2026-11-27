# 二维零件库：索引/查询与核实边界

首期只做“二维画法、参数来源和审图规则索引/查询”，不是六套完整生成器，不承诺三维参数化模型或 SolidWorks 特征树。数据载体是 `library/catalog.json`，查询脚本是 `scripts/part_library.py`。

## 查询命令（离线，仅标准库）

```bash
python scripts/part_library.py list                        # 紧凑列出6类 id/名称/状态
python scripts/part_library.py search 关键词                # 中文/英文别名、大小写不敏感
python scripts/part_library.py show ID                     # 来源、画法、参数、核实/实现状态
python scripts/part_library.py check ID --parameters p.json # 只列真正缺项/条件待确认
```

- 只读、离线：不导入 ezdxf/FreeCAD/CadQuery，不下载，不执行外部项目代码，只用标准库。
- 退出码：`0` 成功（含 search 命中/show/check 出报告）；`1` 未命中/未知 id（`not_found`，不硬选近似零件）；`2` 用法或输入错误。
- 未知类别明确 `not_found`；不会因为关键词接近就返回近似零件。

## check 的输出语义

`--parameters` 沿用现有 `value`/`source` 记录形式（也可直接给裸值）。check 只读、不改输入、不填数值：

- `missing`：真正缺失的必需参数，或条件已被触发但值缺失的条件参数。
- `conditional_pending`：条件参数适用性未知（条件输入未给或值无法识别）时返回“待确认”，不默认为无。
- `invalid_zero`：值为 `0` 的参数不是缺失，但对“正值”参数报告其无效。
- `implementation`：资料与实现状态；**参数齐全也不代表可正式出图**。

`None`/空字符串/空列表/空对象是缺失；`0` 是存在的值（不按空处理）。仅有 `source` 而无 `value` 的记录是缺失（来源不等于已提供值）。

### 条件输入（condition inputs）

条件参数按显式条件输入（键 + 值）决定，**不按字段名存在即触发**，不新增表达式求值器：

| 条件键 | 取值 | 含义 | 影响的条件参数 |
|---|---|---|---|
| `view_spec` | `end` / `side` / `section` | 视图方向：端视/侧视/剖切 | 垫圈 `thickness`（`side`/`section` 需要，`end` 不需要） |
| `thread_form` | `coarse` / `fine` | 螺纹形式：已明确粗牙/细牙 | 螺栓/螺母 `pitch`（`fine` 需要，`coarse` 不需要） |
| `thread_termination` | `false` / `true` | 是否需要表达螺纹终止线/旋合长度 | 螺栓 `thread_length` |
| `grade_series_specified` | `true` / `false` | 指定类型/标准是否已包含产品等级与尺寸系列 | 垫圈 `series`（`false` 需要，`true` 不重复追问） |
| `keyway_tolerance_required` | `false` / `true` | 是否需要标注键槽配合公差 | 平键 `keyway_tolerance` |
| `chamfer_required` | `false` / `true` | 按任务条件是否需要倒角 | 隔套 `chamfer` |

布尔条件键同时接受 `true`/`false` 与中文“需要/不需要”；枚举同时接受英文与中文（如 `fine`/细牙、`coarse`/粗牙）。条件输入未给或值无法识别视为 unknown（待确认），**不等于 false（不需要）**；明确不需要时不再追问，已给的值不重复问。thread_form 的 coarse/fine 须已给标记或标准明确，未知时不能自动设 coarse，不得补默认螺距值。

## 六类条目

| id | 中文名 | 适用标准（catalog_status） | 尺寸表核验 | 可正式出图 |
|---|---|---|---|---|
| bolt | 螺栓 | GB/T 4459.1-1995（表示法）、GB/T 5782-2025（产品） | 未核验 | 否 |
| nut | 螺母 | GB/T 4459.1-1995（表示法）、GB/T 6170-2015（产品） | 未核验 | 否 |
| washer | 垫圈 | GB/T 97.1-2002（产品） | 未核验 | 否 |
| bearing | 单列圆锥滚子轴承 | GB/T 4459.7-2017（表示法，具体条款待核验） | 未核验 | 否 |
| key | 平键 | GB/T 1096-2003（产品） | 未核验 | 否 |
| spacer | 隔套 | 本任务未指定专用产品标准（按用户尺寸） | 无指定标准 | 否 |

`catalog_status`（官方目录为现行）不等于尺寸表已核验；本轮所有产品尺寸表未核验，目录为现行也不能标成正式尺寸库。表示法核实与产品数据核实分开记录。

## 类别要点

- **螺栓/螺母**：端视粗/细圆内外相反（外螺纹大径粗、内螺纹小径粗）；侧视与端视投影一致；沿轴线装配剖切按不剖。`scripts/fasteners.py` 仅提供简化图元，不含尺寸表；`part_templates.hex_nut` 是旧比例示意，严禁作标准尺寸表。
- **垫圈**：需要类型、接口直径及对应视图所需厚度；端视同心圆不需要厚度，侧视/剖切需要。产品等级与尺寸系列分别按选定标准核验；本轮只核实 GB/T 97.1-2002 A级的目录状态，未核验全部系列及尺寸表。
- **单列圆锥滚子轴承**：规定画法候选（GB/T 4459.7-2017），具体条款/样例待核验；现有工程图型号未知，不新增型号，完整结构不能从图估计。
- **平键**：必须区分类型（按已给键型核验端部形状，不从装配图局部露出轮廓直接判定型号）与轴槽/毂槽；参数从所选规格或用户给定，不把 N9/JS9 或圆头形状套给所有情况。
- **隔套**：本任务未指定专用产品标准，需内外径、长度/接触界面；倒角按任务条件，不自动添加。

## GitHub 候选与许可冲突

- FastenersWB（螺栓/螺母/垫圈）：LICENSE 现为 LGPL-2.1，但 README 末尾有 GPLv2 残留，后续按固定提交/文件核验；本库不复制。
- cq_warehouse（紧固件/轴承）：Apache-2.0，CadQuery 依赖，此期不引入，仅参考参数化/表值。
- FreeCAD-library：资产 CC-BY-3.0（需署名）、代码 LGPL-2.1+，库巨大，只按需取文件。
- freecad.gears（GPL-3.0）供后续齿轮，不属首批。
- 平键无已核实专用模块在证据内，标记 pending；禁止照搬进本 MIT 库而丢来源。

## 陌生零件工作流

1. 先查本库已核实内容（`search`/`show`）；未命中或不熟悉，明确 `not_found`，不猜近似零件。
2. 优先搜 GitHub 与官方生态的成熟实现，记录仓库、模块、许可证、维护日期、依赖与改造成本。
3. 再按适用版本国标与教材核对表示法与产品数据；目录状态不等于全文/尺寸表核验。
4. 成熟实现合适则最小复用，注明模块、许可证和代价；核验前仅标 `candidate`。
5. 同一规范优先复用已有记录，不每次重新大段检索。

DIN/ISO 参数不等于同号 GB 参数；图纸缺参数不能按图片比例补造；来源字段只是追溯记录，不证明内容真实，仍须核对原文和计算。
