import hid, io, time
from PIL import Image, ImageDraw
d=[x for x in hid.enumerate(0x0300) if x['usage_page']==65440][0]
h=hid.device(); h.open_path(d['path']); P=1024
def pkt(b): h.write(b'\0'+bytes(b).ljust(P,b'\0'))
pkt(b'CRT\0\0DIS'); pkt(b'CRT\0\0LIG\0\0\x64\x64'); pkt(b'CRT\0\0CLE\0\0\0\xff'); pkt(b'CRT\0\0STP'); time.sleep(.5)
def card(n,rot):
    im=Image.new('RGB',(n,n),'black'); g=ImageDraw.Draw(im); q=n//2
    g.rectangle([0,0,q,q],fill='red'); g.rectangle([q,0,n,q],fill='lime')
    g.rectangle([0,q,q,n],fill='blue'); g.rectangle([q,q,n,n],fill='yellow')
    g.rectangle([0,0,n-1,n-1],outline='white',width=2)
    g.ellipse([q-6,q-6,q+6,q+6],fill='white')
    return im.rotate(rot)
# (size, PIL rotate degrees): keys 1..6
cfg=[(60,0),(60,-90),(60,180),(60,90),(64,-90),(56,-90)]
for key,(n,r) in enumerate(cfg):
    b=io.BytesIO(); card(n,r).save(b,'JPEG',quality=95); data=b.getvalue()
    pkt(b'CRT\0\0BAT\0\0'+bytes([len(data)>>8,len(data)&255,key+1]))
    for i in range(0,len(data),P): pkt(data[i:i+P])
pkt(b'CRT\0\0STP'); print("sent")
