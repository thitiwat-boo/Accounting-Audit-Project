from __future__ import annotations
import pandas as pd

def _num(s): return pd.to_numeric(s,errors='coerce')
def tb_quality(tb: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for col in ['Account Code','Account Name','Debit','Credit']:
        rows.append({'Check':f'Required column: {col}','Status':'Pass' if col in tb.columns else 'Critical','Detail':'พบคอลัมน์' if col in tb.columns else 'ไม่พบคอลัมน์ที่จำเป็น'})
    if {'Debit','Credit'}.issubset(tb.columns):
        d=_num(tb.Debit); c=_num(tb.Credit); invalid=int(d.isna().sum()+c.isna().sum()); diff=round(float(d.fillna(0).sum()-c.fillna(0).sum()),2)
        rows += [{'Check':'TB Debit = Credit','Status':'Pass' if abs(diff)<.01 else 'Critical','Detail':f'Debit={d.fillna(0).sum():,.2f}; Credit={c.fillna(0).sum():,.2f}; Difference={diff:,.2f}'},
                 {'Check':'Invalid numeric values','Status':'Critical' if invalid else 'Pass','Detail':f'จำนวนช่อง Debit/Credit ที่แปลงเป็นตัวเลขไม่ได้: {invalid}'}]
    if 'Account Code' in tb:
        codes=tb['Account Code'].fillna('').astype(str).str.strip(); missing=int(codes.eq('').sum()); dup=int(codes.duplicated(keep=False).sum())
        rows += [{'Check':'Missing account code','Status':'Critical' if missing else 'Pass','Detail':f'{missing} แถว'}, {'Check':'Duplicate account code','Status':'Warning' if dup else 'Pass','Detail':f'{dup} แถว; ตรวจว่ารหัสซ้ำเป็น subtotal หรือรายการจริง'}]
    return pd.DataFrame(rows)

def gl_quality(gl: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for col in ['Date','Document No','Account Code','Debit','Credit']:
        rows.append({'Check':f'Required column: {col}','Status':'Pass' if col in gl.columns else 'Warning','Detail':'พบคอลัมน์' if col in gl.columns else 'ไม่พบคอลัมน์; ตรวจความเหมาะสมกับ GL'})
    if {'Debit','Credit'}.issubset(gl.columns):
        d=_num(gl.Debit); c=_num(gl.Credit); invalid=int(d.isna().sum()+c.isna().sum()); diff=round(float(d.fillna(0).sum()-c.fillna(0).sum()),2)
        rows += [{'Check':'GL total debit = credit','Status':'Pass' if abs(diff)<.01 else 'Critical','Detail':f'Debit={d.fillna(0).sum():,.2f}; Credit={c.fillna(0).sum():,.2f}; Difference={diff:,.2f}'}, {'Check':'Invalid numeric values','Status':'Critical' if invalid else 'Pass','Detail':f'{invalid} ช่อง'}]
    if 'Date' in gl:
        dt=pd.to_datetime(gl.Date,errors='coerce',dayfirst=True); n=int(dt.isna().sum()); rows.append({'Check':'GL date validity','Status':'Critical' if n else 'Pass','Detail':f'วันที่ว่าง/อ่านไม่ได้ {n} แถว'})
    return pd.DataFrame(rows)

def duplicate_gl_rows(gl: pd.DataFrame) -> pd.DataFrame:
    # Flag identical transaction lines, never document number alone. Paired debit/credit lines naturally differ by account/amount.
    cols=[c for c in ['Date','Document No','Account Code','Debit','Credit','Description','Reference'] if c in gl.columns]
    if len(cols)<4: return pd.DataFrame(columns=list(gl.columns)+['Duplicate Reason'])
    mask=gl.duplicated(subset=cols,keep=False)
    out=gl.loc[mask].copy()
    if not out.empty: out['Duplicate Reason']='Identical composite transaction key; confirm whether duplicate posting'
    return out
