import os, glob, struct, zlib

outdir = os.path.dirname(os.path.abspath(__file__))

def ppm_to_png(ppm_path, png_path):
    with open(ppm_path, 'rb') as f:
        header = f.readline().strip()
        if header != b'P6':
            return False
        line = f.readline().strip()
        while line.startswith(b'#'):
            line = f.readline().strip()
        dims = line.split()
        w, h = int(dims[0]), int(dims[1])
        maxval = int(f.readline().strip())
        pixels = f.read()

    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(chunk) & 0xffffffff)
        return struct.pack('>I', len(data)) + chunk + crc

    signature = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    ihdr = make_chunk(b'IHDR', ihdr_data)

    raw = b''
    for y in range(h):
        raw += b'\x00'
        raw += pixels[y * w * 3:(y + 1) * w * 3]

    compressed = zlib.compress(raw)
    idat = make_chunk(b'IDAT', compressed)
    iend = make_chunk(b'IEND', b'')

    with open(png_path, 'wb') as f:
        f.write(signature + ihdr + idat + iend)
    return True

for ppm in sorted(glob.glob(os.path.join(outdir, 'ucitelji_img_*.ppm'))):
    png_path = ppm.replace('.ppm', '.png')
    if ppm_to_png(ppm, png_path):
        size = os.path.getsize(png_path)
        print(f'{os.path.basename(ppm)} -> {os.path.basename(png_path)} ({size} bytes)')
    else:
        print(f'Failed: {ppm}')

print('Done!')
