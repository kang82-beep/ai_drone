"""Orthographic triangle rasterizer with depth testing and per-pixel selection."""
import math
import numpy as np
from PIL import Image
from .site_structures import COLORS


def rasterize(parts,width,height,yaw,elevation,scale,cx,cy,screen_y=None,selected=None):
    depth=np.full((height,width),-np.inf,dtype=np.float32)
    pixels=np.zeros((height,width,3),dtype=np.uint8);pixels[:]=[16,29,43]
    picking=np.full((height,width),-1,dtype=np.int32)
    co,si=math.cos(yaw),math.sin(yaw);ce,se=math.cos(elevation),math.sin(elevation)
    screen_y=height/2 if screen_y is None else screen_y
    for index,part in enumerate(parts):
        vertices=np.asarray(part['vertices'],dtype=float)
        x=vertices[:,0]-cx;y=vertices[:,1]-cy;z=vertices[:,2]
        a=x*co-y*si;b=x*si+y*co
        pp=np.column_stack((width/2+a*scale,screen_y+(b*se-z*ce)*scale,b*ce+z*se))
        color=COLORS[part['kind']] if part['id']!=selected else '#ecad42'
        base=np.array([int(color[i:i+2],16) for i in (1,3,5)])
        for face in part['faces']:
            normal=np.cross(vertices[face[1]]-vertices[face[0]],vertices[face[2]]-vertices[face[0]])
            norm=np.linalg.norm(normal)
            shade=.72+.28*abs(float(np.dot(normal/norm,[.3,-.4,.866]))) if norm else 1
            rgb=np.clip(base*shade,0,255).astype(np.uint8)
            for n in range(1,len(face)-1):
                p,q,r=pp[[face[0],face[n],face[n+1]]]
                xmin=max(0,int(math.floor(min(p[0],q[0],r[0]))));xmax=min(width-1,int(math.ceil(max(p[0],q[0],r[0]))))
                ymin=max(0,int(math.floor(min(p[1],q[1],r[1]))));ymax=min(height-1,int(math.ceil(max(p[1],q[1],r[1]))))
                if xmax<xmin or ymax<ymin:continue
                den=(q[1]-r[1])*(p[0]-r[0])+(r[0]-q[0])*(p[1]-r[1])
                if abs(den)<1e-9:continue
                xx=np.arange(xmin,xmax+1)[None,:]+.5;yy=np.arange(ymin,ymax+1)[:,None]+.5
                u=((q[1]-r[1])*(xx-r[0])+(r[0]-q[0])*(yy-r[1]))/den
                v=((r[1]-p[1])*(xx-r[0])+(p[0]-r[0])*(yy-r[1]))/den;t=1-u-v
                zz=u*p[2]+v*q[2]+t*r[2]
                tile=depth[ymin:ymax+1,xmin:xmax+1]
                mask=(u>=-1e-7)&(v>=-1e-7)&(t>=-1e-7)&(zz>tile)
                tile[mask]=zz[mask]
                pixels[ymin:ymax+1,xmin:xmax+1][mask]=rgb
                picking[ymin:ymax+1,xmin:xmax+1][mask]=index
    return Image.fromarray(pixels),picking
