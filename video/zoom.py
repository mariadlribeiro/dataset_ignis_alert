"""Amplia as telas de inventário (0:21-0:33) e de detalhamento (1:28-1:41) da retrospectiva,
mantendo a legenda queimada na imagem no lugar original. Só o vídeo; o áudio é copiado depois.
uso: python3 zoom.py entrada.mp4 saida.mp4 [instantes para prévia...]
"""
import sys, subprocess
import numpy as np, cv2

W, H, FPS = 1920, 1080, 30
CHEIO = (1.0, 960, 540)
def lado(cx, cy, s=1.65): return (s, cx, cy)
# (tempo em s, estado): entre dois pontos, transição suave
CHAVES = [
    (21.2, CHEIO), (21.9, (1.4, 500, 476)), (25.4, (1.4, 500, 476)), (26.3, (1.4, 1234, 500)),
    (32.3, (1.4, 1234, 500)), (33.0, CHEIO),
    (88.0, CHEIO), (88.7, (1.45, 662, 465)), (90.0, (1.45, 662, 465)), (90.8, (1.4, 1234, 476)),
    (97.5, (1.4, 1234, 476)), (98.3, (1.25, 768, 480)), (100.8, (1.25, 768, 480)), (101.4, CHEIO),
]
CORTE = 900   # daqui para baixo fica o quadro original (só fundo e legenda)
OY = 470      # o centro do zoom vai para esta altura, acima da legenda

def estado(t):
    if t <= CHAVES[0][0] or t >= CHAVES[-1][0]: return CHEIO
    for (t0, a), (t1, b) in zip(CHAVES, CHAVES[1:]):
        if t0 <= t <= t1:
            if a == b: return a
            u = (t - t0) / (t1 - t0); u = u * u * (3 - 2 * u)
            return tuple(x + (y - x) * u for x, y in zip(a, b))
    return CHEIO

def aplicar(fr, t):
    s, cx, cy = estado(t)
    if s <= 1.0001: return fr
    k = (s - 1) / 0.25 if s < 1.25 else 1.0          # no começo da transição, o centro vai aos poucos para OY
    oy = 540 + (OY - 540) * min(1.0, k)
    hw = W / 2 / s
    cx = min(max(cx, hw), W - hw); cy = max(cy, oy / s)
    M = np.float32([[s, 0, W / 2 - s * cx], [0, s, oy - s * cy]])
    out = cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    # abaixo de CORTE, o quadro original (fundo e legenda), com emenda suave
    r = 40; a = CORTE - r
    m = np.linspace(0, 1, r, dtype=np.float32)[:, None, None]
    out[a:CORTE] = (fr[a:CORTE] * m + out[a:CORTE] * (1 - m)).astype(np.uint8)
    out[CORTE:] = fr[CORTE:]
    return out

if __name__ == '__main__':
    ent, sai = sys.argv[1], sys.argv[2]
    if len(sys.argv) > 3:
        for ts in sys.argv[3:]:
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', ts, '-i', ent, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True).stdout
            fr = np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy()
            cv2.imwrite(f'{sai}_{ts}.png', aplicar(fr, float(ts)))
        sys.exit()
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', ent, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-i', ent, '-map', '0:v', '-map', '1:a', '-c:a', 'copy',
                            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', sai], stdin=subprocess.PIPE)
    n, tam = 0, W * H * 3
    while True:
        buf = dec.stdout.read(tam)
        if len(buf) < tam: break
        fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        enc.stdin.write(aplicar(fr.copy(), n / FPS).tobytes()); n += 1
    enc.stdin.close(); enc.wait(); print('quadros', n)
