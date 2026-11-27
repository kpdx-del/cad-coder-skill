"""Original, explicitly dimensionless convention examples; not product geometry."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ezdxf
from sketch_helpers import new_doc
from typography import add_text
from fasteners import hex_end,hex_head_side,thread_end
from render_dxf import render_many


def build():
    d=new_doc(font='times.ttf');m=d.modelspace()
    m.add_lwpolyline([(5.5,5.5),(291.5,5.5),(291.5,204.5),(5.5,204.5)],close=True,dxfattribs={'layer':'THIN'})
    def t(text,x,y,h=3.5):return add_text(m,text,(x,y),h)
    def axes(x,y,r):
        for a,b in [((x-r,y),(x+r,y)),((x,y-r),(x,y+r))]:
            m.add_line(a,b,dxfattribs={'layer':'CENTER'})
    t('螺栓／螺母画法对照',13,193,5)
    t('装配简化画法；全部尺寸为演示比例，不代表任何产品规格或制造数据',13,183,3)
    for x in (101,195):m.add_line((x,57),(x,176),dxfattribs={'layer':'THIN'})
    t('A  六角头螺栓',14,170);t('B  六角螺母',108,170);t('C  螺杆螺纹端部',202,170)
    hex_end(m,(53,145),30);axes(53,145,19)
    hex_head_side(m,53,100,30,12)
    m.add_lwpolyline([(45,100),(45,65),(61,65),(61,100)])
    for x in (46.2,59.8):m.add_line((x,65),(x,87),dxfattribs={'layer':'THIN'})
    m.add_line((45,87),(61,87))
    m.add_line((53,61),(53,98.5),dxfattribs={'layer':'CENTER'})
    t('头部端视：没有螺纹孔',14,120,3)
    t('侧视：六角面与端视对应',14,58,3)
    hex_end(m,(147,145),30);thread_end(m,(147,145),16,13.6,internal=True);axes(147,145,19)
    hex_head_side(m,147,100,30,12)
    for dx in (-8,-6.8,6.8,8):
        m.add_line((147+dx,100),(147+dx,112),dxfattribs={'layer':'HIDDEN','ltscale':.35})
    t('端视：小径粗，大径细',108,120,3)
    t('侧视：不可见螺纹用细虚线',108,91,3)
    t('沿轴线的装配剖切不画剖面线',108,58,2.8)
    thread_end(m,(242,145),24,20.4);axes(242,145,19)
    m.add_lwpolyline([(230,112),(254,112),(254,65),(230,65)],close=True)
    for x in (231.8,252.2):m.add_line((x,65),(x,112),dxfattribs={'layer':'THIN'})
    m.add_line((242,61),(242,116),dxfattribs={'layer':'CENTER'})
    t('端视：大径粗，小径细',202,120,3)
    t('细圆约3/4圈；侧视细线表牙底',202,58,2.8)
    t('1. 本图省略六角头、螺母的倒角细节。详细画法中的倒角圆及投影圆弧须按实际规格补全。',13,44,3)
    t('2. 端视方向必须说清；螺栓头部端视、螺杆端视、螺母端视不能混用。',13,36,3)
    t('3. 依据：GB/T 4459.1-1995；公开工程制图样章。产品标准、出处和未核验内容见随附说明。',13,28,3)
    t('未指定M号、螺距、长度或性能等级；图中不据比例补造这些数据。',13,16,3)
    return d


if __name__=='__main__':
    out=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent/'output/fastener-views'
    out.mkdir(parents=True,exist_ok=True)
    path=out/'螺栓螺母_画法对照.dxf';build().saveas(path)
    d=ezdxf.readfile(path);assert not d.audit().has_errors
    render_many(path,[path.with_suffix('.png'),path.with_suffix('.pdf')],paper='A4',margin=5,scale=1)
    print(path)
