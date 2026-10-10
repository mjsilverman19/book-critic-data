import re
EN=set('the a an and of to in is it that this with as for his her but was he she not are be by on at from which its their have has one more than all'.split())
FX=set('der die das und ist nicht mit ein eine einen den dem von zu sich auf auch wie im des le la les et est des une dans pour qui que pas du au sur il elle el los las y en por con lo del una che di della non è per si nel het een van niet och att som är jest nie się'.split())
def is_english(t):
    w=re.findall(r"[^\W\d_]+",str(t).lower())
    if not w: return False
    return sum(x in EN for x in w)>=sum(x in FX for x in w)
