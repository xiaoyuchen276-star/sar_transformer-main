"""Import author-provided means; this does not run an image metric or model."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import json, re, shutil

ROOT = Path(r"D:\research\sar_transformer-main")
OUT = ROOT / "output/pdf/GRSL_ICEYE20_revision_20261115"
SOURCE = Path(r"D:\Users\Chen\Desktop\实验结果.md")
PAPER = ROOT / "docs/GRSL_LaTeX/GRSL-02805-2026_Revised_Clean.tex"
rows = [[c.strip().strip('*') for c in line.strip().strip('|').split('|')]
        for line in SOURCE.read_text(encoding='utf8').splitlines() if line.startswith('|')]
methods = ['Noisy','SAR-BM3D','SAR2SAR','SDUDNet','Trans-SAR','Ours-base','Ours+AMS']
whole = {r[0]: r[1:] for r in rows if len(r)==5 and r[0] in methods}
groups = {k: {r[2]:r[3:] for r in rows if len(r)==7 and r[0].endswith(k) and r[2] in methods}
          for k in ['H','S','T']}
pending = []
for name, group in [('whole',whole),*groups.items()]:
    noisy = Decimal(group['Noisy'][-1])
    if not all(Decimal(v[-1])<=noisy for k,v in group.items() if k!='Noisy'):
        pending.append(name)
assert 'whole' not in pending, 'Whole-scene RGPI must be reconciled first'
average = {m:[('--' if i==1 and m=='Noisy' else str((sum(Decimal(groups[c][m][i]) for c in groups)/3).quantize(Decimal('0.01' if i==0 else '0.0001'),rounding=ROUND_HALF_UP))) for i in range(4)] for m in ['Noisy','Ours-base','Ours+AMS']}

def opening(caption,label):
    return '\n'.join([r'\begin{table}[!t]',r'\caption{\rev{'+caption+'}}',r'\label{'+label+'}',r'\centering',r'\footnotesize',r'\setlength{\tabcolsep}{2.5pt}',r'\renewcommand{\arraystretch}{1.04}',r'\rev{\begin{tabular*}{\columnwidth}{@{\extracolsep{\fill}}lrrrr@{}}',r'\toprule',r'\textbf{Method} & \textbf{ENL} & \textbf{M-index}\,$\downarrow$ & \textbf{EPI} & \textbf{RGPI}\,$\uparrow$ \\',r'\midrule'])+'\n'
def closing(note):
    return '\n'.join([r'\bottomrule',r'\end{tabular*}}',r'\vspace{1pt}',r'\parbox{\columnwidth}{\footnotesize\rev{'+note+'}}',r'\end{table}'])

iv = opening('Mean No-Reference Results on 20 Complete ICEYE Scenes','tab:real')
for method in methods:
    values = [v.replace('—','--') for v in whole[method]]
    for i,second in [(1,'SDUDNet'),(2,'SAR-BM3D'),(3,'SAR2SAR')]:
        if method=='Ours+AMS': values[i]=r'\textbf{'+values[i]+'}'
        elif method==second: values[i]=r'\underline{'+values[i]+'}'
    iv += ' & '.join([method,*values])+r' \\'+'\n'
iv += closing('Each parent scene has equal weight. ENL is a mean smoothness diagnostic and is not ranked. Noisy is excluded from ranking; its M-index is undefined. Bold and underlined entries mark the best and second-best filtered scores.')

v = opening('Mean No-Reference Results by ICEYE Region Type','tab:real_scenes')
for category,name in [('H','Homogeneous: 20 regions'),('S','Structural: 20 regions'),('T','Textured: 20 regions'),('Average','Average: 60 regions from 20 parents')]:
    v += r'\multicolumn{5}{@{}l@{}}{\textit{'+name+r'}} \\'+'\n'
    for method in ['Noisy','Ours-base','Ours+AMS']:
        values = [x.replace('—','--') for x in (average[method] if category=='Average' else groups[category][method])]
        if method=='Ours+AMS':
            for i in [1,2,3]: values[i]=r'\textbf{'+values[i]+'}'
        if category in pending or (category=='Average' and pending):
            values[3] = '--'
        v += ' & '.join([method,*values])+r' \\'+'\n'
    if category!='Average': v += r'\midrule'+'\n'
v += closing(r'Each category uses the same twenty fixed $256\times256$ regions for both models. Average weights the three category means equally. Bold marks the better filtered M-index, EPI, and RGPI; ENL is not ranked.' + (' RGPI for H and Average awaits data confirmation.' if pending else ''))

s=PAPER.read_text(encoding='utf8')
for label,table in [('tab:real',iv),('tab:real_scenes',v)]:
    spans=list(re.finditer(r'\\begin\{table\}(?:\[[^\]]*\])?.*?\\end\{table\}',s,re.S))
    matching=[m for m in spans if r'\label{'+label+'}' in m.group()]
    assert len(matching)==1
    m=matching[0]; s=s[:m.start()]+table+s[m.end():]
s=s.replace('% Source: ../实验结果表.md. All scene and Average entries are reproduced\n% from the experimental-results table, as confirmed by the author.','% Source: author-updated Desktop/实验结果.md, 2026-11-15.\n% Average is computed from the supplied rounded category means; remote raw scores remain unavailable.')
PAPER.write_text(s,encoding='utf8')
shutil.copy2(SOURCE,OUT/'author_results_updated.md')
(OUT/'imported_results.json').write_text(json.dumps({'whole':whole,'groups':groups,'average_from_displayed_means':average,'rgpi_pending':pending,'source':str(SOURCE),'metric_recomputation_performed':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(average,ensure_ascii=False))
