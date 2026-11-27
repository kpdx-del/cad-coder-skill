"""2D simplified fastener representations, not a catalogue of product sizes.

GB/T 4459.1-1995 drawing conventions; product dimensions must be supplied
from the selected specification. End view and side view use the same hex.
"""
import math
from drawing_checks import mark_annotation


def hex_end(msp,center,across_corners,*,part=None):
    if not (math.isfinite(across_corners) and across_corners > 0):
        raise ValueError('positive finite across_corners required')
    x,y=center;r=across_corners/2
    e=msp.add_lwpolyline([(x+r*math.cos(i*math.pi/3),y+r*math.sin(i*math.pi/3)) for i in range(6)],close=True)
    mark_annotation(e,'fastener_hex_end',part=part,representation='assembly simplified')
    return e


def hex_head_side(msp,center_x,bearing_y,across_corners,thickness,*,outward=1,part=None):
    if not (math.isfinite(across_corners) and math.isfinite(thickness)
            and across_corners > 0 and thickness > 0 and outward in (-1,1)):
        raise ValueError('positive finite dimensions and outward +/-1 required')
    y1=bearing_y+outward*thickness;r=across_corners/2
    boundary=msp.add_lwpolyline([(center_x-r,bearing_y),(center_x+r,bearing_y),
                                 (center_x+r,y1),(center_x-r,y1)],close=True)
    faces=[]
    # Orthographic projection of the hex_end orientation: corners at +/-e/4.
    for dx in (-across_corners/4,across_corners/4):
        faces.append(msp.add_line((center_x+dx,bearing_y),(center_x+dx,y1)))
    centerline=msp.add_line((center_x,bearing_y-outward*1.5),(center_x,y1+outward*1.5),dxfattribs={'layer':'CENTER'})
    group=boundary.dxf.handle
    mark_annotation(boundary,'fastener_hex_side',role='boundary',group=group,part=part,
                    bearing_y=bearing_y,center_x=center_x,across_corners=across_corners,
                    thickness=thickness,outward=outward,faces=[f.dxf.handle for f in faces],
                    centerline=centerline.dxf.handle,
                    representation='simplified; chamfer omitted; no axial section hatch')
    for dx,face in zip((-across_corners/4,across_corners/4),faces):
        mark_annotation(face,'fastener_hex_side',role='face',group=group,part=part,
                        bearing_y=bearing_y,x=center_x+dx,y1=y1,
                        representation='simplified; chamfer omitted; no axial section hatch')
    mark_annotation(centerline,'fastener_hex_side',role='centerline',group=group,part=part,
                    bearing_y=bearing_y,
                    representation='simplified; chamfer omitted; no axial section hatch')
    return boundary


def thread_end(msp,center,major,minor,*,internal=False):
    if not (math.isfinite(major) and math.isfinite(minor) and 0 < minor < major):
        raise ValueError('require finite 0 < minor < major')
    # Tooth crest: thick full circle. Tooth root: thin 3/4 circle.
    crest=minor if internal else major;root=major if internal else minor
    full=msp.add_circle(center,crest/2)
    arc=msp.add_arc(center,root/2,30,300,dxfattribs={'layer':'THIN'})
    group=full.dxf.handle
    mark_annotation(full,'thread_end',role='crest',group=group,sibling=arc.dxf.handle,
                    internal=internal,major=major,minor=minor)
    mark_annotation(arc,'thread_end',role='root',group=group,sibling=full.dxf.handle,
                    internal=internal,major=major,minor=minor)
    return full,arc
