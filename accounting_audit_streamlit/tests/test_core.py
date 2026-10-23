import pandas as pd
from src.validators import tb_quality
from src.mapping import suggest_mapping
from src.financial_statements import build_statement
from src.audit_tests import duplicate_gl_rows

def test_tb_balanced():
    df=pd.DataFrame({"Account Code":["1","2"],"Debit":[100,0],"Credit":[0,100]})
    q=tb_quality(df)
    assert q.iloc[0]["Status"]=="Pass"

def test_tb_unbalanced():
    df=pd.DataFrame({"Account Code":["1"],"Debit":[100],"Credit":[50]})
    q=tb_quality(df)
    assert q.iloc[0]["Status"]=="Error"

def test_mapping_requires_approval():
    tb=pd.DataFrame({"Account Code":["100"],"Account Name":["เงินสด"],"Debit":[100],"Credit":[0],"_Source_Row":[2]})
    mp=suggest_mapping(tb)
    result=build_statement(tb,mp)
    assert result["balance_sheet"].empty
    assert len(result["unmapped_or_pending"])==1

def test_approved_mapping_included():
    tb=pd.DataFrame({"Account Code":["100"],"Account Name":["เงินสด"],"Debit":[100],"Credit":[0],"_Source_Row":[2]})
    mp=suggest_mapping(tb)
    mp.loc[0,"Reviewer Status"]="Approved"
    result=build_statement(tb,mp)
    assert len(result["balance_sheet"])==1

def test_duplicate_detection():
    from src.audit_tests import duplicate_gl_rows
    gl=pd.DataFrame({"Date":["2025-12-31"]*2,"Document No":["JV1"]*2,"Account Code":["1"]*2,
                     "Description":["x"]*2,"Debit":[100]*2,"Credit":[0]*2})
    assert len(duplicate_gl_rows(gl))==2
