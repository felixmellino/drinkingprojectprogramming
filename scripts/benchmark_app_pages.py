"""Run actual pages with synthetic records/50 ms reads; no live client allowed.

Run in a separate process: python scripts/benchmark_app_pages.py
These are Streamlit server render times, excluding a browser/phone and hosting.
"""
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
import json

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import supabase
supabase.create_client=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('Live client disabled in page benchmark'))
from streamlit.testing.v1 import AppTest


def main():
    fixture=Path(__file__).resolve().parents[1]/'tests/fixtures/performance_app.py'
    report={}
    for route in ('profile','lobby','check_in_photos','standings','map'):
        page=AppTest.from_file(fixture,default_timeout=15)
        page.query_params['qa_page']=route
        start=perf_counter()
        page.run()
        first=round((perf_counter()-start)*1000,2)
        if page.exception: raise RuntimeError(str(page.exception))
        times=[];counts=[]
        for _ in range(3):
            start=perf_counter();page.run();times.append((perf_counter()-start)*1000)
            if page.exception: raise RuntimeError(str(page.exception))
            counts.append(len(page.session_state['_qa_reads']))
        report[route]={'first_render_ms':first,'median_warm_render_ms':round(median(times),2),
                       'read_count_range':[min(counts),max(counts)]}
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
