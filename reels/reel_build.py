"""Monte un reel 1080x1920 à partir d'un fichier de spec JSON.
usage: python3 reel_build.py spec.json sortie.mp4
"""
import sys, json, os, subprocess, tempfile
from PIL import Image, ImageOps

spec = json.load(open(sys.argv[1])); out = sys.argv[2]
work = tempfile.mkdtemp(dir='/tmp/claude-0'); ov = os.path.join(work, 'ov'); os.makedirs(ov)
subprocess.run(['python3', '/home/claude/build/reel_overlays.py', sys.argv[1], ov], check=True)

ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30',
       '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2']
COVER = 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30'
OVF = '[1:v]format=rgba,fade=in:st=0.12:d=0.3:alpha=1[o]'

def run(cmd):
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if r.returncode: print(r.stderr[-2000:]); sys.exit(1)

parts = []
for i, s in enumerate(spec['segments']):
    d = s['dur']; o = os.path.join(work, f'p{i:02d}.mp4'); png = os.path.join(ov, s['name'] + '.png')
    if s['kind'] == 'video':
        vol = s.get('vol', 0.55)
        run(['ffmpeg', '-y', '-ss', str(s['start']), '-t', str(d), '-i', s['src'], '-loop', '1', '-t', str(d), '-i', png,
             '-filter_complex', f'[0:v]{COVER}[v];{OVF};[v][o]overlay=0:0:shortest=1,format=yuv420p[vo];'
             f'[0:a]aresample=48000,volume={vol},afade=t=in:d=0.15,afade=t=out:st={d-0.2}:d=0.2[ao]',
             '-map', '[vo]', '-map', '[ao]', '-t', str(d)] + ENC + [o])
    else:
        if s['kind'] == 'photo':
            src = os.path.join(work, f'ph{i}.jpg')
            ImageOps.exif_transpose(Image.open(s['src'])).convert('RGB').save(src, quality=92)
            ovl = f'{OVF};[v][o]overlay=0:0,format=yuv420p[vo]'
        else:  # carte de fin : le PNG est l'image elle-même
            src = png
            ovl = '[v]format=yuv420p[vo]'
        n = int(d * 30)
        zp = f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,zoompan=z='1+0.07*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1080x1920:fps=30,setsar=1"
        inputs = ['-loop', '1', '-t', str(d), '-i', src]
        if s['kind'] == 'photo':
            inputs += ['-loop', '1', '-t', str(d), '-i', png]
        run(['ffmpeg', '-y'] + inputs + ['-f', 'lavfi', '-t', str(d), '-i', 'anullsrc=r=48000:cl=stereo',
             '-filter_complex', f'[0:v]{zp}[v];{ovl}',
             '-map', '[vo]', '-map', f'{2 if s["kind"]=="photo" else 1}:a', '-t', str(d)] + ENC + [o])
    parts.append(o)

lst = os.path.join(work, 'list.txt')
open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', '-movflags', '+faststart', out])
print('ok', out)
