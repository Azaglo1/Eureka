from PIL import Image
im = Image.open('favicon.png')
im = im.convert('RGB')
im = im.resize((100, 100))
pixels = list(im.getdata())
avg_r = sum(p[0] for p in pixels) // len(pixels)
avg_g = sum(p[1] for p in pixels) // len(pixels)
avg_b = sum(p[2] for p in pixels) // len(pixels)
print(f'#{avg_r:02x}{avg_g:02x}{avg_b:02x}')