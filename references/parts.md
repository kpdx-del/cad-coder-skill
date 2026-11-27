# 六类专项：只询问当前特征所需条件

通用规则见 annotation-rules.md。下列是输入/复核范围，不是默认技术要求，也不表示已提供六套自动生成器。

| part_type | 基础参数名 | 条件必需与专项复核 |
|---|---|---|
| shaft | diameters、axial_dimensions | 配合处自身公差、定位功能；有键槽才问槽宽/深/长，有几何控制才问基准与公差项目；移出断面方向 |
| gear | module、teeth、pressure_angle、width、bore | 斜齿再问helix_angle、hand；轮毂与连接结构、精度/检验要求按任务补入required；不默认压力角20°、精度7级或齿顶h11 |
| bearing_seat | interface_dimensions | 已知轴承型号核对接口；设计配合才需load_type、rotation_relation、operating_conditions；不自动给轴承内部公差或默认0级 |
| key_spline | type、specification、connection | 轴槽/毂槽区分；定心方式、槽尺寸及对应标准版本；不将N9/JS9、小径定心等套用于全部键/花键 |
| thread | type、specification、length | 非默认螺距/旋向/多线需pitch、hand、starts；公差、旋合长度及镀层要求按任务补入required；不能默认6g/6H |
| taper | independent_geometry、reference_plane、tolerance_method | 独立参数唯一确定形状，锥度/角度/直径/长度关系校核；给定截面直径与全长直径公差区分 |

`conditions` 支持 helical、design_fit、keyway、datum_control、nonstandard_thread（见 drawing_checks.CONDITIONAL）。更具体的缺项由生成脚本的 required 明示，布尔条件未给不能假设结构不存在。

## 轴

两中心孔与两轴承轴颈是不同基准方案：依据功能和加工/检验过程选用。教材图3-80采用两端中心孔A、B；不能误写成两轴承轴颈。图2-1给定尺寸与图2-2示例外形/标注不同，不混用数值。

轴承轴颈圆度/圆柱度、配合处同轴度/跳动、轴肩垂直度/端面跳动、键槽对称度都是按功能选用的候选，不能全加。第三章第91页明确说明后续若干图为展示项目，不代表实际零件全部需要。

## 齿轮与轴承配合件

齿轮规定画法及参数表需核对相应制图标准；已知m、z不一定足以确定变位、斜齿、齿顶修缘等全部几何。不要把齿面精度、齿坯几何公差和尺寸公差混为一项。

轴承是标准件，常规任务画相配轴/座孔或装配简图，不虚构轴承内部零件图。选择配合需考虑负荷相对套圈的关系；不能只看“轴转/孔不转”就选公差带。

## 键/花键、螺纹、圆锥

轴上键槽以便于测量的 d−t₁ 等形式表达时，所需值必须来自实际规格/标准，不按比例估计；槽宽、槽深、长度、对称度及粗糙度按要求分别核对。

教材第三章把螺纹的中径轴线与齿轮/花键的PD、MD、LD说明分别列出，不能写成“三者一律默认中径”。普通螺纹标记中的省略规则先确定标准和螺纹类型，细牙、左旋、多线等不能丢项。

圆锥先核对 C=(D−d)/L=2tan(α/2)，再按选定给定方式标注；冗余输入不一致应报错。理论正确角度方框不是尺寸公差，基面位置和长度单位必须明确。
