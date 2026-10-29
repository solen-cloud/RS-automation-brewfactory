"""Monte un reel 1080x1920 dynamique à partir d'un fichier de spec JSON.
usage: python3 reel_build.py spec.json sortie.mp4

Options par segment :
  video : src, start, dur (durée FINALE à l'écran), speed (1 = normal), zoom (amplitude du punch-in, ex 0.12)
  photo : src, dur, zoom (amplitude), zin (true = zoom avant, false = arrière)
  end   : carte de fin
  flash : true -> flash blanc de 3 images à l'entrée du plan
"""
import sys, json, os, subprocess, tempfile
from PIL import Image, ImageOps

spec = json.load(open(sys.argv[1])); out = sys.argv[2]
work = tempfile.mkdtemp(dir='/tmp/claude-0'); ov = os.path.join(work, 'ov'); os.makedirs(ov)
subprocess.run(['python3', '/home/claude/build/reel_overlays.py', sys.argv[1], ov], check=True)

ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30',
       '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2']
# texte : glisse de 90 px vers le haut et apparaît en 0,22 s
OVF = '[1:v]format=rgba,fade=in:st=0:d=0.22:alpha=1[o]'
OVL = "[v][o]overlay=x=0:y='if(lt(t,0.22),90*(1-t/0.22),0)':shortest=1"

def run(cmd):
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if r.returncode: print(' '.join(cmd)); print(r.stderr[-2500:]); sys.exit(1)

def zoompan(n, amp, zin=True, big=False):
    z = f"1+{amp}*on/{n}" if zin else f"1+{amp}-{amp}*on/{n}"
    pre = 'scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,' if big else \
          'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,'
    dd = n if big else 1
    return pre + f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={dd}:s=1080x1920:fps=30,setsar=1"

parts = []
for i, s in enumerate(spec['segments']):
    d = s['dur']; n = max(2, int(round(d * 30)))
    o = os.path.join(work, f'p{i:02d}.mp4'); png = os.path.join(ov, s['name'] + '.png')
    flash = ',fade=in:st=0:d=0.1:color=white' if s.get('flash') else ''
    if s['kind'] == 'video':
        sp = s.get('speed', 1.0); vol = s.get('vol', 0.5)
        src_d = d * sp
        atempo = ','.join(['atempo=2.0'] * int(sp // 2) + ([f'atempo={sp / (2 ** int(sp // 2)):.4f}'] if sp % 2 else [])) if sp != 1 else 'anull'
        vf = (f"[0:v]setpts=PTS/{sp},fps=30,{zoompan(n, s.get('zoom', 0.1), s.get('zin', True))}{flash}[v]")
        run(['ffmpeg', '-y', '-ss', str(s['start']), '-t', str(src_d), '-i', s['src'], '-loop', '1', '-t', str(d), '-i', png,
             '-filter_complex', f"{vf};{OVF};{OVL},format=yuv420p[vo];"
             f"[0:a]aresample=48000,{atempo},volume={vol},afade=t=in:d=0.06,afade=t=out:st={max(0, d - 0.08)}:d=0.08[ao]",
             '-map', '[vo]', '-map', '[ao]', '-t', str(d)] + ENC + [o])
    else:
        if s['kind'] == 'photo':
            src = os.path.join(work, f'ph{i}.jpg')
            ImageOps.exif_transpose(Image.open(s['src'])).convert('RGB').save(src, quality=92)
            inputs = ['-loop', '1', '-t', str(d), '-i', src, '-loop', '1', '-t', str(d), '-i', png]
            ovl = f'{OVF};{OVL},format=yuv420p[vo]'; amap = '2:a'
            zp = zoompan(n, s.get('zoom', 0.14), s.get('zin', True), big=True)
        else:
            inputs = ['-loop', '1', '-t', str(d), '-i', png]
            ovl = '[v]format=yuv420p[vo]'; amap = '1:a'
            zp = zoompan(n, 0.05, True, big=True)
        run(['ffmpeg', '-y'] + inputs + ['-f', 'lavfi', '-t', str(d), '-i', 'anullsrc=r=48000:cl=stereo',
             '-filter_complex', f'[0:v]{zp}{flash}[v];{ovl}',
             '-map', '[vo]', '-map', amap, '-t', str(d)] + ENC + [o])
    parts.append(o)

lst = os.path.join(work, 'list.txt')
open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', '-movflags', '+faststart', out])
print('ok', out)
