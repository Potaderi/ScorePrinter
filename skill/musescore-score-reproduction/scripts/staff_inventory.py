"""Independent horizontal five-line staff hints from rendered source pixels.

This conservative detector is a second coverage signal, not general OMR. Handwriting,
skewed/broken/short staff lines and tablature still require source-page inspection.
"""

def staff_hints(samples, width, height, threshold=180):
    if len(samples) != width * height:
        raise ValueError('Expected an 8-bit grayscale image')
    dark = bytes([1 if value < threshold else 0 for value in range(256)])
    runs, run = [], []
    minimum = width * .33
    for y in range(height):
        row = samples[y*width:(y+1)*width]
        if sum(row.translate(dark)) >= minimum:
            run.append(y)
        elif run:
            runs.append(sum(run)/len(run))
            run = []
    if run:
        runs.append(sum(run)/len(run))
    result, used = [], set()
    for i in range(len(runs)-4):
        indices = set(range(i, i+5))
        if indices & used:
            continue
        lines = runs[i:i+5]
        gaps = [b-a for a,b in zip(lines,lines[1:])]
        mean = sum(gaps)/4
        if mean < 3 or mean > height*.04 or max(abs(g-mean) for g in gaps) > max(1.5,mean*.2):
            continue
        result.append({'lines': [round(y/height,6) for y in lines],
                       'center': sum(lines)/5/height,
                       'bbox': [0,max(0,(lines[0]-mean*2)/height),1,min(1,(lines[-1]+mean*2)/height)]})
        used |= indices
    return result


def coverage_findings(hints, recognized, tolerance=.009):
    """Find independent source staff hints absent from OMR's staff inventory."""
    findings = []
    remaining = list(recognized)
    for hint in hints:
        matches = [(abs(hint['center']-s['center']),i) for i,s in enumerate(remaining)
                   if s['page'] == hint['page']]
        if matches and min(matches)[0] <= tolerance:
            remaining.pop(min(matches)[1])
        else:
            findings.append(dict(hint, reason='Possible omitted staff: source-pixel lines have no OMR staff',
                                 kind='coverage', severity='high'))
    return findings
