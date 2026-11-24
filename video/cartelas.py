"""Gera as duas cartelas novas da retrospectiva (gancho e resultado) como quadros 1920x1080, 30 fps.
uso: python3 cartelas.py gancho|resultado saida.mp4
"""
import sys, subprocess, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1920, 1080, 30
import os
IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'img') + os.sep
F = '/usr/share/fonts/opentype/inter/'
def fonte(nome, t): return ImageFont.truetype(F + nome, t)
LARANJA = (232, 122, 40); VERDE = (53, 185, 133); TINTA = (234, 242, 236); MUDO = (150, 165, 156)
CINZA_CHIP = (60, 72, 66)

def fundo():
    y, x = np.mgrid[0:H, 0:W]
    d = np.sqrt(((x - W * .5) / (W * .62)) ** 2 + ((y - H * .5) / (H * .62)) ** 2).clip(0, 1)
    c0, c1 = np.array([16, 31, 22]), np.array([4, 9, 8])
    a = (c0 * (1 - d[..., None]) + c1 * d[..., None])
    a[::60, :] += 3; a[:, ::60] += 3                     # grade suave, como no vídeo
    return Image.fromarray(a.clip(0, 255).astype('uint8'))
BG = fundo()

def ease(t): t = max(0., min(1., t)); return t * t * (3 - 2 * t)
def fase(t, a, b): return ease((t - a) / (b - a))

def cabecalho(d, direita, k=1.0):
    cor = tuple(int(c * k) for c in LARANJA)
    d.text((80, 58), 'IGNIS ALERT', font=fonte('Inter-Bold.otf', 26), fill=cor)
    d.text((255, 58), '· Retrospectiva do dataset', font=fonte('Inter-Regular.otf', 26), fill=tuple(int(c * k) for c in (150, 158, 155)))
    f = fonte('Inter-SemiBold.otf', 26); w = d.textlength(direita, font=f)
    d.text((1840 - w, 58), direita, font=f, fill=tuple(int(c * k) for c in (200, 205, 200)))
    d.line((80, 100, 626, 100), fill=cor, width=4)

def foto(nome, larg, alt):
    im = Image.open(IMG + nome).convert('RGB'); r = max(larg / im.width, alt / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    x, y = (im.width - larg) // 2, (im.height - alt) // 2
    return im.crop((x, y, x + larg, y + alt))

def chip(d, x, y, texto, fundo_c, cor_t, tam=30):
    f = fonte('Inter-Bold.otf', tam); w = d.textlength(texto, font=f)
    d.rounded_rectangle((x, y, x + w + 36, y + tam + 26), radius=(tam + 26) // 2, fill=fundo_c)
    d.text((x + 18, y + 11), texto, font=f, fill=cor_t)
    return w + 36

def misturar(base, camada, alfa):
    return Image.blend(base, camada, alfa) if alfa < 1 else camada

# ---------------- gancho (6,5 s) ----------------
FOTO1 = foto('foto-01.jpg', 900, 600)
def gancho(t):
    im = BG.copy(); d = ImageDraw.Draw(im)
    a = fase(t, 0, .7)
    if a > 0:
        f = Image.blend(Image.new('RGB', FOTO1.size, (8, 14, 11)), FOTO1, a)
        im.paste(f, (110, 240)); d = ImageDraw.Draw(im)
        d.rectangle((110, 240, 1010, 840), outline=tuple(int(c * a) for c in LARANJA), width=3)
    if t > .7:
        k = fase(t, .7, 1.1)
        chip(d, 140, 270, 'pasta: SEM FOGO', tuple(int(c * k) for c in CINZA_CHIP), tuple(int(c * k) for c in TINTA))
    if t > 1.9:   # carimbo da revisão
        k = fase(t, 1.9, 2.25); s = 1 + .35 * (1 - k)
        f = fonte('Inter-Black.otf', round(52 * s)); txt = 'É INCÊNDIO'
        w = d.textlength(txt, font=f); cx, cy = 560, 740
        d.rounded_rectangle((cx - w / 2 - 26, cy - 44 * s, cx + w / 2 + 26, cy + 44 * s), radius=14,
                            fill=tuple(int(c * k) for c in LARANJA))
        d.text((cx - w / 2, cy - 33 * s), txt, font=f, fill=(255, 255, 255) if k > .5 else LARANJA)
    # texto à direita
    fT = fonte('InterDisplay-Bold.otf', 62); fS = fonte('Inter-Regular.otf', 38)
    if t > 2.3:
        k = fase(t, 2.3, 2.9)
        cor = tuple(int(c * k) for c in TINTA)
        for i, l in enumerate(['Este incêndio estava', 'guardado como', '“sem fogo”.']):
            d.text((1090, 300 + i * 76 + (1 - k) * 20), l, font=fT, fill=cor if i < 2 else tuple(int(c * k) for c in LARANJA))
    if t > 3.7:
        k = fase(t, 3.7, 4.3); cor = tuple(int(c * k) for c in (200, 210, 204))
        for i, l in enumerate(['Num dataset público, sem', 'ninguém ter conferido.']):
            d.text((1090, 560 + i * 52), l, font=fS, fill=cor)
    if t > 4.6:
        k = fase(t, 4.6, 5.1); cor = tuple(int(c * k) for c in LARANJA)
        d.text((1090, 700), 'Quem confere o que o', font=fonte('Inter-SemiBold.otf', 40), fill=cor)
        d.text((1090, 752), 'alarme vai aprender?', font=fonte('Inter-SemiBold.otf', 40), fill=cor)
    out = fase(t, 6.0, 6.5)     # escurece para a abertura original
    return Image.blend(im, Image.new('RGB', (W, H), (4, 9, 8)), out) if out > 0 else im

# ---------------- resultado (7 s) ----------------
LIMIAR = .2274
CASOS = [  # dados de relatorios/12_treino/efficientnet_b0_torchvision/predicoes_teste.csv
    dict(img='fire.676.jpg', nome='fire.676', antes='rótulo: com fogo', p=.9981, alerta=True),
    dict(img='foto-02.jpg', nome='fire.320', antes='pasta “fogo”, mas é só fumaça', p=.0311, alerta=False),
]
FOTOS = [foto(c['img'], 760, 400) for c in CASOS]
def pct(v): return f'{v * 100:.1f}'.replace('.', ',') + '%'
def resultado(t):
    im = BG.copy(); d = ImageDraw.Draw(im)
    k0 = fase(t, 0, .5); cabecalho(d, 'RESULTADO', k0)
    d.text((80, 140), 'O modelo escolhido, em fotos reais do teste', font=fonte('InterDisplay-Bold.otf', 54),
           fill=tuple(int(c * k0) for c in TINTA))
    d.text((80, 212), 'EfficientNet-B0 · imagens que a rede nunca viu no treino', font=fonte('Inter-Regular.otf', 30),
           fill=tuple(int(c * k0) for c in MUDO))
    for i, c in enumerate(CASOS):
        x0, y0 = 80 + i * 920, 280
        k = fase(t, .4 + i * .5, 1.0 + i * .5)
        if k <= 0: continue
        f = Image.blend(Image.new('RGB', FOTOS[i].size, (8, 14, 11)), FOTOS[i], k)
        im.paste(f, (x0, y0)); d = ImageDraw.Draw(im)
        d.text((x0, y0 + 416), c['nome'], font=fonte('Inter-Bold.otf', 30), fill=tuple(int(v * k) for v in TINTA))
        d.text((x0 + 140, y0 + 418), c['antes'], font=fonte('Inter-Regular.otf', 28), fill=tuple(int(v * k) for v in MUDO))
        # barra de probabilidade de fogo, com o limiar
        by, bw = y0 + 484, 760
        d.rounded_rectangle((x0, by, x0 + bw, by + 26), radius=13, fill=tuple(int(v * k) for v in (40, 52, 46)))
        g = fase(t, 1.6 + i * .5, 2.8 + i * .5); v = c['p'] * g
        cor = LARANJA if c['alerta'] else VERDE
        if v > .01: d.rounded_rectangle((x0, by, x0 + max(26, bw * v), by + 26), radius=13, fill=cor)
        lx = x0 + bw * LIMIAR
        d.line((lx, by - 12, lx, by + 38), fill=tuple(int(v2 * k) for v2 in TINTA), width=3)
        d.text((lx + 8, by + 34), 'limiar 22,7%', font=fonte('Inter-Regular.otf', 22), fill=tuple(int(v2 * k) for v2 in MUDO))
        d.text((x0, by + 66), pct(v) + ' de fogo', font=fonte('InterDisplay-Bold.otf', 46), fill=cor if g > 0 else MUDO)
        if t > 3.0 + i * .5:
            kk = fase(t, 3.0 + i * .5, 3.4 + i * .5)
            txt = 'ALERTA' if c['alerta'] else 'SEM ALERTA'
            fz = fonte('Inter-Bold.otf', 28); w = d.textlength(txt, font=fz)
            xx = x0 + bw - w - 36
            d.rounded_rectangle((xx, by + 72, xx + w + 36, by + 122), radius=25, fill=tuple(int(v2 * kk) for v2 in cor))
            d.text((xx + 18, by + 81), txt, font=fz, fill=tuple(int(v2 * kk) for v2 in (255, 255, 255)))
    if t > 4.3:   # legenda no estilo das outras cenas
        k = fase(t, 4.3, 4.8); f1 = fonte('Inter-Medium.otf', 38); f2 = fonte('Inter-Bold.otf', 38)
        partes = [('No teste inteiro, ', f1, TINTA), ('205 de 207', f2, LARANJA), (' imagens certas.', f1, TINTA)]
        w = sum(d.textlength(p, font=fo) for p, fo, _ in partes); x = (W - w) / 2
        d.rounded_rectangle((x - 34, 966, x + w + 34, 1042), radius=10, fill=tuple(int(v * k) for v in (8, 12, 10)))
        d.rectangle((x - 34, 966, x - 28, 1042), fill=tuple(int(v * k) for v in LARANJA))
        for p, fo, cor in partes:
            d.text((x, 981), p, font=fo, fill=tuple(int(v * k) for v in cor)); x += d.textlength(p, font=fo)
    out = fase(t, 6.6, 7.0)
    return Image.blend(im, Image.new('RGB', (W, H), (4, 9, 8)), out) if out > 0 else im

if __name__ == '__main__':
    qual, saida = sys.argv[1], sys.argv[2]
    fn, dur = (gancho, 6.5) if qual == 'gancho' else (resultado, 7.0)
    if len(sys.argv) > 3:       # prévia: quadros em instantes dados
        for s in sys.argv[3:]: fn(float(s)).save(f'{saida}_{s}.png')
        sys.exit()
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-f', 'lavfi', '-i', f'anoisesrc=color=brown:amplitude=0.25:d={dur},lowpass=f=320,volume=0.9,'
                          f'afade=t=in:d=0.8,afade=t=out:st={dur - 1.0}:d=1.0',
                          '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS),
                          '-c:a', 'aac', '-ar', '44100', '-ac', '2', '-shortest', saida], stdin=subprocess.PIPE)
    for i in range(round(dur * FPS)):
        p.stdin.write(fn(i / FPS).tobytes())
    p.stdin.close(); p.wait()
