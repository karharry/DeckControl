import hid, io, time
from PIL import Image, ImageDraw
d=[x for x in hid.enumerate(0x0300,0x3002) if x['usage_page']==65440][0]
h=hid.device(); h.open_path(d['path'])
P=1024
def pkt(b): h.write(b'\0'+bytes(b).ljust(P,b'\0'))
pkt(b'CRT\0\0DIS'); pkt(b'CRT\0\0LIG\0\0\x64\x64')
pkt(b'CRT\0\0CLE\0\0\0\xff'); pkt(b'CRT\0\0STP'); time.sleep(0.5)
def card(n):
    im=Image.new('RGB',(n,n),'#0a3'); g=ImageDraw.Draw(im)
    g.rectangle([0,0,n-1,n-1],outline='red',width=2)
    g.line([0,0,n-1,n-1],fill='white'); g.line([0,n-1,n-1,0],fill='white')
    g.text((n//2-8,n//2-5),str(n),fill='white')
    return im.rotate(-90)
for key,n in enumerate([60,64,72,80,85,96]):
    b=io.BytesIO(); card(n).save(b,'JPEG',quality=95); data=b.getvalue()
    pkt(b'CRT\0\0BAT\0\0'+bytes([len(data)>>8,len(data)&255,key+1]))
    for i in range(0,len(data),P): pkt(data[i:i+P])
pkt(b'CRT\0\0STP'); print("sent sizes 60,64,72,80,85,96 to keys 1-6 (row1: 60 64 72, row2: 80 85 96)")
