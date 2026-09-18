"""Create page PNGs and side-by-side images; never report blank-pixel accuracy."""
import argparse,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--render',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--dpi',type=int,default=150);p.add_argument('--deps',type=Path);a=p.parse_args()
    if a.deps:sys.path.insert(0,str(a.deps.resolve()))
    try:import pymupdf
    except ImportError:print('Install optional dependency locally: python -m pip install --target <project>/deps pymupdf');return 2
    if a.out.exists():print('Output folder must be new');return 2
    if not 72<=a.dpi<=400:print('DPI must be 72..400');return 2
    a.out.mkdir(parents=True)
    docs=[('source',pymupdf.open(a.source))]
    if a.render:docs.append(('render',pymupdf.open(a.render)))
    for label,doc in docs:
        for i,page in enumerate(doc):
            page.get_pixmap(dpi=a.dpi,alpha=False).save(a.out/f'{label}-{i+1}.png')
            # Three overlapping horizontal strips per page reduce repeated cropping.
            for band in range(3):
                h=page.rect.height;clip=pymupdf.Rect(0,max(0,band*h/3-h*.03),page.rect.width,min(h,(band+1)*h/3+h*.03))
                page.get_pixmap(dpi=a.dpi,clip=clip,alpha=False).save(a.out/f'{label}-{i+1}-strip-{band+1}.png')
    count=len(docs[0][1]);html=['<!doctype html><meta charset="utf-8"><title>Score review</title><style>body{font:16px system-ui}section{display:flex}img{width:49%;object-fit:contain;align-self:flex-start}</style><h1>Original source / MSCZ render</h1><p>Review every measure. Image similarity is not musical accuracy.</p>']
    for i in range(max(len(d) for _,d in docs)):
        html.append(f'<h2>Page {i+1}</h2><section>')
        for label,d in docs:
            if i<len(d):html.append(f'<img src="{label}-{i+1}.png" alt="{label} page {i+1}">')
        html.append('</section>')
    (a.out/'index.html').write_text('\n'.join(html),encoding='utf-8')
    print('Review images:',a.out/'index.html')
    for _,d in docs:d.close()
    return 0
if __name__=='__main__':sys.exit(main())
