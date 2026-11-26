# Gera docs/i18n.js a partir de p1.py e p2.py (pt -> en, es). Uso: python docs/i18n_fonte/build.py
import json,re,importlib.util
rows=[]
for f in ('p1','p2'):
    import os; sp=importlib.util.spec_from_file_location(f,os.path.join(os.path.dirname(os.path.abspath(__file__)),f+'.py')); m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m); rows+=m.T
en,es={},{}
for pt,e,s in rows:
    assert pt.count('#')==e.count('#')==s.count('#'),(pt,e,s)
    en[pt]=e; es[pt]=s
    m=re.match(r'^\(([^)]*)\): (.*)$',pt)
    if m:
        e2=re.match(r'^\(([^)]*)\): (.*)$',e).group(2); s2=re.match(r'^\(([^)]*)\): (.*)$',s).group(2)
        en.setdefault(m.group(2),e2); es.setdefault(m.group(2),s2)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','i18n.js'),'w',encoding='utf-8').write(
 '/* Traduções do site (pt → en, es). Chaves = texto em português com os números trocados por #. Gerado de i18n_src. */\nwindow.I18N = '+json.dumps({'en':en,'es':es},ensure_ascii=False,separators=(',',':'))+';\n')
print(len(rows),len(en))
